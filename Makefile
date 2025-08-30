# Lead Intelligence System Makefile
# Usage: make <target>

.PHONY: help install test clean scrape attio url setup intelligence intelligence-dashboard intelligence-analyze attio-setup attio-objects attio-test

# Default target
help: ## Show this help message
	@echo "Lead Intelligence System - Available Commands:"
	@echo "=============================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

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
	@GITHUB_TOKEN=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 python lead_intelligence/scripts/run_intelligence.py --list-icps || echo "⚠️  Could not load ICP list"
	@echo ""
	@echo "📊 Starting intelligence pipeline..."
	GITHUB_TOKEN=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 python lead_intelligence/scripts/run_intelligence.py --us-only --english-only $(filter-out $@ install,$(MAKECMDGOALS))

# Enhanced Data Collection (Phase 1)
collect: install ## Enhanced data collection for Phase 1
	@echo "🚀 Running Enhanced Data Collection..."
	@echo "🎯 Available ICPs (Ideal Customer Profiles):"
	@echo "=============================================="
	@GITHUB_TOKEN=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 python lead_intelligence/core/data_collector.py --icp all --config config.yaml --max-repos 50 --max-leads 25

collect-pypi: install ## Collect PyPI maintainer prospects
	@echo "📦 Collecting PyPI Maintainers..."
	GITHUB_TOKEN=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 python lead_intelligence/core/data_collector.py --icp icp01_pypi_maintainers --config config.yaml --max-repos 50 --max-leads 25

collect-ml: install ## Collect ML/DS maintainer prospects
	@echo "🧠 Collecting ML/DS Maintainers..."
	GITHUB_TOKEN=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 python lead_intelligence/core/data_collector.py --icp icp02_ml_ds_maintainers --config config.yaml --max-repos 50 --max-leads 25

collect-saas: install ## Collect SaaS company prospects
	@echo "🚀 Collecting SaaS Company Prospects..."
	GITHUB_TOKEN=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 python lead_intelligence/core/data_collector.py --icp icp03_seed_series_a_python_saas --config config.yaml --max-repos 30 --max-leads 15

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

# Development
test: ## Run small test scrape
	python github_prospect_scraper.py --config config.yaml --out data/test.csv -n 2

clean: ## Clean up files
	rm -rf data/*.csv exports/ lead_intelligence/data/ __pycache__/ *.pyc
	@echo "✅ Cleaned up"

clean-intelligence: ## Clean up intelligence data only
	rm -rf lead_intelligence/data/
	@echo "✅ Intelligence data cleaned up"

# Catch-all target to prevent "make: *** No rule to make target" errors
%:
	@:
