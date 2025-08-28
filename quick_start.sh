#!/bin/bash

# Quick Start Demo Script
# This shows how to use the GitHub scraper end-to-end

echo "🚀 GitHub Prospect Scraper - Quick Start Demo"
echo "==========================================="
echo ""

# Check dependencies
echo "📋 Checking dependencies..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GITHUB_TOKEN not set!"
    echo ""
    echo "To fix this:"
    echo "1. Go to https://github.com/settings/tokens"
    echo "2. Generate a new token with 'public_repo' scope"
    echo "3. Run: export GITHUB_TOKEN=ghp_your_token_here"
    echo ""
    exit 1
fi

echo "✅ Dependencies OK"
echo ""

# Install Python packages
echo "📦 Installing Python packages..."
pip install -r requirements.txt > /dev/null 2>&1
echo "✅ Packages installed"
echo ""

# Create directories
mkdir -p data
mkdir -p exports

# Demo run with small limits
echo "🔍 Running scraper with demo configuration..."
cat > demo_config.yaml << EOF
search:
  query: 'language:python stars:>1000 pushed:>2024-01-01 topic:ai'
  sort: 'updated'
  order: 'desc'
  per_page: 10

filters:
  activity_days: 30

limits:
  max_repos: 3
  per_repo_prs: 3
  per_repo_commits: 2
  max_people: 20

delay: 1
EOF

# Run the scraper
echo ""
python github_prospect_scraper.py --config demo_config.yaml --out data/demo_prospects.csv

# Check if successful
if [ -f "data/demo_prospects.csv" ]; then
    echo ""
    echo "📊 Scraping complete! Let's look at the results..."
    echo ""
    
    # Show preview
    echo "First 5 prospects:"
    echo "=================="
    head -n 6 data/demo_prospects.csv | column -t -s, | head -20
    echo ""
    
    # Count results
    TOTAL=$(tail -n +2 data/demo_prospects.csv | wc -l)
    echo "Total prospects found: $TOTAL"
    echo ""
    
    # Enrich emails
    echo "📧 Running email enrichment..."
    python enrich_emails.py data/demo_prospects.csv -o data/demo_prospects_enriched.csv
    echo ""
    
    # Create summary
    echo "📈 Summary of prospects by repository:"
    echo "====================================="
    tail -n +2 data/demo_prospects.csv | cut -d, -f6 | sort | uniq -c | sort -rn
    echo ""
    
    echo "✅ Quick start complete!"
    echo ""
    echo "📁 Output files:"
    echo "  - data/demo_prospects.csv (raw scraper output)"
    echo "  - data/demo_prospects_enriched.csv (with email patterns)"
    echo "  - demo_config.yaml (configuration used)"
    echo ""
    echo "🎯 Next steps:"
    echo "1. Edit config.yaml to target your market"
    echo "2. Run: ./run_scraper.sh"
    echo "3. Use configs/ai-startups.yaml, configs/devtools.yaml, etc. for specific segments"
    echo "4. Enrich emails with professional services"
    echo "5. Import to your CRM/outreach tool"
    echo ""
else
    echo "❌ Something went wrong. Check the error messages above."
fi

# Cleanup
rm -f demo_config.yaml
