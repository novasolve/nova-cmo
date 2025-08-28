# GitHub Prospect Scraper Makefile
# Usage: make <target>

.PHONY: help install test clean scrape attio url setup

# Default target
help: ## Show this help message
	@echo "GitHub Prospect Scraper - Available Commands:"
	@echo "============================================="
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

# Development
test: ## Run small test scrape
	python github_prospect_scraper.py --config config.yaml --out data/test.csv -n 2

clean: ## Clean up files
	rm -rf data/*.csv exports/ __pycache__/ *.pyc
	@echo "✅ Cleaned up"
