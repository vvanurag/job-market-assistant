PYTHON ?= python3.12
VENV   := .venv
BIN    := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help setup lint format test doctor doctor-deep docs check

help: ## Show available commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  make %-12s %s\n", $$1, $$2}'

setup: ## Create the virtual environment, install dependencies and git hooks
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"
	$(BIN)/pre-commit install
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example; fill in your values.")

lint: ## Check code style (no changes made)
	$(BIN)/ruff check src tests
	$(BIN)/ruff format --check src tests

format: ## Fix code style automatically
	$(BIN)/ruff check --fix src tests
	$(BIN)/ruff format src tests

test: ## Run the test suite
	$(BIN)/pytest

doctor: ## Check the local environment against the Phase 0 exit criteria
	$(BIN)/jobmarket doctor

doctor-deep: ## Like doctor, but also calls each model and API
	$(BIN)/jobmarket doctor --deep

docs: ## Serve the documentation site at http://127.0.0.1:8000
	$(BIN)/mkdocs serve

check: lint test ## Run everything CI runs
	$(BIN)/mkdocs build --strict --quiet
