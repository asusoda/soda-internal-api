.PHONY: help build up down logs shell clean deploy dev prod rollback status health discard-local-changes check ci backup migrate

# Use bash as the shell for all commands
SHELL := /usr/bin/env bash

# Configuration
PROJECT_DIR ?= /var/www/soda-internal-api
BRANCH ?= main
# The commit before this deploy, to find the changed files. cd.yml sets it.
DEPLOY_FROM ?=
# The commit that passed Check. When set, check out this commit instead of origin/$(BRANCH).
DEPLOY_SHA ?=
COMPOSE_CMD := $(shell if command -v podman-compose > /dev/null 2>&1; then echo "podman-compose"; elif docker compose version > /dev/null 2>&1; then echo "docker compose"; else echo "docker-compose"; fi)
CONTAINER_CMD := $(shell if command -v podman > /dev/null 2>&1; then echo "podman"; else echo "docker"; fi)

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

# Default target
help:
	@echo "Available commands:"
	@echo "  make build                  - Build container images"
	@echo "  make up                     - Start services in development mode"
	@echo "  make down                   - Stop and remove containers"
	@echo "  make logs                   - View last 50 lines of container logs"
	@echo "  make logs-follow            - Follow container logs continuously"
	@echo "  make shell                  - Open shell in API container"
	@echo "  make clean                  - Clean up containers and images"
	@echo "  make deploy                 - Deploy to production (pull, build, restart)"
	@echo "  make discard-local-changes  - Discard local git changes (used by CD)"
	@echo "  make dev                    - Start development environment with hot reloading"
	@echo "  make rollback               - Rollback to previous version"
	@echo "  make status                 - Show container status"
	@echo "  make health                 - Check container health"
	@echo "  make check                  - Run lint (auto-fix), format, type check, and tests"
	@echo "  make ci                     - Run the same checks without changing files (what CI runs)"
	@echo "  make backup                 - Copy the SQLite database to data/backups (keeps the last 14)"
	@echo "  make migrate                - Run alembic database migrations"

# Build container images
build:
	@echo -e "$(GREEN)[INFO]$(NC) Building container images with BuildKit..."
	@export COMMIT_HASH=$$(git rev-parse HEAD 2>/dev/null || echo "unknown") && \
		DOCKER_BUILDKIT=1 $(COMPOSE_CMD) build

# Build only API
build-api:
	@echo -e "$(GREEN)[INFO]$(NC) Building API image..."
	@export COMMIT_HASH=$$(git rev-parse HEAD 2>/dev/null || echo "unknown") && \
		DOCKER_BUILDKIT=1 $(COMPOSE_CMD) build api

# Build only web
build-web:
	@echo -e "$(GREEN)[INFO]$(NC) Building web image..."
	@DOCKER_BUILDKIT=1 $(COMPOSE_CMD) build web

# Build only the dashboard
build-dashboard:
	@echo -e "$(GREEN)[INFO]$(NC) Building dashboard image..."
	@DOCKER_BUILDKIT=1 $(COMPOSE_CMD) build dashboard

# Start services in development mode
up:
	@echo -e "$(GREEN)[INFO]$(NC) Starting services..."
	@export COMMIT_HASH=$$(git rev-parse HEAD 2>/dev/null || echo "unknown") && \
		$(COMPOSE_CMD) up -d

# Stop services
down:
	@echo -e "$(GREEN)[INFO]$(NC) Stopping services..."
	@$(COMPOSE_CMD) down

# View logs (batch-friendly, last 50 lines)
logs:
	@$(COMPOSE_CMD) logs --tail=50

# Follow logs (continuous)
logs-follow:
	@$(COMPOSE_CMD) logs -f

# Open shell in API container
shell:
	@$(COMPOSE_CMD) exec api /bin/bash

# Clean up everything
clean:
	@echo -e "$(YELLOW)[WARNING]$(NC) Cleaning up containers and volumes..."
	@$(COMPOSE_CMD) down -v
	@$(CONTAINER_CMD) system prune -f

# Discard local changes (used by CD workflow)
discard-local-changes:
	@printf "$(GREEN)[INFO]$(NC) Discarding any local changes...\n"
	@git reset --hard || (printf "$(RED)[ERROR]$(NC) Failed to reset local changes\n"; exit 1)
	@printf "$(GREEN)[INFO]$(NC) Local changes discarded successfully!\n"

# Deploy to production
# web, dashboard, bot and mcp are created with --requires on the api container. When any image changes,
# all of them are recreated together. podman-compose 1.0.6 recreates a service's dependencies with it, so
# `up -d dashboard` also tries to replace api. It then removes the other containers that require api and
# fails to replace api ("has dependent containers"), which leaves only api and dashboard running.
# soda-mcp (profile mcp) is recreated when it exists. Docker Compose gets --profile mcp; podman-compose
# 1.0.6 has no --profile option and ignores profiles, so it gets the service name only.
# soda-site (profile site) does not require api. When it exists and site/ or docs/ changes, it is rebuilt
# and recreated on its own with --no-deps, after the other containers.
# data/deployed-sha stores the last commit that finished this target.
deploy:
	@set -e; \
		echo -e "$(GREEN)[INFO]$(NC) Starting deployment process..."; \
		if [ "$$(pwd)" != "$(PROJECT_DIR)" ]; then \
			echo -e "$(YELLOW)[WARNING]$(NC) Not in project directory, changing to $(PROJECT_DIR)"; \
			cd "$(PROJECT_DIR)"; \
		fi; \
		RECORDED=""; \
		if [ -f data/deployed-sha ]; then RECORDED=$$(tr -d '[:space:]' < data/deployed-sha); fi; \
		if [[ ! "$$RECORDED" =~ ^[0-9a-f]{40}$$ ]]; then RECORDED=""; fi; \
		OLD_HEAD="$$RECORDED"; \
		if [ -z "$$OLD_HEAD" ]; then OLD_HEAD="$(DEPLOY_FROM)"; fi; \
		if [ -z "$$OLD_HEAD" ]; then OLD_HEAD=$$(git rev-parse HEAD 2>/dev/null || echo ""); fi; \
		echo -e "$(GREEN)[INFO]$(NC) Fetching the deploy commit..."; \
		if [ -n "$(DEPLOY_SHA)" ]; then \
			if [[ ! "$(DEPLOY_SHA)" =~ ^[0-9a-f]{40}$$ ]]; then \
				echo -e "$(RED)[ERROR]$(NC) DEPLOY_SHA is not a 40-character sha."; \
				exit 1; \
			fi; \
			git fetch origin "$(DEPLOY_SHA)" || git fetch origin "$(BRANCH)"; \
			git checkout --detach --force "$(DEPLOY_SHA)"; \
		else \
			git fetch origin "$(BRANCH)"; \
			git checkout "$(BRANCH)"; \
			git reset --hard "origin/$(BRANCH)"; \
		fi; \
		NEW_HEAD=$$(git rev-parse HEAD 2>/dev/null || echo ""); \
		CHANGED_FILES=""; \
		if [ -n "$$OLD_HEAD" ] && [ -n "$$NEW_HEAD" ] && [ "$$OLD_HEAD" != "$$NEW_HEAD" ]; then \
			CHANGED_FILES=$$(git diff --name-only "$$OLD_HEAD" "$$NEW_HEAD"); \
		fi; \
		BUILD_API=0; \
		BUILD_WEB=0; \
		BUILD_DASHBOARD=0; \
		BUILD_SITE=0; \
		if [ -n "$$CHANGED_FILES" ]; then \
			echo -e "$(GREEN)[INFO]$(NC) Changed files since last deploy commit:"; \
			printf "%s\n" "$$CHANGED_FILES"; \
			while IFS= read -r FILE; do \
				case "$$FILE" in \
					web/*|Dockerfile.web) \
						BUILD_WEB=1 ;; \
					dashboard/*|Dockerfile.dashboard) \
						BUILD_DASHBOARD=1 ;; \
					site/*|docs/*|Dockerfile.site|Dockerfile.site.dockerignore) \
						BUILD_SITE=1 ;; \
					docker-compose.yml|docker-compose.dev.yml|Makefile) \
						BUILD_API=1; BUILD_WEB=1; BUILD_DASHBOARD=1; BUILD_SITE=1 ;; \
					.github/*|*.md|CLAUDE.md|AGENTS.md|.pre-commit-config.yaml) \
						;; \
					*) \
						BUILD_API=1 ;; \
				esac; \
			done <<< "$$CHANGED_FILES"; \
		else \
			echo -e "$(GREEN)[INFO]$(NC) No new commit detected on $(BRANCH)."; \
		fi; \
		SERVICES_TO_BUILD=""; \
		if [ "$$BUILD_API" -eq 1 ]; then SERVICES_TO_BUILD="$$SERVICES_TO_BUILD api"; fi; \
		if [ "$$BUILD_WEB" -eq 1 ]; then SERVICES_TO_BUILD="$$SERVICES_TO_BUILD web"; fi; \
		if [ "$$BUILD_DASHBOARD" -eq 1 ]; then SERVICES_TO_BUILD="$$SERVICES_TO_BUILD dashboard"; fi; \
		MCP_ON=0; PROFILE_ARGS=""; \
		if $(CONTAINER_CMD) inspect soda-mcp >/dev/null 2>&1; then MCP_ON=1; fi; \
		if [ "$$MCP_ON" -eq 1 ] && [ "$(COMPOSE_CMD)" != "podman-compose" ]; then PROFILE_ARGS="--profile mcp"; fi; \
		SITE_ON=0; SITE_PROFILE_ARGS=""; \
		if $(CONTAINER_CMD) inspect soda-site >/dev/null 2>&1; then SITE_ON=1; fi; \
		if [ "$(COMPOSE_CMD)" != "podman-compose" ]; then SITE_PROFILE_ARGS="--profile site"; fi; \
		echo -e "$(GREEN)[INFO]$(NC) Setting up data directory permissions..."; \
		mkdir -p data; \
		chmod -R 755 data; \
		chown -R 1000:1000 data; \
		if [ "$$BUILD_API" -eq 1 ]; then \
			echo -e "$(GREEN)[INFO]$(NC) Tagging API image as previous..."; \
			$(CONTAINER_CMD) tag soda-internal-api:latest soda-internal-api:previous 2>/dev/null || true; \
		fi; \
		if [ "$$BUILD_WEB" -eq 1 ]; then \
			echo -e "$(GREEN)[INFO]$(NC) Tagging web image as previous..."; \
			$(CONTAINER_CMD) tag soda-web:latest soda-web:previous 2>/dev/null || true; \
		fi; \
		if [ "$$BUILD_DASHBOARD" -eq 1 ]; then \
			echo -e "$(GREEN)[INFO]$(NC) Tagging dashboard image as previous..."; \
			$(CONTAINER_CMD) tag soda-dashboard:latest soda-dashboard:previous 2>/dev/null || true; \
		fi; \
		if [ -n "$$SERVICES_TO_BUILD" ]; then \
			echo -e "$(GREEN)[INFO]$(NC) Building changed service images:$$SERVICES_TO_BUILD"; \
			export COMMIT_HASH=$$(git rev-parse HEAD 2>/dev/null || echo "unknown"); \
			BUILDAH_LAYERS=true DOCKER_BUILDKIT=1 $(COMPOSE_CMD) -f docker-compose.yml build $$SERVICES_TO_BUILD; \
		fi; \
		echo -e "$(GREEN)[INFO]$(NC) Running database migrations..."; \
		uv run alembic upgrade head || { echo -e "$(RED)[ERROR]$(NC) Database migration failed!"; exit 1; }; \
		if [ -n "$$SERVICES_TO_BUILD" ]; then \
			SERVICES_TO_START="api bot web dashboard"; \
			if [ "$$MCP_ON" -eq 1 ]; then SERVICES_TO_START="$$SERVICES_TO_START mcp"; fi; \
			echo -e "$(GREEN)[INFO]$(NC) Recreating changed services:$$SERVICES_TO_START"; \
			$(COMPOSE_CMD) -f docker-compose.yml $$PROFILE_ARGS up -d --remove-orphans $$SERVICES_TO_START; \
		else \
			echo -e "$(YELLOW)[WARNING]$(NC) No deploy-impacting service changes detected. Skipping build/restart."; \
		fi; \
		wait_for_health() { \
			CONTAINER_NAME="$$1"; \
			MAX_SECONDS="$$2"; \
			ELAPSED=0; \
			echo -e "$(GREEN)[INFO]$(NC) Waiting for $$CONTAINER_NAME to become healthy..."; \
			while [ "$$ELAPSED" -lt "$$MAX_SECONDS" ]; do \
				RAW=$$($(CONTAINER_CMD) inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{.State.Status}}' "$$CONTAINER_NAME" 2>/dev/null || echo "missing|missing"); \
				STATUS=$${RAW%%|*}; [ -n "$$STATUS" ] || STATUS=$${RAW#*|}; \
				case "$$STATUS" in \
					healthy|running) \
						echo -e "$(GREEN)[INFO]$(NC) $$CONTAINER_NAME is $$STATUS."; \
						return 0 ;; \
					unhealthy|exited|dead) \
						echo -e "$(RED)[ERROR]$(NC) $$CONTAINER_NAME reported $$STATUS."; \
						return 1 ;; \
				esac; \
				sleep 2; \
				ELAPSED=$$((ELAPSED + 2)); \
			done; \
			echo -e "$(YELLOW)[WARNING]$(NC) Timed out waiting for $$CONTAINER_NAME health."; \
			return 1; \
		}; \
		check_image() { \
			WANT=$$($(CONTAINER_CMD) image inspect --format '{{.Id}}' "$$2" 2>/dev/null || echo "none"); \
			HAVE=$$($(CONTAINER_CMD) inspect --format '{{.Image}}' "$$1" 2>/dev/null || echo "missing"); \
			if [ "$${WANT#sha256:}" != "$${HAVE#sha256:}" ]; then \
				echo -e "$(RED)[ERROR]$(NC) $$1 does not run the new $$2 image (container: $$HAVE)."; \
				return 1; \
			fi; \
			echo -e "$(GREEN)[INFO]$(NC) $$1 runs the new $$2 image."; \
		}; \
		if [ -n "$$SERVICES_TO_BUILD" ]; then \
			wait_for_health soda-internal-api 60; \
			wait_for_health soda-bot 60; \
			wait_for_health soda-web 60; \
			wait_for_health soda-dashboard 60; \
			check_image soda-internal-api soda-internal-api:latest; \
			check_image soda-bot soda-internal-api:latest; \
			check_image soda-web soda-web:latest; \
			check_image soda-dashboard soda-dashboard:latest; \
			if [ "$$MCP_ON" -eq 1 ]; then \
				wait_for_health soda-mcp 60; \
				check_image soda-mcp soda-internal-api:latest; \
			fi; \
		fi; \
		if [ "$$BUILD_API" -eq 1 ]; then \
			if ! curl -fsS http://127.0.0.1:8000/health | grep -q "$$NEW_HEAD"; then \
				echo -e "$(RED)[ERROR]$(NC) /health does not report commit $$NEW_HEAD."; \
				exit 1; \
			fi; \
			echo -e "$(GREEN)[INFO]$(NC) /health reports commit $$NEW_HEAD."; \
		fi; \
		if [ "$$BUILD_SITE" -eq 1 ] && [ "$$SITE_ON" -eq 1 ]; then \
			echo -e "$(GREEN)[INFO]$(NC) Building and recreating the site..."; \
			$(CONTAINER_CMD) tag soda-site:latest soda-site:previous 2>/dev/null || true; \
			$(COMPOSE_CMD) -f docker-compose.yml $$SITE_PROFILE_ARGS build site; \
			$(COMPOSE_CMD) -f docker-compose.yml $$SITE_PROFILE_ARGS up -d --no-deps site; \
			wait_for_health soda-site 90; \
			check_image soda-site soda-site:latest; \
		fi; \
		echo -e "$(GREEN)[INFO]$(NC) Container status:"; \
		$(COMPOSE_CMD) ps; \
		echo -e "$(GREEN)[INFO]$(NC) Recent logs:"; \
		$(COMPOSE_CMD) logs --tail=20; \
		echo -e "$(GREEN)[INFO]$(NC) Cleaning up unused container images..."; \
		$(CONTAINER_CMD) image prune -f 2>/dev/null || true; \
		if [[ ! "$$NEW_HEAD" =~ ^[0-9a-f]{40}$$ ]]; then \
			echo -e "$(RED)[ERROR]$(NC) The deploy commit is not a sha."; \
			exit 1; \
		fi; \
		printf '%s\n' "$$NEW_HEAD" > data/deployed-sha; \
		echo -e "$(GREEN)[INFO]$(NC) Recorded deployed commit $$NEW_HEAD."; \
		echo -e "$(GREEN)[INFO]$(NC) Deployment completed successfully!"

# Development environment
dev:
	@echo -e "$(GREEN)[INFO]$(NC) Starting development environment with hot reloading..."
	@export COMMIT_HASH=$$(git rev-parse HEAD 2>/dev/null || echo "unknown") && \
		$(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.dev.yml up


# Rollback to previous version
rollback:
	@echo -e "$(YELLOW)[WARNING]$(NC) Rolling back to previous version..."
	@if $(CONTAINER_CMD) images | grep -q "soda-internal-api:previous"; then \
		echo -e "$(GREEN)[INFO]$(NC) Found previous version, rolling back..."; \
		$(CONTAINER_CMD) tag soda-internal-api:latest soda-internal-api:rollback-$$(date +%Y%m%d-%H%M%S); \
		$(CONTAINER_CMD) tag soda-internal-api:previous soda-internal-api:latest; \
		$(COMPOSE_CMD) up -d; \
		echo -e "$(GREEN)[INFO]$(NC) Rollback completed!"; \
		$(COMPOSE_CMD) ps; \
	else \
		echo -e "$(RED)[ERROR]$(NC) No previous version found for rollback"; \
		exit 1; \
	fi

# Show container status
status:
	@echo -e "$(GREEN)[INFO]$(NC) Container status:"
	@$(COMPOSE_CMD) ps

# Run database migrations
migrate:
	@echo -e "$(GREEN)[INFO]$(NC) Running database migrations..."
	@uv run alembic upgrade head
	@echo -e "$(GREEN)[INFO]$(NC) Database migrations complete!"

# Run lint (with auto-fix), format, type check, and tests
check:
	@echo -e "$(GREEN)[INFO]$(NC) Running ruff linting with auto-fix..."
	@uv run ruff check --fix .
	@echo -e "$(GREEN)[INFO]$(NC) Running ruff formatting..."
	@uv run ruff format .
	@echo -e "$(GREEN)[INFO]$(NC) Running ty type checking..."
	@uv run ty check .
	@echo -e "$(GREEN)[INFO]$(NC) Running tests..."
	@uv run pytest -v
	@echo -e "$(GREEN)[INFO]$(NC) Checking alembic migrations are up to date..."
	@uv run alembic upgrade head
	@uv run alembic check
	@echo -e "$(GREEN)[INFO]$(NC) All checks passed!"

# Run every check without changing files. CI runs this; a failure blocks the merge.
ci:
	@echo -e "$(GREEN)[INFO]$(NC) Running ruff linting..."
	@uv run ruff check .
	@echo -e "$(GREEN)[INFO]$(NC) Checking ruff formatting..."
	@uv run ruff format --check .
	@echo -e "$(GREEN)[INFO]$(NC) Running ty type checking..."
	@uv run ty check .
	@echo -e "$(GREEN)[INFO]$(NC) Checking module boundaries..."
	@uv run lint-imports --no-cache
	@echo -e "$(GREEN)[INFO]$(NC) Running tests, including the API contract tests..."
	@uv run pytest -v
	@echo -e "$(GREEN)[INFO]$(NC) Checking alembic migrations against a fresh database..."
	@TMP_DB=$$(mktemp -d) && \
		DATABASE_URL=sqlite:///$$TMP_DB/ci.db uv run alembic upgrade head && \
		DATABASE_URL=sqlite:///$$TMP_DB/ci.db uv run alembic check; \
		STATUS=$$?; rm -rf $$TMP_DB; exit $$STATUS
	@echo -e "$(GREEN)[INFO]$(NC) All checks passed!"

# Copy the SQLite database before a deploy. Uses SQLite's online backup, so it is safe while the API runs.
backup:
	@mkdir -p data/backups
	@if [ -f data/user.db ]; then \
		BACKUP=data/backups/user-$$(date +%Y%m%d-%H%M%S).db; \
		uv run python -c 'import sqlite3, sys; src = sqlite3.connect("data/user.db"); dst = sqlite3.connect(sys.argv[1]); src.backup(dst); dst.close(); src.close()' "$$BACKUP" && \
		echo -e "$(GREEN)[INFO]$(NC) Database copied to $$BACKUP"; \
	else \
		echo -e "$(YELLOW)[WARNING]$(NC) data/user.db not found, nothing to back up"; \
	fi
	@ls -1t data/backups/user-*.db 2>/dev/null | tail -n +15 | xargs -r rm -f

# Health check
health:
	@FAILED=0; \
	CONTAINERS="soda-internal-api soda-bot soda-web soda-dashboard"; \
	if $(CONTAINER_CMD) inspect soda-mcp >/dev/null 2>&1; then CONTAINERS="$$CONTAINERS soda-mcp"; fi; \
	if $(CONTAINER_CMD) inspect soda-site >/dev/null 2>&1; then CONTAINERS="$$CONTAINERS soda-site"; fi; \
	for CONTAINER_NAME in $$CONTAINERS; do \
		RAW=$$($(CONTAINER_CMD) inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{.State.Status}}' "$$CONTAINER_NAME" 2>/dev/null || echo "missing|missing"); \
		STATUS=$${RAW%%|*}; [ -n "$$STATUS" ] || STATUS=$${RAW#*|}; \
		case "$$STATUS" in \
			healthy|running) echo -e "$(GREEN)✅ $$CONTAINER_NAME is $$STATUS$(NC)" ;; \
			*) echo -e "$(RED)❌ $$CONTAINER_NAME is $$STATUS$(NC)"; FAILED=1 ;; \
		esac; \
	done; \
	if [ "$$FAILED" -eq 1 ]; then \
		echo -e "$(RED)[ERROR]$(NC) Recent logs:"; \
		$(COMPOSE_CMD) logs --tail=50; \
		exit 1; \
	fi
