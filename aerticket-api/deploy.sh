#!/bin/bash

# Simple wrapper for eth-api deployment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 ETH-API Quick Deploy"
echo "======================"

# If no arguments provided, run with default branch
if [[ $# -eq 0 ]]; then
    echo "Deploying eth-api from main branch..."
    $SCRIPT_DIR/deploy-api.sh --branch main
else
    # Pass all arguments to the main script
    $SCRIPT_DIR/deploy-api.sh "$@"
fi
