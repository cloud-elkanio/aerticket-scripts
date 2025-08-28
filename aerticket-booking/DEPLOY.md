# ETH-BOOKING Deployment Guide

This directory contains deployment scripts specifically for the **eth-booking** service.

## 🚀 Quick Start

### Simplest Usage
```bash
# Deploy from main branch with auto-generated tag
./deploy.sh
```

### Advanced Usage
```bash
# Full deployment script with all options
./deploy-booking.sh [OPTIONS]
```

## 📁 Files

- **`deploy.sh`** - Simple wrapper script (just run this!)
- **`deploy-booking.sh`** - Full-featured deployment script
- **`DEPLOY.md`** - This documentation

## 🛠️ Available Options

| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--branch` | `-b` | Git branch to deploy | `--branch feature/new-booking` |
| `--tag` | `-t` | Docker image tag | `--tag v1.2.3` |
| `--no-build` | `-n` | Skip build, use existing images | `--no-build` |
| `--restart-only` | `-r` | Only restart deployment | `--restart-only` |
| `--status` | `-s` | Show deployment status | `--status` |
| `--dry-run` | `-d` | Preview actions | `--dry-run` |
| `--help` | `-h` | Show help | `--help` |

## 📋 Common Use Cases

### 1. Deploy from main branch
```bash
./deploy.sh
# or
./deploy-booking.sh --branch main
```

### 2. Deploy from feature branch
```bash
./deploy-booking.sh --branch feature/payment-gateway
```

### 3. Deploy with specific tag
```bash
./deploy-booking.sh --branch main --tag v2.1.0
```

### 4. Quick restart (no build)
```bash
./deploy-booking.sh --restart-only
```

### 5. Check deployment status
```bash
./deploy-booking.sh --status
```

### 6. Refresh with existing image
```bash
./deploy-booking.sh --no-build
```

## 🔍 What It Does

1. ✅ **Code Pull** - Pulls latest code from specified Git branch
2. ✅ **Docker Build** - Builds Docker image using local Dockerfile
3. ✅ **ECR Push** - Pushes to `722955677910.dkr.ecr.ap-south-1.amazonaws.com/aerticket-booking`
4. ✅ **K8s Update** - Updates `aerticket-booking` deployment in `aerticket` namespace
5. ✅ **Rollout Monitor** - Waits for successful deployment
6. ✅ **Status & Logs** - Shows deployment status and recent logs

## 📊 Service Details

- **Service Name:** `eth-booking`
- **ECR Repository:** `aerticket-booking`
- **K8s Deployment:** `aerticket-booking`
- **K8s Namespace:** `aerticket`
- **Container Name:** `booking`
- **Health Check:** `/booking/health/`

## 🔧 Prerequisites

- **Docker** - Must be running for builds
- **AWS CLI** - Configured with ECR access
- **kubectl** - Connected to your EKS cluster
- **Git** - For pulling code updates

## 🎯 Examples

```bash
# Standard deployment
./deploy.sh

# Deploy specific feature
./deploy-booking.sh --branch feature/seat-selection --tag seat-v1

# Emergency restart
./deploy-booking.sh --restart-only

# Preview changes
./deploy-booking.sh --branch main --dry-run

# Check current status
./deploy-booking.sh --status
```

## 🚨 Troubleshooting

### Common Issues

1. **"Dockerfile not found"** - Make sure you're in the eth-booking directory
2. **"Docker not running"** - Start Docker Desktop
3. **"kubectl not configured"** - Run `aws eks update-kubeconfig --region ap-south-1 --name your-cluster`
4. **"ECR login failed"** - Check AWS credentials with `aws sts get-caller-identity`

### Checking Logs

```bash
# Deployment logs
kubectl logs -f deployment/aerticket-booking -n aerticket

# Pod status
kubectl get pods -n aerticket -l app=aerticket-booking

# Recent events
kubectl get events -n aerticket --sort-by=.metadata.creationTimestamp
```

### Rolling Back

```bash
# Rollback to previous version
kubectl rollout undo deployment/aerticket-booking -n aerticket

# Check rollout history
kubectl rollout history deployment/aerticket-booking -n aerticket
```

## 🔗 Service Dependencies

**eth-booking** depends on **eth-api** for core functionality. The deployment configuration includes:
- **API_BASE_URL:** `http://aerticket-api.aerticket.svc.cluster.local`

Make sure eth-api is deployed and healthy before deploying eth-booking.

## 🎨 Output Example

```
=== ETH-BOOKING Deployment Script ===
[INFO] Branch: main
[INFO] Tag: 20250828_083045
[INFO] Checking prerequisites for eth-booking deployment...
[SUCCESS] All prerequisites satisfied
[INFO] Authenticating with ECR...
[SUCCESS] ECR authentication successful
[INFO] Building Docker image...
[INFO] Pushing Docker image: 722955677910.dkr.ecr.ap-south-1.amazonaws.com/aerticket-booking:20250828_083045
[SUCCESS] Successfully built and pushed eth-booking image
[INFO] Setting new image: 722955677910.dkr.ecr.ap-south-1.amazonaws.com/aerticket-booking:20250828_083045
[INFO] Waiting for rollout to complete...
deployment "aerticket-booking" successfully rolled out
[SUCCESS] ETH-BOOKING deployment process completed successfully!
```

---

**💡 Tip:** For the quickest deployment, just run `./deploy.sh` from this directory!
