# Deployment Scripts for eth-api and eth-booking

This directory contains comprehensive deployment scripts for the eth-api and eth-booking services.

## Files

- **`deploy.sh`** - Full-featured deployment script with all options
- **`quick-deploy.sh`** - Interactive menu for common deployment scenarios
- **`DEPLOYMENT.md`** - This documentation file

## Prerequisites

Ensure you have the following tools installed and configured:

- **AWS CLI** - Configured with appropriate credentials and region
- **Docker** - Running and accessible
- **kubectl** - Configured to connect to your EKS cluster
- **Git** - For pulling latest code from repositories

## Quick Start

### Interactive Deployment (Recommended for beginners)

```bash
./quick-deploy.sh
```

This will show a menu with common deployment options.

### Command Line Deployment

Deploy both services from main branch:
```bash
./deploy.sh --service all --branch main
```

Deploy specific service:
```bash
./deploy.sh --service eth-api --branch main
./deploy.sh --service eth-booking --branch feature/new-booking
```

## Script Options

### deploy.sh Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--service` | `-s` | Service to deploy (`eth-api`, `eth-booking`, `all`) | `all` |
| `--branch` | `-b` | Git branch to deploy | `main` |
| `--tag` | `-t` | Docker image tag | Current timestamp |
| `--no-build` | `-n` | Skip build and use existing images | `false` |
| `--dry-run` | `-d` | Show what would be done without executing | `false` |
| `--help` | `-h` | Show help message | - |

### Usage Examples

1. **Deploy both services from main branch:**
   ```bash
   ./deploy.sh --service all --branch main
   ```

2. **Deploy specific service with custom tag:**
   ```bash
   ./deploy.sh --service eth-api --branch feature/new-api --tag v1.2.3
   ```

3. **Refresh deployment without rebuilding:**
   ```bash
   ./deploy.sh --service eth-booking --no-build
   ```

4. **Dry run to see what would happen:**
   ```bash
   ./deploy.sh --service all --branch main --dry-run
   ```

## What the Script Does

1. **Prerequisites Check** - Verifies AWS CLI, Docker, and kubectl are available
2. **ECR Authentication** - Logs into ECR registry
3. **Repository Creation** - Creates ECR repositories if they don't exist
4. **Code Pull** - Pulls latest code from specified Git branch
5. **Docker Build** - Builds Docker images with proper tags
6. **ECR Push** - Pushes images to ECR registry
7. **Kubernetes Update** - Updates deployment with new image
8. **Rollout Status** - Waits for successful deployment
9. **Status Display** - Shows final deployment status

## Configuration

### Service Mapping

The script maps service names to their respective configurations:

- `eth-api` → `aerticket-api` (ECR repo and K8s deployment)
- `eth-booking` → `aerticket-booking` (ECR repo and K8s deployment)

### AWS Configuration

- **Region:** `ap-south-1`
- **Account ID:** `722955677910`
- **ECR Base URL:** `722955677910.dkr.ecr.ap-south-1.amazonaws.com`

### Kubernetes Configuration

- **Namespace:** `aerticket`
- **Deployment Files:** Located in `/Users/riz/aws-eks-infrastructure/k8s/aerticket/`

## Troubleshooting

### Common Issues

1. **Docker not running:**
   ```bash
   # Start Docker Desktop or Docker daemon
   ```

2. **AWS credentials not configured:**
   ```bash
   aws configure
   # or
   export AWS_PROFILE=your-profile
   ```

3. **kubectl not configured:**
   ```bash
   aws eks update-kubeconfig --region ap-south-1 --name your-cluster-name
   ```

4. **ECR login issues:**
   ```bash
   aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin 722955677910.dkr.ecr.ap-south-1.amazonaws.com
   ```

### Checking Deployment Status

```bash
# Check deployments
kubectl get deployments -n aerticket

# Check pods
kubectl get pods -n aerticket

# Check logs
kubectl logs -f deployment/aerticket-api -n aerticket
kubectl logs -f deployment/aerticket-booking -n aerticket

# Check deployment history
kubectl rollout history deployment/aerticket-api -n aerticket
```

### Rolling Back

If you need to rollback to a previous version:

```bash
# Rollback to previous version
kubectl rollout undo deployment/aerticket-api -n aerticket
kubectl rollout undo deployment/aerticket-booking -n aerticket

# Rollback to specific revision
kubectl rollout undo deployment/aerticket-api --to-revision=2 -n aerticket
```

## CI/CD Integration

The deployment script can be easily integrated into CI/CD pipelines:

### GitHub Actions Example

```yaml
name: Deploy to EKS
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-south-1
      - name: Deploy to EKS
        run: |
          ./deploy.sh --service all --branch main --tag ${{ github.sha }}
```

### CircleCI Example

```yaml
version: 2.1
jobs:
  deploy:
    docker:
      - image: cimg/base:stable
    steps:
      - checkout
      - setup_remote_docker
      - run:
          name: Deploy to EKS
          command: |
            ./deploy.sh --service all --branch main --tag $CIRCLE_SHA1
```

## Security Notes

- The script handles ECR authentication automatically
- It uses timestamp-based tags by default for image versioning
- Secrets are managed through Kubernetes secrets (not exposed in logs)
- The script stashes local changes before pulling latest code

## Support

For issues or questions:
1. Check the logs using the troubleshooting commands above
2. Use `--dry-run` to see what the script would do
3. Review the deployment status using `kubectl` commands
4. Check ECR repositories in AWS Console
