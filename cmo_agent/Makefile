# CMO Agent Makefile

.PHONY: install run run-config dry-run test dev-setup test-campaign test-persistence test-queue demo-processing submit-job run-job start-workers job-status list-jobs clean clean-all new-config help

PYTHONPATH?=$(shell pwd)/..
GOAL?=$(goal)

# Installation
install:
	pip install -r requirements.txt

# Development setup
dev-setup: install
	mkdir -p logs exports data
	cp config/default.yaml config/dev.yaml

# Run agent
run:
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.run_agent "$(GOAL)"

# Run with custom config
run-config:
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.run_agent --config $(CONFIG) "$(GOAL)"

# Dry run
dry-run:
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.run_agent --dry-run "$(GOAL)"

# Test campaign (small scale)
test-campaign: dev-setup
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.run_agent --dry-run "Find 10 Python repos with CI, extract 5 maintainers each"

# Test execution engine persistence
test-persistence:
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.test_execution_with_persistence

# Test persistent queue functionality
test-queue:
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.test_persistent_queue

# Demo job processing (shows actual execution)
demo-processing:
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.demo_job_processing

# Submit a job to execution engine (just queue it)
submit-job:
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.submit_job_simple "$(GOAL)"

# Submit and process a job immediately
run-job:
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.run_execution --job "$(GOAL)" --start-workers

# Start worker pool only (no job submission)
start-workers:
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.run_execution --workers-only

# Check job status
job-status:
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.check_job_status $(JOB_ID)

# List all jobs
list-jobs:
	PYTHONPATH=$(PYTHONPATH) python -m cmo_agent.scripts.check_job_status

# Clean up generated files
clean:
	rm -rf logs/*.log
	rm -rf exports/*.csv
	rm -rf data/*.json
	rm -rf data/jobs/*.json

# Full cleanup including config and jobs
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
	@echo "  make test-persistence - Test job persistence across script runs"
	@echo "  make test-queue       - Test persistent queue functionality"
	@echo "  make demo-processing  - Demo job submission and actual processing"
	@echo "  make submit-job GOAL='...' - Submit job to execution engine (queue only)"
	@echo "  make run-job GOAL='...'    - Submit and process job immediately"
	@echo "  make job-status JOB_ID=job_id - Check job status"
	@echo "  make list-jobs        - List all jobs"
	@echo "  make clean            - Clean generated files"
	@echo "  make new-config NAME=config_name - Create new campaign config"
