#!/bin/bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-coderev}"

echo "Building Docker images..."

# Build images
docker build -t coderev-api:local -f docker/Dockerfile.api .
docker build -t coderev-worker:local -f docker/Dockerfile.worker .

echo "Loading images into Kind cluster..."

# Check if cluster exists
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Kind cluster ${CLUSTER_NAME} not found!"
    echo "Run: make k8s-setup"
    exit 1
fi

# Load images
kind load docker-image coderev-api:local --name "${CLUSTER_NAME}"
kind load docker-image coderev-worker:local --name "${CLUSTER_NAME}"

echo "Images loaded successfully!"