#!/bin/bash

set -e  # Exit on any error

# Configuration for eth-booking
SERVICE_NAME="eth-booking"
ECR_REPO_NAME="aerticket-booking"
K8S_DEPLOYMENT_NAME="aerticket-booking"
K8S_CONTAINER_NAME="booking"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_REGION="ap-south-1"
AWS_ACCOUNT_ID="722955677910"
ECR_BASE_URL="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
K8S_NAMESPACE="aerticket"
K8S_DEPLOYMENT_FILE="/Users/riz/aws-eks-infrastructure/k8s/aerticket/booking-deployment.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_header() {
    echo -e "${PURPLE}=== $1 ===${NC}"
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Deploy eth-booking service to EKS"
    echo ""
    echo "Options:"
    echo "  -b, --branch BRANCH      Git branch to deploy (default: main)"
    echo "  -t, --tag TAG           Docker image tag (default: current timestamp)"
    echo "  -n, --no-build          Skip build and use existing images"
    echo "  -r, --restart-only      Only restart the deployment (no pull/build)"
    echo "  -s, --status            Show current deployment status"
    echo "  -d, --dry-run           Show what would be done without executing"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --branch main"
    echo "  $0 --branch feature/new-booking --tag v1.2.3"
    echo "  $0 --no-build --tag latest"
    echo "  $0 --restart-only"
    echo "  $0 --status"
}

# Parse command line arguments
BRANCH="main"
TAG=""
NO_BUILD=false
RESTART_ONLY=false
SHOW_STATUS=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--branch)
            BRANCH="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -n|--no-build)
            NO_BUILD=true
            shift
            ;;
        -r|--restart-only)
            RESTART_ONLY=true
            shift
            ;;
        -s|--status)
            SHOW_STATUS=true
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option $1"
            show_help
            exit 1
            ;;
    esac
done

# Set default tag if not provided
if [[ -z "$TAG" ]]; then
    TAG=$(date +"%Y%m%d_%H%M%S")
fi

# Function to show deployment status
show_deployment_status() {
    log_header "ETH-BOOKING Deployment Status"
    
    echo "Deployment:"
    if kubectl get deployment "$K8S_DEPLOYMENT_NAME" -n "$K8S_NAMESPACE" &> /dev/null; then
        kubectl get deployment "$K8S_DEPLOYMENT_NAME" -n "$K8S_NAMESPACE"
    else
        log_warning "Deployment $K8S_DEPLOYMENT_NAME not found"
    fi
    
    echo ""
    echo "Pods:"
    kubectl get pods -l app="$K8S_DEPLOYMENT_NAME" -n "$K8S_NAMESPACE" 2>/dev/null || log_warning "No pods found"
    
    echo ""
    echo "Service:"
    kubectl get service "$K8S_DEPLOYMENT_NAME" -n "$K8S_NAMESPACE" 2>/dev/null || log_warning "Service not found"
    
    echo ""
    echo "Recent Events:"
    kubectl get events --sort-by=.metadata.creationTimestamp -n "$K8S_NAMESPACE" | grep "$K8S_DEPLOYMENT_NAME" | tail -5 || echo "No recent events"
}

# If only status is requested
if [[ "$SHOW_STATUS" == "true" ]]; then
    show_deployment_status
    exit 0
fi

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites for eth-booking deployment..."
    
    # Check if we're in the right directory
    if [[ ! -f "$SCRIPT_DIR/Dockerfile" ]]; then
        log_error "Dockerfile not found in $SCRIPT_DIR"
        log_error "Make sure you're running this script from the eth-booking directory"
        exit 1
    fi
    
    # Check if AWS CLI is installed and configured
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed or not in PATH"
        exit 1
    fi
    
    # Check if Docker is running
    if [[ "$NO_BUILD" == "false" && "$RESTART_ONLY" == "false" ]]; then
        if ! docker info &> /dev/null; then
            log_error "Docker is not running or not accessible"
            exit 1
        fi
    fi
    
    # Check if kubectl is installed and configured
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    # Test kubectl connection
    if ! kubectl get nodes &> /dev/null; then
        log_error "kubectl is not configured or cluster is not accessible"
        exit 1
    fi
    
    # Check if deployment file exists
    if [[ ! -f "$K8S_DEPLOYMENT_FILE" ]]; then
        log_error "Kubernetes deployment file not found: $K8S_DEPLOYMENT_FILE"
        exit 1
    fi
    
    log_success "All prerequisites satisfied"
}

# Function to authenticate with ECR
ecr_login() {
    if [[ "$NO_BUILD" == "true" || "$RESTART_ONLY" == "true" ]]; then
        log_info "Skipping ECR authentication (no build required)"
        return
    fi
    
    log_info "Authenticating with ECR..."
    if [[ "$DRY_RUN" == "false" ]]; then
        aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_BASE_URL
        log_success "ECR authentication successful"
    else
        log_info "[DRY RUN] Would authenticate with ECR"
    fi
}

# Function to create ECR repository if it doesn't exist
create_ecr_repo() {
    if [[ "$NO_BUILD" == "true" || "$RESTART_ONLY" == "true" ]]; then
        log_info "Skipping ECR repository check (no build required)"
        return
    fi
    
    log_info "Ensuring ECR repository exists: $ECR_REPO_NAME"
    
    if [[ "$DRY_RUN" == "false" ]]; then
        if ! aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION &> /dev/null; then
            log_info "Creating ECR repository: $ECR_REPO_NAME"
            aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION
            log_success "Created ECR repository: $ECR_REPO_NAME"
        else
            log_info "ECR repository already exists: $ECR_REPO_NAME"
        fi
    else
        log_info "[DRY RUN] Would ensure ECR repository exists: $ECR_REPO_NAME"
    fi
}

# Function to pull latest code
pull_code() {
    if [[ "$RESTART_ONLY" == "true" ]]; then
        log_info "Skipping code pull (restart only mode)"
        return
    fi
    
    log_info "Pulling latest code for eth-booking from branch $BRANCH..."
    
    cd "$SCRIPT_DIR"
    
    if [[ "$DRY_RUN" == "false" ]]; then
        # Check if it's a git repository
        if [[ -d ".git" ]]; then
            # Stash any local changes
            if git diff --quiet && git diff --staged --quiet; then
                log_info "No local changes to stash"
            else
                log_info "Stashing local changes..."
                git stash push -m "Auto-stash before deployment $(date)"
            fi
            
            # Fetch latest changes
            log_info "Fetching latest changes..."
            git fetch origin
            
            # Switch to the specified branch
            if git branch -r | grep -q "origin/$BRANCH"; then
                log_info "Switching to branch $BRANCH..."
                git checkout $BRANCH
                git pull origin $BRANCH
                log_success "Updated eth-booking to latest $BRANCH"
            else
                log_error "Branch $BRANCH not found for eth-booking"
                exit 1
            fi
        else
            log_warning "eth-booking is not a git repository, skipping git pull"
        fi
    else
        log_info "[DRY RUN] Would pull latest code for eth-booking from branch $BRANCH"
    fi
}

# Function to build and push Docker image
build_and_push() {
    if [[ "$NO_BUILD" == "true" || "$RESTART_ONLY" == "true" ]]; then
        log_info "Skipping Docker build and push"
        return
    fi
    
    local image_uri="$ECR_BASE_URL/$ECR_REPO_NAME:$TAG"
    local latest_uri="$ECR_BASE_URL/$ECR_REPO_NAME:latest"
    
    log_info "Building and pushing Docker image for eth-booking..."
    log_info "Image URI: $image_uri"
    
    cd "$SCRIPT_DIR"
    
    if [[ "$DRY_RUN" == "false" ]]; then
        # Build the Docker image
        log_info "Building Docker image..."
        docker build -t "$image_uri" -t "$latest_uri" .
        
        # Push both tagged and latest images
        log_info "Pushing Docker image: $image_uri"
        docker push "$image_uri"
        
        log_info "Pushing Docker image: $latest_uri"
        docker push "$latest_uri"
        
        log_success "Successfully built and pushed eth-booking image"
    else
        log_info "[DRY RUN] Would build and push Docker image: $image_uri"
    fi
}

# Function to update Kubernetes deployment
update_k8s_deployment() {
    local image_uri="$ECR_BASE_URL/$ECR_REPO_NAME:$TAG"
    
    log_info "Updating Kubernetes deployment for eth-booking..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        # Update the image in the deployment
        log_info "Setting new image: $image_uri"
        kubectl set image deployment/$K8S_DEPLOYMENT_NAME $K8S_CONTAINER_NAME=$image_uri -n $K8S_NAMESPACE
        
        # Wait for rollout to complete
        log_info "Waiting for rollout to complete..."
        kubectl rollout status deployment/$K8S_DEPLOYMENT_NAME -n $K8S_NAMESPACE --timeout=300s
        
        log_success "Successfully updated deployment for eth-booking"
    else
        log_info "[DRY RUN] Would update deployment $K8S_DEPLOYMENT_NAME with image: $image_uri"
    fi
}

# Function to restart deployment (force refresh)
restart_deployment() {
    log_info "Restarting deployment for eth-booking..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        kubectl rollout restart deployment/$K8S_DEPLOYMENT_NAME -n $K8S_NAMESPACE
        kubectl rollout status deployment/$K8S_DEPLOYMENT_NAME -n $K8S_NAMESPACE --timeout=300s
        log_success "Successfully restarted deployment for eth-booking"
    else
        log_info "[DRY RUN] Would restart deployment: $K8S_DEPLOYMENT_NAME"
    fi
}

# Function to show logs
show_logs() {
    log_info "Recent logs from eth-booking:"
    kubectl logs --tail=20 deployment/$K8S_DEPLOYMENT_NAME -n $K8S_NAMESPACE || log_warning "Could not fetch logs"
}

# Main execution
main() {
    log_header "ETH-BOOKING Deployment Script"
    log_info "Branch: $BRANCH"
    log_info "Tag: $TAG"
    log_info "No Build: $NO_BUILD"
    log_info "Restart Only: $RESTART_ONLY"
    log_info "Dry Run: $DRY_RUN"
    
    # Check prerequisites
    check_prerequisites
    
    if [[ "$RESTART_ONLY" == "true" ]]; then
        # Only restart the deployment
        restart_deployment
    else
        # Full deployment process
        ecr_login
        create_ecr_repo
        pull_code
        build_and_push
        
        if [[ "$NO_BUILD" == "false" ]]; then
            update_k8s_deployment
        else
            restart_deployment
        fi
    fi
    
    # Show final status
    echo ""
    show_deployment_status
    
    # Show recent logs
    echo ""
    show_logs
    
    log_success "ETH-BOOKING deployment process completed successfully!"
}

# Execute main function
main "$@"
