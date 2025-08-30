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
intelligence: ## Run complete lead intelligence cycle
	@echo "🚀 Running Lead Intelligence System..."
	python lead_intelligence/scripts/run_intelligence.py

intelligence-demo: ## Run intelligence system in demo mode (no GitHub token needed)
	@echo "🎭 Running Lead Intelligence System (Demo Mode)..."
	python lead_intelligence/scripts/run_intelligence.py --demo

intelligence-pipeline: ## Run the complete intelligence pipeline (same as make intelligence)
	@echo "🚀 Running Complete Lead Intelligence Pipeline..."
	python lead_intelligence/scripts/run_intelligence.py

intelligence-dashboard: ## Generate intelligence dashboard
	@echo "📊 Generating Intelligence Dashboard..."
	python lead_intelligence/reporting/dashboard.py

intelligence-analyze: ## Run intelligence analysis on existing data
	@echo "🧠 Running Intelligence Analysis..."
	python lead_intelligence/scripts/run_intelligence.py --phase analyze

intelligence-collect: ## Run intelligence data collection only
	@echo "📥 Running Intelligence Data Collection..."
	python lead_intelligence/scripts/run_intelligence.py --phase collect

intelligence-test: ## Test the intelligence system
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
