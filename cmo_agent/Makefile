# CMO Agent Makefile

.PHONY: install run test clean

# Installation
install:
	pip install -r requirements.txt

# Development setup
dev-setup: install
	mkdir -p logs exports data
	cp config/default.yaml config/dev.yaml

# Run agent
run:
	python scripts/run_agent.py "$(GOAL)"

# Run with custom config
run-config:
	python scripts/run_agent.py --config $(CONFIG) "$(GOAL)"

# Dry run
dry-run:
	python scripts/run_agent.py --dry-run "$(GOAL)"

# Test campaign (small scale)
test-campaign: dev-setup
	python scripts/run_agent.py --dry-run "Find 10 Python repos with CI, extract 5 maintainers each"

# Clean up generated files
clean:
	rm -rf logs/*.log
	rm -rf exports/*.csv
	rm -rf data/*.json

# Full cleanup including config
clean-all: clean
	rm -rf config/dev.yaml
	rm -rf data/
	rm -rf exports/
	rm -rf logs/

# Create new campaign config
new-config:
	cp config/default.yaml config/$(NAME).yaml
	@echo "Created config/$(NAME).yaml - edit it for your campaign"

# Show help
help:
	@echo "CMO Agent - Available commands:"
	@echo "  make install          - Install dependencies"
	@echo "  make dev-setup        - Setup development environment"
	@echo "  make run GOAL='...'   - Run campaign with default config"
	@echo "  make run-config CONFIG=config/name.yaml GOAL='...'"
	@echo "  make dry-run GOAL='...' - Run campaign in dry-run mode"
	@echo "  make test-campaign    - Run a small test campaign"
	@echo "  make clean            - Clean generated files"
	@echo "  make new-config NAME=config_name - Create new campaign config"
