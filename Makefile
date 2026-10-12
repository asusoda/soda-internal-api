.PHONY: help doppler-check doppler-check-service build up down logs shell clean deploy dev prod rollback status health discard-local-changes check ci backup migrate

# Use bash as the shell for all commands
SHELL := /usr/bin/env bash

# Configuration
PROJECT_DIR ?= /var/www/soda-internal-api
BRANCH ?= main
# The commit before this deploy, to find the changed files. cd.yml sets it.
DEPLOY_FROM ?=
# The commit that passed Check. When set, check out this commit instead of origin/$(BRANCH).
DEPLOY_SHA ?=
# Where make deploy gets the images. registry: pull $(IMAGE_REPO)-<service>:<commit>, which images.yml
# pushes, and build on this server only when the pull fails. build: always build on this server.
IMAGE_SOURCE ?= registry
IMAGE_REPO ?= ghcr.io/asusoda/platform
# The last lines of each container's log. podman-compose 1.0.6 logs stops with exit code 125 when a
# service has no container (worker, postgres), so this reads each container that exists.
CONTAINERS := soda-internal-api soda-bot soda-worker soda-mcp soda-dashboard soda-site soda-postgres
define container_logs
for CONTAINER_NAME in $(CONTAINERS); do \
	if $(CONTAINER_CMD) inspect "$$CONTAINER_NAME" >/dev/null 2>&1; then \
		echo "--- $$CONTAINER_NAME"; \
		$(CONTAINER_CMD) logs --tail=$(1) "$$CONTAINER_NAME" 2>&1 || true; \
	fi; \
done
endef
COMPOSE_CMD := $(shell if command -v podman-compose > /dev/null 2>&1; then echo "podman-compose"; elif docker compose version > /dev/null 2>&1; then echo "docker compose"; else echo "docker-compose"; fi)
CONTAINER_CMD := $(shell if command -v podman > /dev/null 2>&1; then echo "podman"; else echo "docker"; fi)

# Settings come from Doppler. See docs/operations.md, "Settings".
# On the host, Compose reads the build args, POSTGRES_PASSWORD and the container caps from Doppler, and Alembic
# reads DATABASE_URL. Each container gets DOPPLER_TOKEN and reads its settings itself (deploy/docker-entrypoint.sh).
# DOPPLER_TOKEN comes from the environment, or from the Doppler CLI configuration of this directory. For deploy it
# comes from the configuration of PROJECT_DIR. Targets that start containers accept only a service token
# (doppler-check-service).
ifndef DOPPLER_TOKEN
doppler_token = $(shell command -v doppler > /dev/null 2>&1 && doppler configure get token --plain --scope "$(1)" 2>/dev/null)
DOPPLER_TOKEN := $(call doppler_token,$(CURDIR))
deploy: DOPPLER_TOKEN := $(call doppler_token,$(PROJECT_DIR))
endif
export DOPPLER_TOKEN
WITH_SETTINGS := doppler run --no-fallback --no-check-version --
COMPOSE_SET := $(WITH_SETTINGS) $(COMPOSE_CMD)

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
	@echo "  make deploy                 - Deploy to production (pull images, migrate, restart)"
	@echo "  make discard-local-changes  - Discard local git changes (used by CD)"
	@echo "  make dev                    - Start development environment with hot reloading"
	@echo "  make rollback               - Rollback to previous version"
	@echo "  make status                 - Show container status"
	@echo "  make health                 - Check container health"
	@echo "  make check                  - Run lint (auto-fix), format, type check, and tests"
	@echo "  make ci                     - Run the same checks without changing files (what CI runs)"
	@echo "  make backup                 - Copy the SQLite database to data/backups (keeps the last 14)"
	@echo "  make migrate                - Run alembic database migrations"
	@echo "  make doppler-check          - Check that the Doppler CLI and a Doppler token are available"

# Stop with a message when the settings cannot come from Doppler
doppler-check:
	@command -v doppler > /dev/null 2>&1 || { \
		echo -e "$(RED)[ERROR]$(NC) The Doppler CLI is not installed. Run deploy/install-doppler.sh."; exit 1; }
	@[ -n "$$DOPPLER_TOKEN" ] || { \
		echo -e "$(RED)[ERROR]$(NC) No Doppler token. Run doppler setup in this directory, or set DOPPLER_TOKEN. See docs/operations.md."; exit 1; }

# The containers get DOPPLER_TOKEN, so it must be a service token, which reads only one config
doppler-check-service: doppler-check
	@case "$$DOPPLER_TOKEN" in dp.st.*) ;; *) \
		echo -e "$(RED)[ERROR]$(NC) This target gives DOPPLER_TOKEN to the containers, so it needs a Doppler service token (dp.st.)."; \
		echo "See docs/getting-started.md (your machine) or docs/operations.md, \"Settings\" (a server)."; \
		exit 1 ;; esac

# Build container images
build: doppler-check
	@echo -e "$(GREEN)[INFO]$(NC) Building container images with BuildKit..."
	@export COMMIT_HASH=$$(git rev-parse HEAD 2>/dev/null || echo "unknown") && \
		DOCKER_BUILDKIT=1 $(COMPOSE_SET) build

# Build only API
build-api: doppler-check
	@echo -e "$(GREEN)[INFO]$(NC) Building API image..."
	@export COMMIT_HASH=$$(git rev-parse HEAD 2>/dev/null || echo "unknown") && \
		DOCKER_BUILDKIT=1 $(COMPOSE_SET) build api

# Build only the dashboard
build-dashboard: doppler-check
	@echo -e "$(GREEN)[INFO]$(NC) Building dashboard image..."
	@DOCKER_BUILDKIT=1 $(COMPOSE_SET) build dashboard

# Start services in development mode
up: doppler-check-service
	@echo -e "$(GREEN)[INFO]$(NC) Starting services..."
	@export COMMIT_HASH=$$(git rev-parse HEAD 2>/dev/null || echo "unknown") && \
		$(COMPOSE_SET) up -d

# Stop services
down:
	@echo -e "$(GREEN)[INFO]$(NC) Stopping services..."
	@$(COMPOSE_CMD) down

# View logs (batch-friendly, last 50 lines)
logs:
	@$(call container_logs,50)

# Follow logs (continuous)
logs-follow:
	@$(COMPOSE_CMD) logs -f

# Open shell in API container
shell:
	@$(COMPOSE_CMD) exec api docker-entrypoint.sh /bin/bash

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
# dashboard, bot and mcp are created with --requires on the api container. When any image changes,
# all of them are recreated together. podman-compose 1.0.6 recreates a service's dependencies with it, so
# `up -d dashboard` also tries to replace api. It then removes the other containers that require api and
# fails to replace api ("has dependent containers"), which leaves only api and dashboard running.
# soda-mcp (profile mcp) and soda-worker (profile postgres) are recreated when they exist. Docker Compose
# gets --profile mcp and --profile postgres; podman-compose 1.0.6 has no --profile option and ignores
# profiles, so it gets the service names only. soda-worker requires api, so podman cannot remove api
# while soda-worker exists and is not recreated with it.
# soda-site (profile site) does not require api. When soda-site:latest or the soda-site
# container exists and site/ or docs/ changes, this target rebuilds site and recreates it
# with --no-deps. When this deploy does not rebuild site and soda-site:latest exists, it
# starts soda-site with --no-deps.
# podman-compose 1.0.6 --remove-orphans removes every project container this up did not
# name, including soda-site. This target omits that flag for podman-compose.
# Docker Compose still gets --remove-orphans.
# podman-compose 1.0.6 recreates a container only when the compose config hash changes. A pulled image
# does not change the hash, so `up` without --force-recreate starts the old containers again.
# .deploy/ is not mounted into the API container, and chown of data/ does not change it.
# .deploy/deployed-sha stores the last commit that finished this target.
# .deploy/rollback-sha stores that commit when a later deploy finishes, so rollback can restore it.
# .deploy/rollback-api and .deploy/rollback-site record that this deploy tagged that image as previous.
deploy: doppler-check-service
	@set -e; \
		echo -e "$(GREEN)[INFO]$(NC) Starting deployment process..."; \
		if [ "$$(pwd)" != "$(PROJECT_DIR)" ]; then \
			echo -e "$(YELLOW)[WARNING]$(NC) Not in project directory, changing to $(PROJECT_DIR)"; \
			cd "$(PROJECT_DIR)"; \
		fi; \
		write_file() { \
			dest="$$1"; contents="$$2"; tmp="$${dest}.tmp.$$$$"; \
			mkdir -p .deploy; \
			printf '%s\n' "$$contents" > "$$tmp"; \
			mv -f "$$tmp" "$$dest"; \
		}; \
		mkdir -p .deploy; \
		rm -f data/deployed-sha data/rollback-api data/rollback-site; \
		rm -f .deploy/rollback-api .deploy/rollback-site .deploy/rollback-sha; \
		RECORDED=""; \
		if [ -f .deploy/deployed-sha ]; then RECORDED=$$(tr -d '[:space:]' < .deploy/deployed-sha); fi; \
		if [[ ! "$$RECORDED" =~ ^[0-9a-f]{40}$$ ]]; then RECORDED=""; fi; \
		if [ -n "$$RECORDED" ] && ! git cat-file -e "$$RECORDED^{commit}" 2>/dev/null; then \
			echo -e "$(YELLOW)[WARNING]$(NC) The recorded deploy commit is not in this checkout."; \
			RECORDED=""; \
		fi; \
		OLD_HEAD="$$RECORDED"; \
		if [ -z "$$OLD_HEAD" ]; then OLD_HEAD="$(DEPLOY_FROM)"; fi; \
		if [ -z "$$OLD_HEAD" ]; then OLD_HEAD=$$(git rev-parse HEAD 2>/dev/null || echo ""); fi; \
		echo -e "$(GREEN)[INFO]$(NC) Fetching the deploy commit..."; \
		if [ -n "$(DEPLOY_SHA)" ]; then \
			if [[ ! "$(DEPLOY_SHA)" =~ ^[0-9a-f]{40}$$ ]]; then \
				echo -e "$(RED)[ERROR]$(NC) DEPLOY_SHA is not a 40-character sha."; \
				exit 1; \
			fi; \
			if [ "$$(git rev-parse HEAD 2>/dev/null)" != "$(DEPLOY_SHA)" ]; then \
				git fetch origin "$(DEPLOY_SHA)" || git fetch origin "$(BRANCH)"; \
				git checkout --detach --force "$(DEPLOY_SHA)"; \
			fi; \
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
		BUILD_DASHBOARD=0; \
		BUILD_SITE=0; \
		if [ -n "$$CHANGED_FILES" ]; then \
			echo -e "$(GREEN)[INFO]$(NC) Changed files since last deploy commit:"; \
			printf "%s\n" "$$CHANGED_FILES"; \
			while IFS= read -r FILE; do \
				case "$$FILE" in \
					dashboard/*|Dockerfile.dashboard) \
						BUILD_DASHBOARD=1 ;; \
					site/*|docs/*|Dockerfile.site|Dockerfile.site.dockerignore) \
						BUILD_SITE=1 ;; \
					docker-compose.yml|docker-compose.dev.yml|Makefile) \
						BUILD_API=1; BUILD_DASHBOARD=1; BUILD_SITE=1 ;; \
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
		if [ "$$BUILD_DASHBOARD" -eq 1 ]; then SERVICES_TO_BUILD="$$SERVICES_TO_BUILD dashboard"; fi; \
		MCP_ON=0; WORKER_ON=0; PROFILE_ARGS=""; \
		if $(CONTAINER_CMD) inspect soda-mcp >/dev/null 2>&1; then MCP_ON=1; fi; \
		if $(CONTAINER_CMD) inspect soda-worker >/dev/null 2>&1; then WORKER_ON=1; fi; \
		if [ "$(COMPOSE_CMD)" != "podman-compose" ]; then \
			if [ "$$MCP_ON" -eq 1 ]; then PROFILE_ARGS="$$PROFILE_ARGS --profile mcp"; fi; \
			if [ "$$WORKER_ON" -eq 1 ]; then PROFILE_ARGS="$$PROFILE_ARGS --profile postgres"; fi; \
		fi; \
		SITE_ON=0; SITE_IMAGE=0; SITE_PROFILE_ARGS=""; \
		if $(CONTAINER_CMD) inspect soda-site >/dev/null 2>&1; then SITE_ON=1; fi; \
		if $(CONTAINER_CMD) image inspect soda-site:latest >/dev/null 2>&1; then SITE_IMAGE=1; fi; \
		if [ "$(COMPOSE_CMD)" != "podman-compose" ]; then SITE_PROFILE_ARGS="--profile site"; fi; \
		ORPHAN_ARGS="--remove-orphans"; \
		if [ "$(COMPOSE_CMD)" = "podman-compose" ]; then ORPHAN_ARGS=""; fi; \
		echo -e "$(GREEN)[INFO]$(NC) Setting up data directory permissions..."; \
		mkdir -p data; \
		chmod -R 755 data; \
		chown -R 1000:1000 data; \
		if [ "$$BUILD_API" -eq 1 ]; then \
			echo -e "$(GREEN)[INFO]$(NC) Tagging API image as previous..."; \
			if $(CONTAINER_CMD) tag soda-internal-api:latest soda-internal-api:previous 2>/dev/null; then \
				write_file .deploy/rollback-api api; \
			fi; \
		fi; \
		if [ "$$BUILD_DASHBOARD" -eq 1 ]; then \
			echo -e "$(GREEN)[INFO]$(NC) Tagging dashboard image as previous..."; \
			$(CONTAINER_CMD) tag soda-dashboard:latest soda-dashboard:previous 2>/dev/null || true; \
		fi; \
		local_image() { \
			case "$$1" in api) echo soda-internal-api:latest ;; *) echo "soda-$$1:latest" ;; esac; \
		}; \
		pull_image() { \
			[ "$(IMAGE_SOURCE)" = "registry" ] || return 1; \
			REF="$(IMAGE_REPO)-$$1:$$NEW_HEAD"; \
			echo -e "$(GREEN)[INFO]$(NC) Pulling $$REF..."; \
			if $(CONTAINER_CMD) pull -q "$$REF" >/dev/null && $(CONTAINER_CMD) tag "$$REF" "$$(local_image "$$1")"; then \
				$(CONTAINER_CMD) rmi "$$REF" >/dev/null 2>&1 || true; \
				return 0; \
			fi; \
			echo -e "$(YELLOW)[WARNING]$(NC) Could not pull $$REF. Building $$1 on this server."; \
			return 1; \
		}; \
		build_images() { \
			echo -e "$(GREEN)[INFO]$(NC) Building on this server:$$*"; \
			export COMMIT_HASH="$$NEW_HEAD"; \
			BUILDAH_LAYERS=true DOCKER_BUILDKIT=1 $(COMPOSE_SET) -f docker-compose.yml $$SITE_PROFILE_ARGS build "$$@"; \
		}; \
		if [ -n "$$SERVICES_TO_BUILD" ]; then \
			echo -e "$(GREEN)[INFO]$(NC) Getting changed service images:$$SERVICES_TO_BUILD"; \
			LOCAL_BUILDS=""; \
			for SERVICE in $$SERVICES_TO_BUILD; do \
				pull_image "$$SERVICE" || LOCAL_BUILDS="$$LOCAL_BUILDS $$SERVICE"; \
			done; \
			if [ -n "$$LOCAL_BUILDS" ]; then build_images $$LOCAL_BUILDS; fi; \
		fi; \
		echo -e "$(GREEN)[INFO]$(NC) Running database migrations..."; \
		$(WITH_SETTINGS) uv run alembic upgrade head || { echo -e "$(RED)[ERROR]$(NC) Database migration failed!"; exit 1; }; \
		if $(CONTAINER_CMD) inspect soda-web >/dev/null 2>&1; then \
			echo -e "$(GREEN)[INFO]$(NC) Removing the soda-web container of the removed web service..."; \
			$(CONTAINER_CMD) rm -f soda-web; \
		fi; \
		$(CONTAINER_CMD) rmi soda-web:latest 2>/dev/null || true; \
		$(CONTAINER_CMD) rmi soda-web:previous 2>/dev/null || true; \
		if [ -n "$$SERVICES_TO_BUILD" ]; then \
			SERVICES_TO_START="api bot dashboard"; \
			if [ "$$MCP_ON" -eq 1 ]; then SERVICES_TO_START="$$SERVICES_TO_START mcp"; fi; \
			if [ "$$WORKER_ON" -eq 1 ]; then SERVICES_TO_START="$$SERVICES_TO_START worker"; fi; \
			echo -e "$(GREEN)[INFO]$(NC) Recreating changed services:$$SERVICES_TO_START"; \
			$(COMPOSE_SET) -f docker-compose.yml $$PROFILE_ARGS up -d --force-recreate $$ORPHAN_ARGS $$SERVICES_TO_START; \
		else \
			echo -e "$(YELLOW)[WARNING]$(NC) No deploy-impacting service changes detected. Skipping build/restart."; \
		fi; \
		wait_for_health() { \
			CONTAINER_NAME="$$1"; \
			MAX_SECONDS="$$2"; \
			PROBE_URL="$${3:-}"; \
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
				if [ "$$STATUS" = "starting" ] && [ -n "$$PROBE_URL" ] && [ "$(CONTAINER_CMD)" = "podman" ] && \
					curl -fsS -o /dev/null --max-time 2 "$$PROBE_URL" 2>/dev/null; then \
					podman healthcheck run "$$CONTAINER_NAME" >/dev/null 2>&1 || true; \
				fi; \
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
				echo -e "$(RED)[ERROR]$(NC) $$1 does not run $$2 (container: $$HAVE)."; \
				return 1; \
			fi; \
			echo -e "$(GREEN)[INFO]$(NC) $$1 runs $$2."; \
		}; \
		check_if_present() { \
			if $(CONTAINER_CMD) inspect "$$1" >/dev/null 2>&1; then check_image "$$1" "$$2"; fi; \
		}; \
		if [ -n "$$SERVICES_TO_BUILD" ]; then \
			wait_for_health soda-internal-api 60 http://127.0.0.1:8000/health; \
			wait_for_health soda-bot 60; \
			wait_for_health soda-dashboard 60 http://127.0.0.1:5001; \
			check_image soda-internal-api soda-internal-api:latest; \
			check_image soda-bot soda-internal-api:latest; \
			check_image soda-dashboard soda-dashboard:latest; \
			if [ "$$MCP_ON" -eq 1 ]; then \
				wait_for_health soda-mcp 60; \
				check_image soda-mcp soda-internal-api:latest; \
			fi; \
			if [ "$$WORKER_ON" -eq 1 ]; then \
				wait_for_health soda-worker 60; \
				check_image soda-worker soda-internal-api:latest; \
			fi; \
		fi; \
		if [ "$$BUILD_API" -eq 1 ]; then \
			if ! curl -fsS http://127.0.0.1:8000/health | grep -q "$$NEW_HEAD"; then \
				echo -e "$(RED)[ERROR]$(NC) /health does not report commit $$NEW_HEAD."; \
				exit 1; \
			fi; \
			echo -e "$(GREEN)[INFO]$(NC) /health reports commit $$NEW_HEAD."; \
		fi; \
		if [ "$$BUILD_SITE" -eq 1 ] && { [ "$$SITE_ON" -eq 1 ] || [ "$$SITE_IMAGE" -eq 1 ]; }; then \
			echo -e "$(GREEN)[INFO]$(NC) Building and recreating the site..."; \
			if $(CONTAINER_CMD) tag soda-site:latest soda-site:previous 2>/dev/null; then \
				write_file .deploy/rollback-site site; \
			fi; \
			pull_image site || build_images site; \
			$(COMPOSE_SET) -f docker-compose.yml $$SITE_PROFILE_ARGS up -d --no-deps --force-recreate site; \
			wait_for_health soda-site 90 http://127.0.0.1:3010; \
			check_image soda-site soda-site:latest; \
		elif [ "$$SITE_IMAGE" -eq 1 ]; then \
			echo -e "$(GREEN)[INFO]$(NC) Starting the site..."; \
			$(COMPOSE_SET) -f docker-compose.yml $$SITE_PROFILE_ARGS up -d --no-deps site; \
			wait_for_health soda-site 90 http://127.0.0.1:3010; \
			check_image soda-site soda-site:latest; \
		elif [ "$$SITE_ON" -eq 1 ]; then \
			check_image soda-site soda-site:latest; \
		fi; \
		echo -e "$(GREEN)[INFO]$(NC) Container status:"; \
		$(COMPOSE_CMD) ps; \
		echo -e "$(GREEN)[INFO]$(NC) Recent logs:"; \
		$(call container_logs,20); \
		echo -e "$(GREEN)[INFO]$(NC) Cleaning up unused container images..."; \
		$(CONTAINER_CMD) image prune -f 2>/dev/null || true; \
		if [ -z "$$SERVICES_TO_BUILD" ]; then \
			check_if_present soda-internal-api soda-internal-api:latest; \
			check_if_present soda-bot soda-internal-api:latest; \
			check_if_present soda-dashboard soda-dashboard:latest; \
			if [ "$$MCP_ON" -eq 1 ]; then check_if_present soda-mcp soda-internal-api:latest; fi; \
		fi; \
		if [[ ! "$$NEW_HEAD" =~ ^[0-9a-f]{40}$$ ]]; then \
			echo -e "$(RED)[ERROR]$(NC) The deploy commit is not a sha."; \
			exit 1; \
		fi; \
		if [ -f .deploy/deployed-sha ]; then \
			PRIOR=$$(tr -d '[:space:]' < .deploy/deployed-sha); \
			if [[ "$$PRIOR" =~ ^[0-9a-f]{40}$$ ]] && [ "$$PRIOR" != "$$NEW_HEAD" ]; then \
				write_file .deploy/rollback-sha "$$PRIOR"; \
			fi; \
		fi; \
		write_file .deploy/deployed-sha "$$NEW_HEAD"; \
		echo -e "$(GREEN)[INFO]$(NC) Recorded deployed commit $$NEW_HEAD."; \
		echo -e "$(GREEN)[INFO]$(NC) Deployment completed successfully!"

# Development environment
dev: doppler-check-service
	@echo -e "$(GREEN)[INFO]$(NC) Starting development environment with hot reloading..."
	@export COMMIT_HASH=$$(git rev-parse HEAD 2>/dev/null || echo "unknown") && \
		$(COMPOSE_SET) -f docker-compose.yml -f docker-compose.dev.yml up


# Rollback to previous version
# It recreates only the services that make deploy recreates. podman-compose 1.0.6 ignores profiles, so a
# bare `up -d` also starts worker and postgres.
rollback: doppler-check-service
	@echo -e "$(YELLOW)[WARNING]$(NC) Rolling back to previous version..."
	@set -e; \
	ROLLED=0; \
	restore_baseline() { \
		if [ -f .deploy/rollback-sha ]; then \
			BASE=$$(tr -d '[:space:]' < .deploy/rollback-sha); \
			if [[ "$$BASE" =~ ^[0-9a-f]{40}$$ ]]; then \
				mkdir -p .deploy; \
				tmp=".deploy/deployed-sha.tmp.$$$$"; \
				printf '%s\n' "$$BASE" > "$$tmp"; \
				mv -f "$$tmp" .deploy/deployed-sha; \
				echo -e "$(GREEN)[INFO]$(NC) Restored deploy baseline $$BASE."; \
			fi; \
			rm -f .deploy/rollback-sha; \
		fi; \
	}; \
	trap 'status=$$?; if [ "$$status" -ne 0 ] && [ "$$ROLLED" -eq 1 ]; then restore_baseline || true; fi; exit $$status' EXIT; \
	if [ -f .deploy/rollback-api ] && $(CONTAINER_CMD) image inspect soda-internal-api:previous >/dev/null 2>&1; then \
		echo -e "$(GREEN)[INFO]$(NC) Found previous API image, rolling back..."; \
		$(CONTAINER_CMD) tag soda-internal-api:latest soda-internal-api:rollback-$$(date +%Y%m%d-%H%M%S); \
		$(CONTAINER_CMD) tag soda-internal-api:previous soda-internal-api:latest; \
		ROLLED=1; \
		SERVICES="api bot dashboard"; PROFILE_ARGS=""; \
		if $(CONTAINER_CMD) inspect soda-mcp >/dev/null 2>&1; then \
			SERVICES="$$SERVICES mcp"; \
			if [ "$(COMPOSE_CMD)" != "podman-compose" ]; then PROFILE_ARGS="$$PROFILE_ARGS --profile mcp"; fi; \
		fi; \
		if $(CONTAINER_CMD) inspect soda-worker >/dev/null 2>&1; then \
			SERVICES="$$SERVICES worker"; \
			if [ "$(COMPOSE_CMD)" != "podman-compose" ]; then PROFILE_ARGS="$$PROFILE_ARGS --profile postgres"; fi; \
		fi; \
		$(COMPOSE_SET) -f docker-compose.yml $$PROFILE_ARGS up -d --force-recreate $$SERVICES; \
	fi; \
	if [ -f .deploy/rollback-site ] && $(CONTAINER_CMD) image inspect soda-site:previous >/dev/null 2>&1; then \
		echo -e "$(GREEN)[INFO]$(NC) Found previous site image, rolling back..."; \
		$(CONTAINER_CMD) tag soda-site:latest soda-site:rollback-$$(date +%Y%m%d-%H%M%S); \
		$(CONTAINER_CMD) tag soda-site:previous soda-site:latest; \
		ROLLED=1; \
		SITE_PROFILE_ARGS=""; \
		if [ "$(COMPOSE_CMD)" != "podman-compose" ]; then SITE_PROFILE_ARGS="--profile site"; fi; \
		$(COMPOSE_SET) -f docker-compose.yml $$SITE_PROFILE_ARGS up -d --no-deps --force-recreate site; \
	fi; \
	if [ "$$ROLLED" -eq 0 ]; then \
		echo -e "$(RED)[ERROR]$(NC) No previous version found for rollback"; \
		exit 1; \
	fi; \
	restore_baseline; \
	echo -e "$(GREEN)[INFO]$(NC) Rollback completed!"; \
	$(COMPOSE_CMD) ps

# Show container status
status:
	@echo -e "$(GREEN)[INFO]$(NC) Container status:"
	@$(COMPOSE_CMD) ps

# Run database migrations
migrate: doppler-check
	@echo -e "$(GREEN)[INFO]$(NC) Running database migrations..."
	@$(WITH_SETTINGS) uv run alembic upgrade head
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
	CONTAINERS="soda-internal-api soda-bot soda-dashboard"; \
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
		$(call container_logs,50); \
		exit 1; \
	fi
