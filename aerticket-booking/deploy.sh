#!/bin/bash

# Simple wrapper for eth-booking deployment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 ETH-BOOKING Quick Deploy"
echo "=========================="

# If no arguments provided, run with default branch
if [[ $# -eq 0 ]]; then
    echo "Deploying eth-booking from main branch..."
    $SCRIPT_DIR/deploy-booking.sh --branch main
else
    # Pass all arguments to the main script
    $SCRIPT_DIR/deploy-booking.sh "$@"
fi
