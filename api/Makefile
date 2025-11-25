.PHONY: install
install: ## Install the poetry environment and install the pre-commit hooks
	@echo "🚀 Creating virtual environment using pyenv and poetry"
	@poetry install
	@poetry run pre-commit install
	@poetry shell

.PHONY: check
check: ## Run code quality tools.
	@echo "🚀 Checking Poetry lock file consistency with 'pyproject.toml': Running poetry check --lock"
	@poetry check --lock
	@echo "🚀 Linting code: Running pre-commit"
	@poetry run pre-commit run -a
	@echo "🚀 Static type checking: Running pyright"
	@poetry run pyright
	@echo "🚀 Checking for obsolete dependencies: Running deptry"
	@poetry run deptry .

.PHONY: dev
dev: ## Run the api in docker compose
	@touch .env.local
	@echo "🚀 Running api: running docker compose up"
	@docker compose up -d --remove-orphans
	@echo "🚀 Starting to tail api logs"
	@docker compose logs -f api

.PHONY: debug
debug: ## Run the api in docker compose with a debugger exposed
	@touch .env.local
	@echo "🚀 Running api (with debugger): running docker compose up"
	@docker compose -f docker-compose.yml -f docker-compose.debug.yml up -d --remove-orphans
	@echo "🚀 Starting to tail api (with debugger) logs"
	@echo "❗❗ Make sure to attach a debugger to port 5678 and 5679 ❗❗"
	@docker compose -f docker-compose.yml -f docker-compose.debug.yml logs -f api

.PHONY: down
down: ## Stop the api in docker compose
	@echo "🚀 Stopping api: running docker compose down"
	@docker compose down

.PHONY: openapi
openapi: ## Create openapi.json file from the FastAPI app
	@echo "🚀 Run generation script"
	@poetry run dotenv -f .env.docker-compose run python -c "\
	from src import app; \
	from src.app.openapi import openapi_generator; \
	openapi_generator(app) \
	"

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
