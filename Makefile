.PHONY: build up down stress-test help

# Default target
.DEFAULT_GOAL := help

# Variables
DOCKER_COMPOSE = docker compose
STRESS_TEST_URL = http://localhost:8081/run-test

# Help target
help:
	@echo "Available targets:"
	@echo "  build       - Build all services"
	@echo "  up          - Start all services"
	@echo "  down        - Stop all services"
	@echo "  stress-test - Run stress test with default parameters"
	@echo "  stress-test-custom - Run stress test with custom parameters"
	@echo "  help        - Show this help message"

# Build all services
build:
	@echo "Building services..."
	$(DOCKER_COMPOSE) build

# Start all services
up:
	@echo "Starting services..."
	$(DOCKER_COMPOSE) up -d
	@echo "Services started. API available at http://localhost:5000"
	@echo "Stress test service available at http://localhost:8081"
	@echo "Victoria metrics is available at http://localhost:8428"
	@echo "Grafana is available at http://localhost:3000"

# Stop all services
down:
	@echo "Stopping services..."
	$(DOCKER_COMPOSE) down

# Run stress test with default parameters
stress-test:
	@echo "Running stress test with default parameters..."
	curl -X POST $(STRESS_TEST_URL) \
		-H "Content-Type: application/json" \
		-d '{"seconds": 120, "requests": 1000}'

# Run stress test with custom parameters
stress-test-custom:
	@echo "Running stress test with custom parameters..."
	@echo "Usage: make stress-test-custom SECONDS=60 REQUESTS=500"
	curl -X POST $(STRESS_TEST_URL) \
		-H "Content-Type: application/json" \
		-d '{"seconds": $(or $(SECONDS), 30), "requests": $(or $(REQUESTS), 100)}'

# All-in-one command: build, start, and run test
all: build up
	@echo "Waiting for services to start..."
	sleep 10
	$(MAKE) stress-test

# Clean up everything
clean: down
	@echo "Removing volumes..."
	$(DOCKER_COMPOSE) down -v
	@echo "Removing unused docker resources..."
	docker system prune -f