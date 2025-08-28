#!/bin/bash

# Quick deployment script for common scenarios
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Quick Deployment Menu${NC}"
echo "================================"
echo "1. Deploy both services (main branch)"
echo "2. Deploy eth-api only (main branch)"
echo "3. Deploy eth-booking only (main branch)"
echo "4. Refresh deployments (no rebuild)"
echo "5. Custom deployment"
echo "6. Show current status"
echo "7. Exit"
echo ""

read -p "Choose an option (1-7): " choice

case $choice in
    1)
        echo -e "${GREEN}Deploying both services from main branch...${NC}"
        $SCRIPT_DIR/deploy.sh --service all --branch main
        ;;
    2)
        echo -e "${GREEN}Deploying eth-api from main branch...${NC}"
        $SCRIPT_DIR/deploy.sh --service eth-api --branch main
        ;;
    3)
        echo -e "${GREEN}Deploying eth-booking from main branch...${NC}"
        $SCRIPT_DIR/deploy.sh --service eth-booking --branch main
        ;;
    4)
        echo -e "${GREEN}Refreshing deployments (no rebuild)...${NC}"
        $SCRIPT_DIR/deploy.sh --service all --no-build
        ;;
    5)
        echo -e "${YELLOW}Custom deployment:${NC}"
        echo "Available services: eth-api, eth-booking, all"
        read -p "Service: " service
        read -p "Branch (default: main): " branch
        read -p "Tag (default: auto-generated): " tag
        
        # Set defaults
        branch=${branch:-main}
        
        cmd="$SCRIPT_DIR/deploy.sh --service $service --branch $branch"
        if [[ ! -z "$tag" ]]; then
            cmd="$cmd --tag $tag"
        fi
        
        echo -e "${GREEN}Running: $cmd${NC}"
        $cmd
        ;;
    6)
        echo -e "${GREEN}Showing current deployment status...${NC}"
        kubectl get deployments -n aerticket
        echo ""
        kubectl get pods -n aerticket
        ;;
    7)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac
