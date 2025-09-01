#!/bin/bash

# GitHub Repository Scraper Runner for Attio
# Usage: ./run_repo_scraper.sh [config_file] [output_file]

CONFIG=${1:-config.yaml}
OUTPUT=${2:-data/repos_$(date +%Y%m%d_%H%M%S).csv}
LATEST_LINK="data/repos_latest.csv"

# Check if GITHUB_TOKEN is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "⚠️  Warning: GITHUB_TOKEN environment variable not set"
    echo "   Running without authentication (rate limits will apply)"
    echo "   Or use the hardcoded token (already configured)"
    echo ""
fi

# Create data directory if it doesn't exist
mkdir -p data

# Run the scraper
echo "🚀 Starting GitHub Repository Scraper for Attio..."
echo "📋 Config: $CONFIG"
echo "💾 Output: $OUTPUT"
echo ""

python3 github_repo_scraper.py --config "$CONFIG" --out "$OUTPUT"

# Create/update latest symlink if scraping was successful
if [ -f "$OUTPUT" ]; then
    ln -sf "$(basename "$OUTPUT")" "$LATEST_LINK"
    echo ""
    echo "✅ Created symlink: $LATEST_LINK -> $(basename "$OUTPUT")"

    # Show summary stats
    echo ""
    echo "📊 Quick Stats:"
    TOTAL_REPOS=$(tail -n +2 "$OUTPUT" | wc -l | tr -d ' ')
    echo "   Total repositories: $TOTAL_REPOS"

    if [ "$TOTAL_REPOS" -gt 0 ]; then
        # Count repos with topics
        WITH_TOPICS=$(awk -F',' 'NR>1 && $6!=""' "$OUTPUT" | wc -l | tr -d ' ')
        echo "   With topics: $WITH_TOPICS"

        # Count repos by language (top 5)
        echo ""
        echo "   Top languages:"
        tail -n +2 "$OUTPUT" | cut -d',' -f7 | grep -v '^$' | sort | uniq -c | sort -rn | head -5 | while read count lang; do
            echo "   - $lang: $count repos"
        done
    fi
fi
