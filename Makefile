PYTHON ?= python3.12
VENV   := .venv
BIN    := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help setup lint format test doctor doctor-deep docs check collect bronze bronze-snowflake compare dbt-build dbt-build-snowflake up down index api demo eval status

help: ## Show available commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  make %-12s %s\n", $$1, $$2}'

setup: ## Create the virtual environment, install dependencies and git hooks
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev,transform]"
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

collect: ## Collect today's postings from approved sources (Greenhouse)
	$(BIN)/jobmarket collect greenhouse

bronze: ## Load raw files into the Bronze layer, then show totals
	$(BIN)/jobmarket bronze load
	$(BIN)/jobmarket bronze status

# dbt reads its settings from environment variables; load them from .env first.
DBT = set -a && . ./.env && set +a && cd transform && ../$(BIN)/dbt

bronze-snowflake: ## Load raw files into the Bronze layer in Snowflake (as JMA_INGEST)
	$(BIN)/jobmarket bronze load --target snowflake

dbt-build: ## Build and test Silver/Gold models on local DuckDB
	$(DBT) build --profiles-dir . --target dev

dbt-build-snowflake: ## Build and test Silver/Gold models on Snowflake
	$(DBT) build --profiles-dir . --target snowflake

compare: ## Check Silver and Gold are identical in DuckDB and Snowflake
	$(BIN)/jobmarket compare

docs: ## Serve the documentation site at http://127.0.0.1:8000
	$(BIN)/mkdocs serve

check: lint test ## Run everything CI runs
	$(BIN)/mkdocs build --strict --quiet

up: ## Start local services (vector database) in Docker
	docker compose up -d --wait vectordb

down: ## Stop local services (data is kept)
	docker compose down

index: ## Build or refresh the retrieval index from Gold
	$(BIN)/jobmarket index build

api: ## Run the API locally on http://localhost:8000 (docs at /docs)
	$(BIN)/uvicorn jobmarket.api.app:app --port 8000 --reload

demo: ## Start every service (vector DB, API, Airflow, Kafka) in Docker
	docker compose up -d --build

eval: ## Run the evaluation set and compare with the accepted run
	$(BIN)/jobmarket eval run --pace 25

status: ## Open the health view in the browser
	@. ./.env && open "http://localhost:8000/status?key=$$API_KEY"
