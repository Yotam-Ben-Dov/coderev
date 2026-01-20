#!/bin/bash
# Tear down CodeRev from Kubernetes

set -euo pipefail

NAMESPACE="${NAMESPACE:-coderev}"
DELETE_CLUSTER="${DELETE_CLUSTER:-false}"
CLUSTER_NAME="${CLUSTER_NAME:-coderev}"

echo "🗑️  Tearing down CodeRev..."

# Delete the namespace (this removes all resources)
if kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo "Deleting namespace ${NAMESPACE}..."
    kubectl delete namespace "${NAMESPACE}" --timeout=60s
    echo "✅ Namespace deleted."
else
    echo "Namespace ${NAMESPACE} not found."
fi

# Optionally delete the entire Kind cluster
if [[ "${DELETE_CLUSTER}" == "true" ]]; then
    echo "🗑️  Deleting Kind cluster: ${CLUSTER_NAME}"
    kind delete cluster --name "${CLUSTER_NAME}"
    echo "✅ Cluster deleted."
fi

echo ""
echo "✅ Teardown complete!"