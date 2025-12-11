# CodeRev

AI-powered code review assistant that provides intelligent feedback on pull requests.

## Features

- 🤖 Automated code review using LLMs (Claude, GPT-4, local models)
- 🔍 Context-aware reviews using RAG
- 💬 Inline comments on specific lines
- 📊 Review summaries with actionable feedback
- 🏠 Local LLM support for privacy and cost savings

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Poetry
- GitHub Personal Access Token

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/coderev.git
   cd coderev

2. **Install dependencies**

bash
make dev
3. **Configure environment**

bash
cp .env.example .env
# Edit .env with your tokens and settings
4. **Start services**

bash
make docker-up
5. **Verify it's running**

bash
curl http://localhost:8000/health

### Development
bash
# Run locally (without Docker)
make run

# Run tests
make test

# Lint and format
make lint
make format
Architecture
text
┌─────────────────────────────────────────────┐
│              GitHub                          │
│  PR Events ──────────────────► Comments     │
└──────┬────────────────────────────▲─────────┘
       │                            │
       ▼                            │
┌─────────────────────────────────────────────┐
│              CodeRev API                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────────┐  │
│  │ Webhook │  │ Review  │  │   GitHub    │  │
│  │ Handler │  │ Pipeline│  │   Client    │  │
│  └────┬────┘  └────┬────┘  └──────▲──────┘  │
│       │            │              │         │
│       ▼            ▼              │         │
│  ┌─────────────────────────────────────┐    │
│  │           LLM Router                │    │
│  │  Claude │ GPT-4 │ Ollama (local)    │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
Configuration
Variable	Description	Required
GITHUB_TOKEN	GitHub PAT with repo scope	Yes
ANTHROPIC_API_KEY	Anthropic API key	If using Claude
OPENAI_API_KEY	OpenAI API key	If using GPT-4
OLLAMA_HOST	Ollama server URL	If using local LLM
License
MIT