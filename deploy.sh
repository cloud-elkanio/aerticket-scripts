#!/bin/bash

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_REGION="ap-south-1"
AWS_ACCOUNT_ID="722955677910"
ECR_BASE_URL="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
K8S_DIR="/home/ubuntu/production-manifests/resources/scripts"

# Service configurations
declare -A SERVICES=(
    ["eth-api"]="aerticket-api"
    ["eth-booking"]="aerticket-booking"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Deploy eth-api and eth-booking services to EKS"
    echo ""
    echo "Options:"
    echo "  -s, --service SERVICE    Deploy specific service (eth-api|eth-booking|all)"
    echo "  -b, --branch BRANCH      Git branch to deploy (default: main)"
    echo "  -t, --tag TAG           Docker image tag (default: current timestamp)"
    echo "  -n, --no-build          Skip build and use existing images"
    echo "  -d, --dry-run           Show what would be done without executing"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --service all --branch main"
    echo "  $0 --service eth-api --branch feature/new-api --tag v1.2.3"
    echo "  $0 --service eth-booking --no-build --tag latest"
}

# Parse command line arguments
SERVICE="all"
BRANCH="main"
TAG=""
NO_BUILD=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--service)
            SERVICE="$2"
            shift 2
            ;;
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

# Validate service parameter
if [[ "$SERVICE" != "all" && "$SERVICE" != "eth-api" && "$SERVICE" != "eth-booking" ]]; then
    log_error "Invalid service. Must be one of: all, eth-api, eth-booking"
    exit 1
fi

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if AWS CLI is installed and configured
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed or not in PATH"
        exit 1
    fi
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker is not running or not accessible"
        exit 1
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
    
    log_success "All prerequisites satisfied"
}

# Function to authenticate with ECR
ecr_login() {
    log_info "Authenticating with ECR..."
    if [[ "$DRY_RUN" == "false" ]]; then
        aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_BASE_URL
        log_success "ECR authentication successful"
    else
        log_info "[DRY RUN] Would authenticate with ECR"
    fi
}

# Function to create ECR repositories if they don't exist
create_ecr_repos() {
    log_info "Ensuring ECR repositories exist..."
    
    for service in "${!SERVICES[@]}"; do
        local repo_name="${SERVICES[$service]}"
        
        if [[ "$DRY_RUN" == "false" ]]; then
            if ! aws ecr describe-repositories --repository-names $repo_name --region $AWS_REGION &> /dev/null; then
                log_info "Creating ECR repository: $repo_name"
                aws ecr create-repository --repository-name $repo_name --region $AWS_REGION
                log_success "Created ECR repository: $repo_name"
            else
                log_info "ECR repository already exists: $repo_name"
            fi
        else
            log_info "[DRY RUN] Would ensure ECR repository exists: $repo_name"
        fi
    done
}

# Function to pull latest code
pull_code() {
    local service=$1
    local service_dir="$SCRIPT_DIR/$service"
    
    log_info "Pulling latest code for $service from branch $BRANCH..."
    
    if [[ ! -d "$service_dir" ]]; then
        log_error "Service directory not found: $service_dir"
        return 1
    fi
    
    cd "$service_dir"
    
    if [[ "$DRY_RUN" == "false" ]]; then
        # Check if it's a git repository
        if [[ -d ".git" ]]; then
            # Stash any local changes
            git stash push -m "Auto-stash before deployment $(date)"
            
            # Fetch latest changes
            git fetch origin
            
            # Switch to the specified branch
            if git branch -r | grep -q "origin/$BRANCH"; then
                git checkout $BRANCH
                git pull origin $BRANCH
                log_success "Updated $service to latest $BRANCH"
            else
                log_error "Branch $BRANCH not found for $service"
                return 1
            fi
        else
            log_warning "$service is not a git repository, skipping git pull"
        fi
    else
        log_info "[DRY RUN] Would pull latest code for $service from branch $BRANCH"
    fi
    
    cd "$SCRIPT_DIR"
}

# Function to build and push Docker image
build_and_push() {
    local service=$1
    local service_dir="$SCRIPT_DIR/$service"
    local repo_name="${SERVICES[$service]}"
    local image_uri="$ECR_BASE_URL/$repo_name:$TAG"
    local latest_uri="$ECR_BASE_URL/$repo_name:latest"
    
    log_info "Building and pushing Docker image for $service..."
    
    if [[ ! -d "$service_dir" ]]; then
        log_error "Service directory not found: $service_dir"
        return 1
    fi
    
    if [[ ! -f "$service_dir/Dockerfile" ]]; then
        log_error "Dockerfile not found in $service_dir"
        return 1
    fi
    
    cd "$service_dir"
    
    if [[ "$DRY_RUN" == "false" ]]; then
        # Build the Docker image
        log_info "Building Docker image: $image_uri"
        docker build -t "$image_uri" -t "$latest_uri" .
        
        # Push both tagged and latest images
        log_info "Pushing Docker image: $image_uri"
        docker push "$image_uri"
        
        log_info "Pushing Docker image: $latest_uri"
        docker push "$latest_uri"
        
        log_success "Successfully built and pushed $service image"
    else
        log_info "[DRY RUN] Would build and push Docker image: $image_uri"
    fi
    
    cd "$SCRIPT_DIR"
}

# Function to update Kubernetes deployment
update_k8s_deployment() {
    local service=$1
    local repo_name="${SERVICES[$service]}"
    local image_uri="$ECR_BASE_URL/$repo_name:$TAG"
    
    local deployment_file=""
    case $service in
        "eth-api")
            deployment_file="$K8S_DIR/api-deployment.yaml"
            ;;
        "eth-booking")
            deployment_file="$K8S_DIR/booking-deployment.yaml"
            ;;
    esac
    
    if [[ ! -f "$deployment_file" ]]; then
        log_error "Deployment file not found: $deployment_file"
        return 1
    fi
    
    log_info "Updating Kubernetes deployment for $service..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        # Update the image in the deployment
        kubectl set image deployment/${SERVICES[$service]} ${service/eth-/}=$image_uri -n aerticket
        
        # Wait for rollout to complete
        log_info "Waiting for rollout to complete..."
        kubectl rollout status deployment/${SERVICES[$service]} -n aerticket --timeout=300s
        
        log_success "Successfully updated deployment for $service"
    else
        log_info "[DRY RUN] Would update deployment ${SERVICES[$service]} with image: $image_uri"
    fi
}

# Function to restart deployment (force refresh)
restart_deployment() {
    local service=$1
    
    log_info "Restarting deployment for $service..."
    
    if [[ "$DRY_RUN" == "false" ]]; then
        kubectl rollout restart deployment/${SERVICES[$service]} -n aerticket
        kubectl rollout status deployment/${SERVICES[$service]} -n aerticket --timeout=300s
        log_success "Successfully restarted deployment for $service"
    else
        log_info "[DRY RUN] Would restart deployment: ${SERVICES[$service]}"
    fi
}

# Function to deploy a single service
deploy_service() {
    local service=$1
    
    log_info "Starting deployment for $service (branch: $BRANCH, tag: $TAG)"
    
    # Pull latest code
    pull_code "$service"
    
    # Build and push if not skipped
    if [[ "$NO_BUILD" == "false" ]]; then
        build_and_push "$service"
        # Update deployment with new image
        update_k8s_deployment "$service"
    else
        log_info "Skipping build for $service"
        # Just restart the deployment to refresh
        restart_deployment "$service"
    fi
    
    log_success "Deployment completed for $service"
}

# Function to get deployment status
show_deployment_status() {
    log_info "Current deployment status:"
    
    for service in "${!SERVICES[@]}"; do
        echo ""
        echo "=== ${SERVICES[$service]} ==="
        if kubectl get deployment "${SERVICES[$service]}" -n aerticket &> /dev/null; then
            kubectl get deployment "${SERVICES[$service]}" -n aerticket
            kubectl get pods -l app="${SERVICES[$service]}" -n aerticket
        else
            log_warning "Deployment ${SERVICES[$service]} not found"
        fi
    done
}

# Main execution
main() {
    log_info "Starting deployment process..."
    log_info "Service: $SERVICE"
    log_info "Branch: $BRANCH" 
    log_info "Tag: $TAG"
    log_info "No Build: $NO_BUILD"
    log_info "Dry Run: $DRY_RUN"
    
    # Check prerequisites
    check_prerequisites
    
    # Authenticate with ECR
    ecr_login
    
    # Create ECR repositories
    create_ecr_repos
    
    # Deploy services
    if [[ "$SERVICE" == "all" ]]; then
        for service in "${!SERVICES[@]}"; do
            deploy_service "$service"
        done
    else
        deploy_service "$SERVICE"
    fi
    
    # Show final status
    show_deployment_status
    
    log_success "Deployment process completed successfully!"
}

# Execute main function
main "$@"
