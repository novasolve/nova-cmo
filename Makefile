# Lead Intelligence System Makefile
# Usage: make <target>

# Source .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

.PHONY: help install test clean scrape attio url setup intelligence intelligence-dashboard intelligence-analyze attio-setup attio-objects attio-test phase2 phase2-simple phase2-test phase2-integration-test phase2-custom run run-config dry-run wizard icp-wizard icp-list icp-details smoke-tools doctor diag.env diag.api diag.github diag.openai diag.queue diag.smoke diag.export smoke-real smoke-dry tail-api tail-frontend tail-all diagnose diagnose-clean diag-env diag-tools diag-local diag-engine diag-stream diag-collect-logs diag-summary

# Default target
help: ## Show this help message
	@echo "Lead Intelligence System - Available Commands:"
	@echo "=============================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Delegate CMO Agent commands from repo root
run: ## Run CMO Agent campaign (from repo root, pass GOAL="...")
	@$(MAKE) -C cmo_agent run GOAL="$(GOAL)"

run-config: ## Run CMO Agent with YAML config (CONFIG=path). Optional overrides: SET="k=v k2=v2"
	@$(MAKE) -C cmo_agent run-config CONFIG="$(CONFIG)" SET="$(SET)"

dry-run: ## Run CMO Agent in dry-run mode from YAML (CONFIG=path). Optional: SET="k=v k2=v2"
	@$(MAKE) -C cmo_agent dry-run CONFIG="$(CONFIG)" SET="$(SET)"

# Toolbelt smoke tests
smoke-tools: ## Run CMO Agent toolbelt smoke tests
	python cmo_agent/scripts/smoke_test_tools.py

# Setup
install: ## Install dependencies
	pip install -r requirements.txt

setup: ## Setup project (install deps + check token)
	@$(MAKE) install
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "⚠️  GITHUB_TOKEN not set. Run: export GITHUB_TOKEN=your_token"; \
		exit 1; \
	fi

# Main commands
scrape: ## Run default scraper
	python github_prospect_scraper.py --config config.yaml --out data/prospects.csv

attio: ## Generate Attio-ready CSVs
	@echo "🎯 Generating Attio exports..."
	python github_prospect_scraper.py \
		--config config.yaml \
		--out data/prospects_attio.csv \
		--out-dir exports/attio \
		-n 50
	@echo "✅ Done! Check exports/attio/"

# URL scraping
url: ## Quick URL scraping (usage: make url URL=@username)
	@if [ -z "$(URL)" ]; then \
		echo "Usage: make url URL=@username"; \
		exit 1; \
	fi
	./scrape_url.sh "$(URL)"

# Lead Intelligence
intelligence: install ## Run complete lead intelligence cycle (US + English only)
	@echo "🚀 Running Lead Intelligence System..."
	@echo "🎯 Available ICPs (Ideal Customer Profiles):"
	@echo "=============================================="
	@python lead_intelligence/scripts/run_intelligence.py --list-icps || echo "⚠️  Could not load ICP list"
	@echo ""
	@echo "📊 Starting intelligence pipeline..."
	python lead_intelligence/scripts/run_intelligence.py --us-only --english-only $(filter-out $@ install,$(MAKECMDGOALS))

# Enhanced Data Collection (Phase 1)
collect: install ## Enhanced data collection for Phase 1
	@echo "🚀 Running Enhanced Data Collection..."
	@echo "🎯 Available ICPs (Ideal Customer Profiles):"
	@echo "=============================================="
	@python lead_intelligence/core/data_collector.py --icp all --config config.yaml --max-repos 50 --max-leads 25

collect-pypi: install ## Collect PyPI maintainer prospects
	@echo "📦 Collecting PyPI Maintainers..."
	python lead_intelligence/core/data_collector.py --icp icp01_pypi_maintainers --config config.yaml --max-repos 50 --max-leads 25

collect-ml: install ## Collect ML/DS maintainer prospects
	@echo "🧠 Collecting ML/DS Maintainers..."
	python lead_intelligence/core/data_collector.py --icp icp02_ml_ds_maintainers --config config.yaml --max-repos 50 --max-leads 25

collect-saas: install ## Collect SaaS company prospects
	@echo "🚀 Collecting SaaS Company Prospects..."
	python lead_intelligence/core/data_collector.py --icp icp03_seed_series_a_python_saas --config config.yaml --max-repos 30 --max-leads 15

intelligence-demo: install ## Run intelligence system in demo mode (installs deps first)
	@echo "🎭 Running Lead Intelligence System (Demo Mode)..."
	python lead_intelligence/scripts/run_intelligence.py --demo

intelligence-pipeline: install ## Run the complete intelligence pipeline (installs deps first)
	@echo "🚀 Running Complete Lead Intelligence Pipeline..."
	python lead_intelligence/scripts/run_intelligence.py

# Simple natural language targets
intelligence-simple: install ## Run with simple defaults (25 repos, 50 leads)
	@echo "🚀 Running Simple Intelligence (25 repos, 50 leads)..."
	python simple_intelligence.py 25 repos 50 leads

intelligence-quick: install ## Run quick scan (10 repos, 30 days)
	@echo "⚡ Running Quick Intelligence Scan..."
	python simple_intelligence.py 10 repos 30 days

intelligence-pypi: install ## Target PyPI maintainers (50 repos, 100 leads)
	@echo "📦 Targeting PyPI Maintainers..."
	python simple_intelligence.py pypi 50 repos 100 leads

intelligence-ml: install ## Target ML/AI maintainers (75 repos, 150 leads)
	@echo "🧠 Targeting ML/AI Maintainers..."
	python simple_intelligence.py ml 75 repos 150 leads

intelligence-saas: install ## Target SaaS companies (40 repos, 80 leads)
	@echo "🚀 Targeting SaaS Companies..."
	python simple_intelligence.py saas 40 repos 80 leads

# Super simple natural language commands
simple: ## Run simple interface (25 repos, 50 leads)
	@echo "🚀 Running Simple Intelligence..."
	python simple_intelligence.py 25 repos 50 leads

quick: ## Run quick scan (10 repos, 30 days)
	@echo "⚡ Running Quick Intelligence Scan..."
	python simple_intelligence.py 10 repos 30 days

icps: ## List all available ICPs
	@echo "🎯 Available ICPs..."
	python simple_intelligence.py list icps

intelligence-dashboard: install ## Generate intelligence dashboard
	@echo "📊 Generating Intelligence Dashboard..."
	python lead_intelligence/reporting/dashboard.py

intelligence-analyze: install ## Run intelligence analysis on existing data
	@echo "🧠 Running Intelligence Analysis..."
	python lead_intelligence/scripts/run_intelligence.py --phase analyze

intelligence-collect: install ## Run intelligence data collection only
	@echo "📥 Running Intelligence Data Collection..."
	python lead_intelligence/scripts/run_intelligence.py --phase collect

intelligence-test: install ## Test the intelligence system
	@echo "🧪 Testing Lead Intelligence System..."
	python lead_intelligence/scripts/test_intelligence.py

# Phase 2: Data Validation & Quality Assurance
phase2: install ## Run complete Phase 2 validation pipeline
	@echo "🚀 Running Phase 2: Data Validation & Quality Assurance..."
	@if [ -z "$(INPUT)" ]; then \
		echo "Usage: make phase2 INPUT=data/raw_prospects.jsonl"; \
		exit 1; \
	fi
	python run_phase2.py --input "$(INPUT)" --output-dir lead_intelligence/data/phase2_results

phase2-simple: install ## Run Phase 2 with defaults (looks for latest raw prospects)
	@echo "🚀 Running Phase 2: Data Validation & Quality Assurance..."
	@LATEST_FILE=$$(find lead_intelligence/data -name "raw_prospects_*.jsonl" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-); \
	if [ -z "$$LATEST_FILE" ]; then \
		echo "❌ No raw prospects file found. Run Phase 1 first."; \
		exit 1; \
	fi; \
	echo "📥 Using: $$LATEST_FILE"; \
	python run_phase2.py --input "$$LATEST_FILE" --output-dir lead_intelligence/data/phase2_results

phase2-test: install ## Test Phase 2 components
	@echo "🧪 Testing Phase 2 Components..."
	python test_phase2.py

phase2-integration-test: install ## Run Phase 2 integration test
	@echo "🔄 Running Phase 2 Integration Test..."
	python test_phase2.py --integration

phase2-custom: install ## Run Phase 2 with custom settings
	@echo "🚀 Running Phase 2 with Custom Settings..."
	@if [ -z "$(INPUT)" ]; then \
		echo "Usage: make phase2-custom INPUT=data/prospects.jsonl [OUTPUT_DIR=path] [ICP_RELEVANCE=0.7]"; \
		exit 1; \
	fi; \
	OUTPUT_DIR_ARG=""; \
	if [ -n "$(OUTPUT_DIR)" ]; then \
		OUTPUT_DIR_ARG="--output-dir $(OUTPUT_DIR)"; \
	fi; \
	ICP_ARG=""; \
	if [ -n "$(ICP_RELEVANCE)" ]; then \
		ICP_ARG="--icp-relevance-threshold $(ICP_RELEVANCE)"; \
	fi; \
	COMPANY_SIZES_ARG=""; \
	if [ -n "$(COMPANY_SIZES)" ]; then \
		COMPANY_SIZES_ARG="--icp-company-sizes $(COMPANY_SIZES)"; \
	fi; \
	TECH_STACKS_ARG=""; \
	if [ -n "$(TECH_STACKS)" ]; then \
		TECH_STACKS_ARG="--icp-tech-stacks $(TECH_STACKS)"; \
	fi; \
	python run_phase2.py --input "$(INPUT)" $$OUTPUT_DIR_ARG $$ICP_ARG $$COMPANY_SIZES_ARG $$TECH_STACKS_ARG

# Attio Integration
attio-setup: ## Setup Attio CRM integration
	@echo "🔗 Setting up Attio CRM integration..."
	./setup_attio.sh

attio-objects: ## Create required Attio objects (People, Repos, Signals)
	@echo "🏗️  Setting up Attio objects..."
	python setup_attio_objects.py

attio-test: ## Test Attio API connection and integration
	@echo "🧪 Testing Attio API connection..."
	python test_attio.py

# ICP Wizard
wizard: ## Start the Interactive ICP Wizard (requires OPENAI_API_KEY)
	@echo "🎯 Starting Interactive ICP Wizard..."
	@if [ -z "$$OPENAI_API_KEY" ]; then \
		echo "❌ OPENAI_API_KEY not set. Run: export OPENAI_API_KEY=your_key"; \
		exit 1; \
	fi
	python icp_wizard_cli.py

icp-wizard: wizard ## Alias for wizard command

icp-list: ## List all available ICPs
	@echo "🎯 Available ICPs..."
	python icp_wizard_cli.py --list

icp-details: ## Show details for specific ICP (usage: make icp-details ICP=icp01_pypi_maintainers)
	@if [ -z "$(ICP)" ]; then \
		echo "Usage: make icp-details ICP=icp01_pypi_maintainers"; \
		exit 1; \
	fi
	python icp_wizard_cli.py --details $(ICP)

# Development
test: ## Run small test scrape
	python github_prospect_scraper.py --config config.yaml --out data/test.csv -n 2

clean: ## Clean up files
	rm -rf data/*.csv exports/ lead_intelligence/data/ __pycache__/ *.pyc
	@echo "✅ Cleaned up"

clean-intelligence: ## Clean up intelligence data only
	rm -rf lead_intelligence/data/
	@echo "✅ Intelligence data cleaned up"

# Diagnostics (doctor legacy, diagnose preferred)

CMO_API_URL ?= http://localhost:8000
CMO_FRONTEND_URL ?= http://localhost:3000
LOG_API ?= /tmp/cmo_api.log
LOG_FE ?= /tmp/cmo_frontend.log
GOAL ?= Find maintainers of Python repos stars:1000..3000 pushed:>=2025-06-01; prioritize active 90 days; export CSV.
DIAG_TIME_LIMIT ?= 120
DIAG_API_URL ?= http://localhost:8000

# Legacy alias
doctor: ## Legacy: alias to diagnose
	@$(MAKE) diagnose

diag.env: ## Verify required env and tools
	@set -e; \
	[ -n "$$GITHUB_TOKEN" ] || { echo "❌ GITHUB_TOKEN missing"; exit 1; }; \
	[ -n "$$OPENAI_API_KEY" ] || { echo "❌ OPENAI_API_KEY missing"; exit 1; }; \
	command -v jq >/dev/null 2>&1 || { echo "❌ jq not installed (brew install jq)"; exit 1; }; \
	echo "✅ env ok"

diag.api: ## Ping API endpoints
	@set -e; \
	curl -sSf "$(CMO_API_URL)/" >/dev/null && echo "✅ API root ok"; \
	curl -sSf "$(CMO_API_URL)/api/jobs" >/dev/null && echo "✅ /api/jobs ok"

diag.github: ## Validate GitHub token by checking rate limit
	@set -e; \
	curl -sS -H "Authorization: Bearer $$GITHUB_TOKEN" https://api.github.com/rate_limit | jq -e '.resources.core.remaining' >/dev/null \
	&& echo "✅ GitHub token valid (rate limit reachable)" || { echo "❌ GitHub token invalid"; exit 1; }

diag.openai: ## Validate OpenAI key
	@set -e; \
	curl -sS -H "Authorization: Bearer $$OPENAI_API_KEY" https://api.openai.com/v1/models | jq -e '.data' >/dev/null \
	&& echo "✅ OpenAI key valid" || { echo "❌ OpenAI key invalid"; exit 1; }

diag.queue: ## Remind to start workers (non-destructive)
	@echo "ℹ️  Ensure workers are running in another terminal: make -C cmo_agent start-workers"; \
	echo "   (Skipping hard start here to avoid backgrounding processes.)"; \
	echo "✅ queue precheck done"

diag.smoke: ## Create a real job and stream SSE briefly, then fetch summary
	@set -e; \
	jid=$$(curl -sS -X POST "$(CMO_API_URL)/api/jobs" \
	  -H 'Content-Type: application/json' \
	  --data "$$(jq -n --arg g '$(GOAL)' '{goal:$$g, dryRun:false, config_path:null, metadata:{created_by:"doctor", test_type:"doctor", campaign_type:"smoke_test", max_leads:5}}')" \
	  | jq -r '.id'); \
	[ "$$jid" != "null" ] && [ -n "$$jid" ] || { echo "❌ failed to create job"; exit 1; }; \
	echo "▶ Streaming SSE for job $$jid"; \
	( command -v timeout >/dev/null 2>&1 && timeout 30s curl -Ns "$(CMO_API_URL)/api/jobs/$$jid/events" || curl -Ns "$(CMO_API_URL)/api/jobs/$$jid/events" ) | head -n 3 || true; \
	curl -sS "$(CMO_API_URL)/api/jobs/$$jid/summary" | jq -e '.status' >/dev/null \
	&& echo "✅ summary reachable" || { echo "❌ no summary"; exit 1; }

diag.export: ## Export hints (implementation-specific)
	@echo "ℹ️  If your flow writes CSV, verify the export dir was updated (implementation-specific)."; \
	echo "✅ export check complete"

smoke-real: ## Run the diag.smoke target
	@$(MAKE) diag.smoke

smoke-dry: ## Submit a dry-run job via API
	@curl -sS -X POST "$(CMO_API_URL)/api/jobs" \
	  -H 'Content-Type: application/json' \
	  --data "$$(jq -n --arg g '$(GOAL)' '{goal:$$g, dryRun:true, metadata:{created_by:"smoke_dry"}}')" | jq

tail-api: ## Tail API log
	@echo "Tailing $(LOG_API)"; [ -f "$(LOG_API)" ] && tail -f "$(LOG_API)" || echo "No API log at $(LOG_API)"

tail-frontend: ## Tail frontend log
	@echo "Tailing $(LOG_FE)"; [ -f "$(LOG_FE)" ] && tail -f "$(LOG_FE)" || echo "No FE log at $(LOG_FE)"

tail-all: ## Tail both logs
	@$(MAKE) -j2 tail-api tail-frontend

# -------- Diagnose (preferred) --------
diagnose: ## One-command triage: env + tools + local dry-run + engine + SSE + logs
	@set -euo pipefail; \
	DIAG_DIR="$${DIAG_DIR:-/tmp/cmo_diag_$$(date +%Y%m%d_%H%M%S)}"; \
	mkdir -p "$$DIAG_DIR"; \
	echo "==> DIAG_DIR=$$DIAG_DIR"; \
	$(MAKE) diag-env DIAG_DIR="$$DIAG_DIR"; \
	$(MAKE) diag-tools DIAG_DIR="$$DIAG_DIR"; \
	$(MAKE) diag-local DIAG_DIR="$$DIAG_DIR" GOAL="$(GOAL)" CONFIG="$(CONFIG)"; \
	$(MAKE) diag-engine DIAG_DIR="$$DIAG_DIR" GOAL="$(GOAL)" DIAG_TIME_LIMIT="$(DIAG_TIME_LIMIT)"; \
	$(MAKE) diag-stream DIAG_DIR="$$DIAG_DIR" DIAG_API_URL="$(DIAG_API_URL)"; \
	$(MAKE) diag-collect-logs DIAG_DIR="$$DIAG_DIR"; \
	$(MAKE) diag-summary DIAG_DIR="$$DIAG_DIR"; \
	echo ""; echo "✅ Diagnose complete. Artifacts: $$DIAG_DIR"

diagnose-clean: ## Remove the last created diag folder (pass DIAG_DIR=... to target a specific one)
	@set -e; \
	if [ -z "$${DIAG_DIR:-}" ]; then \
		ls -1dt /tmp/cmo_diag_* 2>/dev/null | head -1 | xargs -I {} rm -rf "{}" || true; \
	else rm -rf "$$DIAG_DIR"; fi; \
	echo "🧹 Cleaned."

diag-env:
	@set -e; \
	{ \
	  echo "# Env checks"; \
	  test -n "$${GITHUB_TOKEN:-}" && echo "GITHUB_TOKEN: present" || { echo "GITHUB_TOKEN: MISSING"; exit 11; }; \
	} | tee "$(DIAG_DIR)/env.txt" >/dev/null

diag-tools:
	@set -e; \
	echo "==> check-tools"; \
	$(MAKE) -C cmo_agent check-tools | tee "$(DIAG_DIR)/check-tools.log" >/dev/null || { echo "Tool check failed"; exit 12; }; \
	echo "==> smoke-tools"; \
	$(MAKE) smoke-tools | tee "$(DIAG_DIR)/smoke-tools.log" >/dev/null || { echo "Smoke-tools failed"; exit 13; }

diag-local:
	@set -e; \
	echo "==> local dry-run"; \
	if [ -n "$(CONFIG)" ]; then \
	  echo "CONFIG=$(CONFIG)"; \
	  $(MAKE) run-config CONFIG="$(CONFIG)" GOAL="$(GOAL)" \
	    | tee "$(DIAG_DIR)/local_dry_run.log" >/dev/null; \
	else \
	  $(MAKE) dry-run GOAL="$(GOAL)" \
	    | tee "$(DIAG_DIR)/local_dry_run.log" >/dev/null; \
	fi

diag-engine:
	@set -e; \
	echo "==> engine one-shot run-job"; \
	$(MAKE) -s -C cmo_agent run-job GOAL="$(GOAL)" \
	  | tee "$(DIAG_DIR)/engine_run_job.log" >/dev/null || true; \
	echo "==> capture latest JOB_ID"; \
	make -s -C cmo_agent list-jobs | tee "$(DIAG_DIR)/list-jobs.log" >/dev/null; \
	JOB_ID=$$(sed -n 's/.*\(cmo-[A-Za-z0-9_-]\{6,64\}\).*/\1/p' "$(DIAG_DIR)/list-jobs.log" | tail -1); \
	if [ -z "$$JOB_ID" ]; then echo "Could not detect JOB_ID"; exit 14; fi; \
	echo "$$JOB_ID" > "$(DIAG_DIR)/JOB_ID"; \
	echo "JOB_ID=$$JOB_ID"; \
	echo "==> poll job-status (timeout $(DIAG_TIME_LIMIT)s)"; \
	SECS=0; STATUS=""; \
	while [ $$SECS -lt $(DIAG_TIME_LIMIT) ]; do \
	  make -s -C cmo_agent job-status JOB_ID="$$JOB_ID" \
	    | tee "$(DIAG_DIR)/job-status.log" >/dev/null; \
	  STATUS=$$(grep -Eo 'completed|failed|running|queued' "$(DIAG_DIR)/job-status.log" | tail -1 || true); \
	  [ "$$STATUS" = "completed" ] && break; \
	  [ "$$STATUS" = "failed" ] && { echo "Job failed"; exit 14; }; \
	  sleep 2; SECS=$$((SECS+2)); \
	done; \
	if [ "$$STATUS" != "completed" ]; then echo "Job did not complete in time"; exit 14; fi

diag-stream:
	@set -e; \
	echo "==> SSE probe"; \
	JOB_ID=$$(cat "$(DIAG_DIR)/JOB_ID"); \
	curl -s -D "$(DIAG_DIR)/sse_headers.txt" -o /dev/null "$(DIAG_API_URL)/api/jobs/$$JOB_ID/events" || true; \
	if ! grep -q "HTTP/1.1 200" "$(DIAG_DIR)/sse_headers.txt"; then \
	  echo "SSE endpoint not returning 200 (check API / dev.sh)"; \
	fi

diag-collect-logs:
	@set -e; \
	[ -f /tmp/cmo_api.log ] && cp /tmp/cmo_api.log "$(DIAG_DIR)/api.log" || true; \
	[ -f /tmp/cmo_frontend.log ] && cp /tmp/cmo_frontend.log "$(DIAG_DIR)/frontend.log" || true

diag-summary:
	@set -e; \
	echo "==> summary"; \
	JOB_ID=$$(cat "$(DIAG_DIR)/JOB_ID" 2>/dev/null || true); \
	STATUS=$$(grep -Eo 'completed|failed|running|queued' "$(DIAG_DIR)/job-status.log" 2>/dev/null | tail -1 || true); \
	{ \
	  echo "# Diagnose Summary"; \
	  echo "Artifacts: $(DIAG_DIR)"; \
	  echo "JOB_ID: $${JOB_ID:-n/a}"; \
	  echo "Engine status: $${STATUS:-n/a}"; \
	  echo ""; \
	  echo "Next actions:"; \
	  if grep -q "MISSING" "$(DIAG_DIR)/env.txt"; then \
	    echo "- Export required env vars (see env.txt) and re-run diagnose."; \
	  fi; \
	  if grep -qi "error" "$(DIAG_DIR)/check-tools.log" 2>/dev/null; then \
	    echo "- Fix toolbelt failures (see check-tools.log)."; \
	  fi; \
	  if grep -qi "error" "$(DIAG_DIR)/smoke-tools.log" 2>/dev/null; then \
	    echo "- Investigate smoke-tools failures (see smoke-tools.log)."; \
	  fi; \
	  if [ "$${STATUS:-}" != "completed" ]; then \
	    echo "- Use engine flow manually: make -C cmo_agent start-workers; make -C cmo_agent submit-job GOAL=\"$(GOAL)\"; make -C cmo_agent list-jobs; make -C cmo_agent job-status JOB_ID=<id>"; \
	  else \
	    echo "- Engine completed. If output looks empty, re-run dry-run and inspect local_dry_run.log for discovery/email stats."; \
	  fi; \
	} | tee "$(DIAG_DIR)/SUMMARY.txt" >/dev/null

check-entrypoints: ## Check that critical entrypoints exist
	python tools/check_entrypoints.py

smoke-test: ## Run smoke tests to verify critical functionality
	PYTHONPATH=. python tests/test_smoke.py

check-env: ## Validate environment variables
	python tools/check_env.py

check-env-dry: ## Validate environment for dry-run mode only
	python tools/check_env.py --dry-run

# Catch-all target to prevent "make: *** No rule to make target" errors
%:
	@:
