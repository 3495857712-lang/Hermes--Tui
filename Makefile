.PHONY: install dev run test test-cov lint format typecheck check clean dist help

help: ## Show this help message
	@echo "Hermes TUI - Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install the package in editable mode with dev dependencies
	@echo "==> Installing Hermes TUI in editable mode..."
	pip install -e ".[dev]"

dev: install ## Set up development environment (install + pre-commit hooks)
	@echo "==> Installing pre-commit hooks..."
	pre-commit install
	@echo "==> Development environment ready!"

run: ## Run Hermes TUI
	@echo "==> Starting Hermes TUI..."
	hermes-tui

test: ## Run the test suite
	@echo "==> Running tests..."
	pytest tests/ -v

test-cov: ## Run tests with coverage report
	@echo "==> Running tests with coverage..."
	pytest tests/ -v --cov=src/hermes_tui --cov-report=term-missing --cov-report=html

lint: ## Run Ruff linter
	@echo "==> Linting with Ruff..."
	ruff check src tests

format: ## Format code with Ruff
	@echo "==> Formatting with Ruff..."
	ruff format src tests

typecheck: ## Run Mypy type checking
	@echo "==> Type checking with Mypy..."
	mypy src

check: lint typecheck test ## Run all checks (lint, typecheck, tests)
	@echo "==> All checks passed!"

clean: ## Clean build artifacts and cache directories
	@echo "==> Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info src/*.egg-info htmlcov/ .coverage 2>/dev/null || true
	@echo "==> Clean complete."

dist: clean ## Build source distribution and wheel
	@echo "==> Building distribution packages..."
	python -m build
	@echo "==> Distribution packages built in dist/"
