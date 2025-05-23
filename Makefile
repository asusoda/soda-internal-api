.PHONY: help build up down logs shell clean deploy dev prod rollback status health-check

# Configuration
PROJECT_DIR ?= /var/www/soda-internal-api
BRANCH ?= main
COMPOSE_CMD := $(shell if docker compose version > /dev/null 2>&1; then echo "docker compose"; else echo "docker-compose"; fi)

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

# Default target
help:
	@echo "Available commands:"
	@echo "  make build       - Build Docker images"
	@echo "  make up          - Start services in development mode"
	@echo "  make down        - Stop and remove containers"
	@echo "  make logs        - View container logs"
	@echo "  make shell       - Open shell in API container"
	@echo "  make clean       - Clean up containers and images"
	@echo "  make deploy      - Deploy to production (pull, build, restart)"
	@echo "  make dev         - Start development environment"
	@echo "  make prod        - Start production environment locally"
	@echo "  make rollback    - Rollback to previous version"
	@echo "  make status      - Show container status"
	@echo "  make health-check - Check container health"

# Build Docker images
build:
	@echo -e "$(GREEN)[INFO]$(NC) Building Docker images with BuildKit..."
	@DOCKER_BUILDKIT=1 $(COMPOSE_CMD) build --parallel

# Build only API
build-api:
	@echo -e "$(GREEN)[INFO]$(NC) Building API image..."
	@DOCKER_BUILDKIT=1 $(COMPOSE_CMD) build api

# Build only web
build-web:
	@echo -e "$(GREEN)[INFO]$(NC) Building web image..."
	@DOCKER_BUILDKIT=1 $(COMPOSE_CMD) build web

# Start services in development mode
up:
	@echo -e "$(GREEN)[INFO]$(NC) Starting services..."
	@$(COMPOSE_CMD) up -d

# Stop services
down:
	@echo -e "$(GREEN)[INFO]$(NC) Stopping services..."
	@$(COMPOSE_CMD) down

# View logs
logs:
	@$(COMPOSE_CMD) logs -f

# Open shell in API container
shell:
	@$(COMPOSE_CMD) exec api /bin/bash

# Clean up everything
clean:
	@echo -e "$(YELLOW)[WARNING]$(NC) Cleaning up containers and volumes..."
	@$(COMPOSE_CMD) down -v
	@docker system prune -f

# Deploy to production
deploy:
	@echo -e "$(GREEN)[INFO]$(NC) Starting deployment process..."
	@if [ "$$(pwd)" != "$(PROJECT_DIR)" ]; then \
		echo -e "$(YELLOW)[WARNING]$(NC) Not in project directory, changing to $(PROJECT_DIR)"; \
		cd $(PROJECT_DIR) || (echo -e "$(RED)[ERROR]$(NC) Failed to change directory"; exit 1); \
	fi
	@echo -e "$(GREEN)[INFO]$(NC) Pulling latest changes from repository..."
	@git pull || (echo -e "$(RED)[ERROR]$(NC) Failed to pull from repository"; exit 1)
	@echo -e "$(GREEN)[INFO]$(NC) Checking out $(BRANCH) branch..."
	@git checkout $(BRANCH) || (echo -e "$(RED)[ERROR]$(NC) Failed to checkout $(BRANCH)"; exit 1)
	@echo -e "$(GREEN)[INFO]$(NC) Setting up data directory permissions..."
	@mkdir -p data
	@chmod -R 755 data
	@chown -R 1000:1000 data
	@echo -e "$(GREEN)[INFO]$(NC) Tagging current version as previous..."
	@docker tag soda-internal-api:latest soda-internal-api:previous 2>/dev/null || true
	@echo -e "$(GREEN)[INFO]$(NC) Building Docker image..."
	@DOCKER_BUILDKIT=1 $(COMPOSE_CMD) -f docker-compose.yml build || (echo -e "$(RED)[ERROR]$(NC) Failed to build Docker image"; exit 1)
	@echo -e "$(GREEN)[INFO]$(NC) Stopping existing containers..."
	@$(COMPOSE_CMD) -f docker-compose.yml down
	@echo -e "$(GREEN)[INFO]$(NC) Starting containers..."
	@$(COMPOSE_CMD) -f docker-compose.yml up -d || (echo -e "$(RED)[ERROR]$(NC) Failed to start containers"; exit 1)
	@echo -e "$(GREEN)[INFO]$(NC) Waiting for container to be healthy..."
	@for i in $$(seq 1 30); do \
		if $(COMPOSE_CMD) ps | grep -q "healthy"; then \
			echo -e "$(GREEN)[INFO]$(NC) Container is healthy!"; \
			break; \
		elif [ $$i -eq 30 ]; then \
			echo -e "$(YELLOW)[WARNING]$(NC) Container health check timed out"; \
		else \
			printf "."; \
			sleep 2; \
		fi; \
	done
	@echo
	@echo -e "$(GREEN)[INFO]$(NC) Container status:"
	@$(COMPOSE_CMD) ps
	@echo -e "$(GREEN)[INFO]$(NC) Recent logs:"
	@$(COMPOSE_CMD) logs --tail=20
	@echo -e "$(GREEN)[INFO]$(NC) Deployment completed successfully!"

# Development environment
dev:
	@echo -e "$(GREEN)[INFO]$(NC) Starting development environment..."
	@$(COMPOSE_CMD) up

# Production environment (locally)
prod:
	@echo -e "$(GREEN)[INFO]$(NC) Starting production environment..."
	@$(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.prod.yml up -d

# Rollback to previous version
rollback:
	@echo -e "$(YELLOW)[WARNING]$(NC) Rolling back to previous version..."
	@if docker images | grep -q "soda-internal-api:previous"; then \
		echo -e "$(GREEN)[INFO]$(NC) Found previous version, rolling back..."; \
		docker tag soda-internal-api:latest soda-internal-api:rollback-$$(date +%Y%m%d-%H%M%S); \
		docker tag soda-internal-api:previous soda-internal-api:latest; \
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
	@echo
	@echo -e "$(GREEN)[INFO]$(NC) Container resource usage:"
	@docker stats --no-stream $$($(COMPOSE_CMD) ps -q) 2>/dev/null || true

# Health check
health-check:
	@echo -e "$(GREEN)[INFO]$(NC) Checking container health..."
	@if $(COMPOSE_CMD) ps | grep -q "healthy"; then \
		echo -e "$(GREEN)✅ Container is healthy!$(NC)"; \
	elif $(COMPOSE_CMD) ps | grep -q "unhealthy"; then \
		echo -e "$(RED)❌ Container is unhealthy!$(NC)"; \
		echo -e "$(RED)[ERROR]$(NC) Recent logs:"; \
		$(COMPOSE_CMD) logs --tail=50; \
		exit 1; \
	else \
		echo -e "$(YELLOW)⚠️  No health check configured or container not running$(NC)"; \
	fi
