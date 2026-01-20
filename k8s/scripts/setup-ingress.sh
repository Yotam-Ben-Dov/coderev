#!/bin/bash
# Install NGINX Ingress Controller for Kind

set -euo pipefail

echo "🌐 Installing NGINX Ingress Controller..."

# Apply the NGINX Ingress manifest for Kind
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

echo "⏳ Waiting for Ingress controller to be ready..."

# Wait for the ingress controller to be ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

echo "✅ NGINX Ingress Controller is ready!"

# Show ingress controller status
kubectl get pods -n ingress-nginx

echo ""
echo "📋 Ingress is now available at:"
echo "   - http://localhost (via Ingress)"
echo "   - http://coderev.localhost (if you add it to /etc/hosts)"
echo ""
echo "To add coderev.localhost to your hosts file:"
echo "   echo '127.0.0.1 coderev.localhost' | sudo tee -a /etc/hosts"
echo ""