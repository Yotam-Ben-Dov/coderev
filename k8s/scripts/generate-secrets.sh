#!/bin/bash
# Generate Kubernetes secrets from .env file

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
ENV_FILE="${PROJECT_ROOT}/.env"
OVERLAY="${1:-local}"
SECRETS_FILE="${SCRIPT_DIR}/../overlays/${OVERLAY}/secrets.env"

echo "🔐 Generating secrets for overlay: ${OVERLAY}"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "❌ .env file not found at ${ENV_FILE}"
    exit 1
fi

# Create secrets.env with Kubernetes-appropriate values
cat > "${SECRETS_FILE}" << 'EOF'
# Auto-generated from .env - DO NOT COMMIT THIS FILE
# Generated at: $(date)
EOF

# Extract relevant secrets from .env
{
    # Database URL - adjust for Kubernetes service names
    echo "DATABASE_URL=postgresql+asyncpg://coderev:coderev@postgres:5432/coderev"
    
    # Redis URL - adjust for Kubernetes service names  
    echo "REDIS_URL=redis://redis:6379/0"
    
    # GitHub token
    grep -E "^GITHUB_TOKEN=" "${ENV_FILE}" || echo "GITHUB_TOKEN="
    
    # Anthropic API key
    grep -E "^ANTHROPIC_API_KEY=" "${ENV_FILE}" || echo "ANTHROPIC_API_KEY="
    
    # OpenAI API key
    grep -E "^OPENAI_API_KEY=" "${ENV_FILE}" || echo "OPENAI_API_KEY="
    
    # Webhook secret (optional)
    grep -E "^GITHUB_WEBHOOK_SECRET=" "${ENV_FILE}" || echo "GITHUB_WEBHOOK_SECRET="
    
} >> "${SECRETS_FILE}"

echo "✅ Secrets written to: ${SECRETS_FILE}"
echo ""
echo "⚠️  IMPORTANT: ${SECRETS_FILE} is gitignored and should never be committed!"

# Ensure it's gitignored
GITIGNORE="${PROJECT_ROOT}/.gitignore"
if ! grep -q "secrets.env" "${GITIGNORE}" 2>/dev/null; then
    echo "" >> "${GITIGNORE}"
    echo "# Kubernetes secrets" >> "${GITIGNORE}"
    echo "k8s/overlays/*/secrets.env" >> "${GITIGNORE}"
    echo "Added secrets.env to .gitignore"
fi