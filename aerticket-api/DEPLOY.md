# ETH-API Deployment Guide

This directory contains deployment scripts specifically for the **eth-api** service.

## 🚀 Quick Start

### Simplest Usage
```bash
# Deploy from main branch with auto-generated tag
./deploy.sh
```

### Advanced Usage
```bash
# Full deployment script with all options
./deploy-api.sh [OPTIONS]
```

## 📁 Files

- **`deploy.sh`** - Simple wrapper script (just run this!)
- **`deploy-api.sh`** - Full-featured deployment script
- **`DEPLOY.md`** - This documentation

## 🛠️ Available Options

| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--branch` | `-b` | Git branch to deploy | `--branch feature/new-api` |
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
./deploy-api.sh --branch main
```

### 2. Deploy from feature branch
```bash
./deploy-api.sh --branch feature/new-endpoint
```

### 3. Deploy with specific tag
```bash
./deploy-api.sh --branch main --tag v1.0.0
```

### 4. Quick restart (no build)
```bash
./deploy-api.sh --restart-only
```

### 5. Check deployment status
```bash
./deploy-api.sh --status
```

### 6. Refresh with existing image
```bash
./deploy-api.sh --no-build
```

## 🔍 What It Does

1. ✅ **Code Pull** - Pulls latest code from specified Git branch
2. ✅ **Docker Build** - Builds Docker image using local Dockerfile
3. ✅ **ECR Push** - Pushes to `722955677910.dkr.ecr.ap-south-1.amazonaws.com/aerticket-api`
4. ✅ **K8s Update** - Updates `aerticket-api` deployment in `aerticket` namespace
5. ✅ **Rollout Monitor** - Waits for successful deployment
6. ✅ **Status & Logs** - Shows deployment status and recent logs

## 📊 Service Details

- **Service Name:** `eth-api`
- **ECR Repository:** `aerticket-api`
- **K8s Deployment:** `aerticket-api`
- **K8s Namespace:** `aerticket`
- **Container Name:** `api`
- **Health Check:** `/api/health/`

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
./deploy-api.sh --branch feature/user-auth --tag auth-v1

# Emergency restart
./deploy-api.sh --restart-only

# Preview changes
./deploy-api.sh --branch main --dry-run

# Check current status
./deploy-api.sh --status
```

## 🚨 Troubleshooting

### Common Issues

1. **"Dockerfile not found"** - Make sure you're in the eth-api directory
2. **"Docker not running"** - Start Docker Desktop
3. **"kubectl not configured"** - Run `aws eks update-kubeconfig --region ap-south-1 --name your-cluster`
4. **"ECR login failed"** - Check AWS credentials with `aws sts get-caller-identity`

### Checking Logs

```bash
# Deployment logs
kubectl logs -f deployment/aerticket-api -n aerticket

# Pod status
kubectl get pods -n aerticket -l app=aerticket-api

# Recent events
kubectl get events -n aerticket --sort-by=.metadata.creationTimestamp
```

### Rolling Back

```bash
# Rollback to previous version
kubectl rollout undo deployment/aerticket-api -n aerticket

# Check rollout history
kubectl rollout history deployment/aerticket-api -n aerticket
```

## 🎨 Output Example

```
=== ETH-API Deployment Script ===
[INFO] Branch: main
[INFO] Tag: 20250828_083045
[INFO] Checking prerequisites for eth-api deployment...
[SUCCESS] All prerequisites satisfied
[INFO] Authenticating with ECR...
[SUCCESS] ECR authentication successful
[INFO] Building Docker image...
[INFO] Pushing Docker image: 722955677910.dkr.ecr.ap-south-1.amazonaws.com/aerticket-api:20250828_083045
[SUCCESS] Successfully built and pushed eth-api image
[INFO] Setting new image: 722955677910.dkr.ecr.ap-south-1.amazonaws.com/aerticket-api:20250828_083045
[INFO] Waiting for rollout to complete...
deployment "aerticket-api" successfully rolled out
[SUCCESS] ETH-API deployment process completed successfully!
```

---

**💡 Tip:** For the quickest deployment, just run `./deploy.sh` from this directory!
