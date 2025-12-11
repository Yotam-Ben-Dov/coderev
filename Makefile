.PHONY: help install dev lint format test run docker-up docker-down clean

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	poetry install --without dev

dev:  ## Install all dependencies including dev
	poetry install
	poetry run pre-commit install

lint:  ## Run linters
	poetry run ruff check src tests
	poetry run mypy src

format:  ## Format code
	poetry run ruff check --fix src tests
	poetry run ruff format src tests

test:  ## Run tests
	poetry run pytest

test-cov:  ## Run tests with coverage report
	poetry run pytest --cov=src --cov-report=html

run:  ## Run the API locally
	poetry run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

docker-up:  ## Start all services with Docker Compose
	docker-compose up -d

docker-down:  ## Stop all services
	docker-compose down

docker-logs:  ## View logs from all services
	docker-compose logs -f

docker-build:  ## Build Docker images
	docker-compose build

clean:  ## Remove cache and build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist htmlcov .coverage