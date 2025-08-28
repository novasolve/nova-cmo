#!/bin/bash

# GitHub URL Scraper - Quick CLI wrapper
# Usage: ./scrape_url.sh <github_url>

if [ $# -eq 0 ]; then
    echo "🎯 GitHub Prospect Scraper - URL Mode"
    echo "====================================="
    echo ""
    echo "Usage: $0 <github_url>"
    echo ""
    echo "Examples:"
    echo "  $0 https://github.com/username"
    echo "  $0 https://github.com/owner/repo"
    echo "  $0 @username"
    echo ""
    echo "Options:"
    echo "  --save    Save results to CSV (default: print only)"
    echo "  --help    Show this help message"
    echo ""
    exit 1
fi

URL="$1"
SAVE_MODE=""

# Check for --save flag
if [[ "$2" == "--save" ]] || [[ "$1" == "--save" && -n "$3" ]]; then
    SAVE_MODE="--out data/url_prospects_$(date +%Y%m%d_%H%M%S).csv"
    if [[ "$1" == "--save" ]]; then
        URL="$3"
    fi
else
    SAVE_MODE="--print-only"
fi

# Handle @username format
if [[ "$URL" == @* ]]; then
    URL="https://github.com/${URL:1}"
fi

echo "🚀 Scraping GitHub URL: $URL"
echo ""

# Run the scraper
python github_prospect_scraper.py --url "$URL" $SAVE_MODE

echo ""
echo "✅ Done! Use --save flag to export to CSV"
