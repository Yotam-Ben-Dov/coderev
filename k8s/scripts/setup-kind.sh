#!/bin/bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-coderev}"

echo "Setting up Kind cluster: ${CLUSTER_NAME}"

# Check if kind is installed
if ! command -v kind &> /dev/null; then
    echo "Kind is not installed. Install it with:"
    echo "  curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.22.0/kind-linux-amd64"
    echo "  chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind"
    exit 1
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "kubectl is not installed. Install it with:"
    echo "  curl -LO https://dl.k8s.io/release/v1.29.0/bin/linux/amd64/kubectl"
    echo "  chmod +x kubectl && sudo mv kubectl /usr/local/bin/"
    exit 1
fi

# Check if cluster already exists
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Cluster ${CLUSTER_NAME} already exists."
    echo "To delete it, run: kind delete cluster --name ${CLUSTER_NAME}"
    echo "Using existing cluster."
    exit 0
fi

# Create Kind config
cat > /tmp/kind-config.yaml << EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ${CLUSTER_NAME}
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
EOF

# Create the cluster
echo "Creating Kind cluster..."
kind create cluster --config /tmp/kind-config.yaml

# Clean up
rm -f /tmp/kind-config.yaml

# Verify
echo "Cluster created successfully!"
kubectl cluster-info --context "kind-${CLUSTER_NAME}"

echo ""
echo "Next steps:"
echo "  1. Install NGINX Ingress: ./k8s/scripts/setup-ingress.sh"
echo "  2. Generate secrets: ./k8s/scripts/generate-secrets.sh"
echo "  3. Build images: make k8s-build"
echo "  4. Deploy: make k8s-deploy-local"