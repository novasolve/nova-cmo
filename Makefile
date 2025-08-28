# GitHub Prospect Scraper Makefile
# Usage: make <target>

.PHONY: help install test clean scrape attio segments url lint format check-token setup

# Default target
help: ## Show this help message
	@echo "GitHub Prospect Scraper - Available Commands:"
	@echo "============================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Setup and Installation
install: ## Install dependencies
	pip install -r requirements.txt

setup: ## Setup project (install deps + check token)
	@$(MAKE) install
	@$(MAKE) check-token

check-token: ## Check if GitHub token is configured
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "⚠️  GITHUB_TOKEN not set. Run: export GITHUB_TOKEN=your_token"; \
		echo "   Get a token at: https://github.com/settings/tokens"; \
		exit 1; \
	else \
		echo "✅ GitHub token is configured"; \
	fi

# Main scraping commands
scrape: ## Run default scraper with main config
	python github_prospect_scraper.py --config config.yaml --out data/prospects.csv --out-dir data

attio: ## Generate Attio-ready CSVs (People, Repos, Memberships, Signals)
	@echo "🎯 Generating Attio-ready exports..."
	python github_prospect_scraper.py \
		--config config.yaml \
		--out data/prospects_attio.csv \
		--out-dir exports/attio \
		-n 50
	@echo "✅ Attio exports generated in exports/attio/"
	@echo "📁 Files created:"
	@find exports/attio -name "*.csv" -type f | head -10

segments: ## Run all target segments and combine results
	@echo "🔄 Running all configured segments..."
	python github_prospect_scraper.py \
		--config config.yaml \
		--out data/prospects_all_segments.csv \
		--out-dir exports/segments \
		--run-all-segments
	@echo "✅ All segments processed"

# Quick URL scraping
url: ## Quick URL scraping (usage: make url URL=@username or URL=https://github.com/user/repo)
	@if [ -z "$(URL)" ]; then \
		echo "Usage: make url URL=@username"; \
		echo "   or: make url URL=https://github.com/user/repo"; \
		exit 1; \
	fi
	./scrape_url.sh "$(URL)"

url-save: ## URL scraping with CSV export
	@if [ -z "$(URL)" ]; then \
		echo "Usage: make url-save URL=@username"; \
		exit 1; \
	fi
	./scrape_url.sh "$(URL)" --save

# Specific segment scraping
ai-startups: ## Scrape AI startups segment
	python github_prospect_scraper.py --config configs/ai-startups.yaml --out data/ai_startups.csv --out-dir exports/ai

devtools: ## Scrape devtools segment  
	python github_prospect_scraper.py --config configs/devtools.yaml --out data/devtools.csv --out-dir exports/devtools

web3: ## Scrape web3 segment
	python github_prospect_scraper.py --config configs/web3.yaml --out data/web3.csv --out-dir exports/web3

# Development and testing
test: ## Run a small test scrape
	python github_prospect_scraper.py --config config.yaml --out data/test.csv -n 2

test-url: ## Test URL scraping with a known user
	./scrape_url.sh @octocat

lint: ## Run linting checks
	@echo "🔍 Running linting checks..."
	@python -m py_compile github_prospect_scraper.py
	@echo "✅ Linting passed"

format: ## Format code (if you have black installed)
	@if command -v black >/dev/null 2>&1; then \
		black github_prospect_scraper.py; \
	else \
		echo "⚠️  black not installed. Run: pip install black"; \
	fi

# Data management
clean: ## Clean up generated files
	rm -rf data/*.csv
	rm -rf exports/
	rm -rf __pycache__/
	rm -f *.pyc
	@echo "✅ Cleaned up generated files"

clean-exports: ## Clean only export directories
	rm -rf exports/
	@echo "✅ Cleaned export directories"

backup: ## Backup current data directory
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
	tar -czf "backup_$$timestamp.tar.gz" data/ exports/ 2>/dev/null || true; \
	echo "✅ Backup created: backup_$$timestamp.tar.gz"

# Utility commands
show-config: ## Show current configuration
	@echo "📋 Current Configuration:"
	@echo "========================"
	@if [ -f config.yaml ]; then cat config.yaml; else echo "config.yaml not found"; fi

show-data: ## Show current data files
	@echo "📊 Current Data Files:"
	@echo "====================="
	@find data/ -name "*.csv" -type f -exec ls -lh {} \; 2>/dev/null || echo "No CSV files found in data/"

show-exports: ## Show current export files
	@echo "📦 Current Export Files:"
	@echo "======================="
	@find exports/ -name "*.csv" -type f -exec ls -lh {} \; 2>/dev/null || echo "No export files found"

rate-limit: ## Check GitHub API rate limit
	@if [ -n "$$GITHUB_TOKEN" ]; then \
		curl -s -H "Authorization: Bearer $$GITHUB_TOKEN" https://api.github.com/rate_limit | python -m json.tool; \
	else \
		echo "⚠️  GITHUB_TOKEN not set"; \
	fi

# Production workflows
production: ## Run production scrape with all segments
	@echo "🚀 Running production scrape..."
	@$(MAKE) check-token
	@$(MAKE) clean-exports
	@$(MAKE) segments
	@$(MAKE) attio
	@$(MAKE) backup
	@echo "✅ Production run complete"

quick: ## Quick scrape for testing (5 repos max)
	python github_prospect_scraper.py --config config.yaml --out data/quick.csv -n 5

# Examples
examples: ## Show usage examples
	@echo "📚 Usage Examples:"
	@echo "=================="
	@echo ""
	@echo "Basic scraping:"
	@echo "  make scrape                    # Default scrape"
	@echo "  make attio                     # Generate Attio exports"
	@echo "  make segments                  # Run all segments"
	@echo ""
	@echo "URL scraping:"
	@echo "  make url URL=@octocat          # Analyze GitHub user"
	@echo "  make url URL=https://github.com/microsoft/vscode"
	@echo "  make url-save URL=@username    # Save to CSV"
	@echo ""
	@echo "Specific segments:"
	@echo "  make ai-startups               # AI/ML companies"
	@echo "  make devtools                  # Developer tools"
	@echo "  make web3                      # Blockchain/Web3"
	@echo ""
	@echo "Development:"
	@echo "  make test                      # Small test run"
	@echo "  make clean                     # Clean up files"
	@echo "  make production                # Full production run"

# Create directories
init-dirs: ## Create necessary directories
	mkdir -p data exports/attio exports/segments exports/ai exports/devtools exports/web3
	@echo "✅ Created directory structure"
