#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "${SCRIPT_DIR}")"
OVERLAY="${1:-local}"
SECRETS_FILE="${K8S_DIR}/overlays/${OVERLAY}/secrets.env"

echo "Deploying CodeRev with overlay: ${OVERLAY}"

# Check if cluster exists
if ! kubectl cluster-info &> /dev/null; then
    echo "No Kubernetes cluster found. Run: make k8s-setup"
    exit 1
fi

# Check if secrets file exists
if [[ ! -f "${SECRETS_FILE}" ]]; then
    echo "Secrets file not found: ${SECRETS_FILE}"
    echo "Run: ./k8s/scripts/generate-secrets.sh ${OVERLAY}"
    exit 1
fi

# Apply the configuration
echo "Applying Kubernetes manifests..."
kubectl apply -k "${K8S_DIR}/overlays/${OVERLAY}"

# Wait for database and redis first
echo "Waiting for database..."
kubectl rollout status deployment/postgres -n coderev --timeout=120s || true

echo "Waiting for redis..."
kubectl rollout status deployment/redis -n coderev --timeout=60s || true

# Wait for application
echo "Waiting for API..."
kubectl rollout status deployment/coderev-api -n coderev --timeout=180s

echo "Waiting for worker..."
kubectl rollout status deployment/coderev-worker -n coderev --timeout=180s

echo ""
echo "Deployment complete!"
echo ""
kubectl get all -n coderev
echo ""
echo "Access the application:"
echo "  http://localhost/coderev/health"
echo "  http://coderev.localhost/health (add to /etc/hosts first)"