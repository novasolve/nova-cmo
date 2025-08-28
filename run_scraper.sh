#!/bin/bash

# GitHub Prospect Scraper Runner
# This script makes it easy to run the scraper with common configurations

set -e

# Check if GITHUB_TOKEN is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Error: GITHUB_TOKEN not set"
    echo "Please run: export GITHUB_TOKEN=ghp_yourtoken"
    echo "Get a token at: https://github.com/settings/tokens"
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p data

# Default values
CONFIG_FILE="config.yaml"
OUTPUT_FILE="data/prospects_$(date +%Y%m%d_%H%M%S).csv"
MAX_REPOS=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -n|--max-repos)
            MAX_REPOS="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -c, --config FILE    Config file (default: config.yaml)"
            echo "  -o, --output FILE    Output CSV file (default: data/prospects_TIMESTAMP.csv)"
            echo "  -n, --max-repos N    Maximum number of repos to process"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run $0 --help for usage"
            exit 1
            ;;
    esac
done

# Show configuration
echo "🚀 GitHub Prospect Scraper"
echo "========================="
echo "📋 Config: $CONFIG_FILE"
echo "💾 Output: $OUTPUT_FILE"
if [ -n "$MAX_REPOS" ]; then
    echo "🔢 Max repos: $MAX_REPOS"
fi
echo ""

# Build command with optional -n argument
CMD="python github_prospect_scraper.py --config \"$CONFIG_FILE\" --out \"$OUTPUT_FILE\""
if [ -n "$MAX_REPOS" ]; then
    CMD="$CMD -n $MAX_REPOS"
fi

# Run the scraper
eval $CMD

# Show results
if [ -f "$OUTPUT_FILE" ]; then
    PROSPECT_COUNT=$(tail -n +2 "$OUTPUT_FILE" | wc -l)
    echo ""
    echo "📊 Summary:"
    echo "- Total prospects: $PROSPECT_COUNT"
    echo "- Output file: $OUTPUT_FILE"
    
    # Create a latest symlink for easy access
    ln -sf "$(basename "$OUTPUT_FILE")" data/prospects_latest.csv
    echo "- Latest symlink: data/prospects_latest.csv"
fi
