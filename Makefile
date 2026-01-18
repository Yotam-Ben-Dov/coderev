.PHONY: help install run worker test lint format clean db-upgrade db-migrate docker-up docker-down logs metrics

# Default target
help:
	@echo "CodeRev Development Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install     - Install dependencies"
	@echo "  make run         - Run API locally"
	@echo "  make worker      - Run Celery worker locally"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run ruff linter"
	@echo "  make typecheck   - Run mypy type checker"
	@echo "  make format      - Format code"
	@echo ""
	@echo "Database:"
	@echo "  make db-upgrade  - Run database migrations"
	@echo "  make db-migrate  - Create new migration (use msg='description')"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up   - Start all services"
	@echo "  make docker-down - Stop all services"
	@echo "  make docker-build - Rebuild containers"
	@echo "  make logs        - View all logs"
	@echo ""
	@echo "Observability:"
	@echo "  make metrics     - View metrics endpoint"
	@echo "  make prometheus  - Open Prometheus UI"
	@echo "  make grafana     - Open Grafana UI"

# =============================================================================
# Development
# =============================================================================

install:
	poetry install

run:
	poetry run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

worker:
	poetry run celery -A src.worker.celery_app worker --loglevel=info --queues=default,reviews

test:
	poetry run pytest

test-cov:
	poetry run pytest --cov=src --cov-report=html --cov-report=term-missing

lint:
	poetry run ruff check src tests --fix
	poetry run ruff format --check src tests

format:
	poetry run ruff check --fix src tests
	poetry run ruff format src tests

# Separate target for type checking (has known issues in pre-existing code)
typecheck:
	poetry run mypy src --ignore-missing-imports

# Strict type check (for CI or when fixing type errors)
typecheck-strict:
	poetry run mypy src

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

# =============================================================================
# Database
# =============================================================================

db-upgrade:
	poetry run alembic upgrade head

db-migrate:
	@if [ -z "$(msg)" ]; then \
		echo "Error: Please provide a migration message with msg='your message'"; \
		exit 1; \
	fi
	poetry run alembic revision --autogenerate -m "$(msg)"

db-downgrade:
	poetry run alembic downgrade -1

db-history:
	poetry run alembic history

# =============================================================================
# Docker
# =============================================================================

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-rebuild:
	docker-compose build --no-cache

docker-logs:
	docker-compose logs -f

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-worker:
	docker-compose logs -f worker

# =============================================================================
# Observability
# =============================================================================

metrics:
	@echo "Fetching metrics from http://localhost:8000/metrics"
	@curl -s http://localhost:8000/metrics | head -100

prometheus:
	@echo "Opening Prometheus at http://localhost:9090"
	@which xdg-open > /dev/null && xdg-open http://localhost:9090 || echo "Visit http://localhost:9090"

grafana:
	@echo "Opening Grafana at http://localhost:3000 (admin/coderev)"
	@which xdg-open > /dev/null && xdg-open http://localhost:3000 || echo "Visit http://localhost:3000"

# =============================================================================
# CI/CD Helpers
# =============================================================================

ci-lint:
	poetry run ruff check src tests
	poetry run ruff format --check src tests

ci-test:
	poetry run pytest --tb=short -q

ci-all: ci-lint ci-test