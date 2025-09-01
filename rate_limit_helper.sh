#!/bin/bash

# Rate Limit Helper Script
# This script helps manage GitHub API rate limits

echo "🔧 GitHub API Rate Limit Helper"
echo "================================"

# Check if token is provided
if [ -z "$1" ]; then
    if [ -z "$GITHUB_TOKEN" ]; then
        echo "❌ No GitHub token provided!"
        echo "Usage: ./rate_limit_helper.sh <github_token>"
        echo "Or set GITHUB_TOKEN environment variable"
        exit 1
    else
        TOKEN="$GITHUB_TOKEN"
    fi
else
    TOKEN="$1"
fi

# Function to check rate limit
check_rate_limit() {
    echo -e "\n📊 Checking rate limit..."
    python check_rate_limit.py "$TOKEN"
}

# Function to wait for rate limit reset
wait_for_reset() {
    while true; do
        RESPONSE=$(curl -s -H "Authorization: token $TOKEN" https://api.github.com/rate_limit)
        REMAINING=$(echo "$RESPONSE" | grep -o '"remaining":[0-9]*' | head -1 | cut -d: -f2)
        RESET=$(echo "$RESPONSE" | grep -o '"reset":[0-9]*' | head -1 | cut -d: -f2)

        if [ "$REMAINING" -gt "0" ]; then
            echo -e "\n✅ Rate limit reset! You have $REMAINING API calls available."
            break
        else
            CURRENT_TIME=$(date +%s)
            WAIT_TIME=$((RESET - CURRENT_TIME))
            WAIT_MINUTES=$((WAIT_TIME / 60))

            echo -ne "\r⏳ Waiting for rate limit reset... ${WAIT_MINUTES} minutes remaining"
            sleep 30
        fi
    done
}

# Main menu
while true; do
    echo -e "\n\nWhat would you like to do?"
    echo "1. Check current rate limit"
    echo "2. Wait for rate limit reset"
    echo "3. Run scraper with smart rate limit handling"
    echo "4. Exit"

    read -p "Enter your choice (1-4): " choice

    case $choice in
        1)
            check_rate_limit
            ;;
        2)
            wait_for_reset
            ;;
        3)
            echo -e "\n🚀 Running scraper with rate limit awareness..."
            # Check rate limit first
            REMAINING=$(curl -s -H "Authorization: token $TOKEN" https://api.github.com/rate_limit | grep -o '"remaining":[0-9]*' | head -1 | cut -d: -f2)

            if [ "$REMAINING" -lt "100" ]; then
                echo "⚠️  Low on API calls ($REMAINING remaining). Waiting for reset..."
                wait_for_reset
            fi

            # Run with conservative settings
            echo "Running with conservative settings to avoid rate limits..."
            python lead_intelligence/scripts/run_intelligence.py \
                --max-repos 10 \
                --max-leads 50 \
                --us-only \
                --english-only
            ;;
        4)
            echo "👋 Goodbye!"
            exit 0
            ;;
        *)
            echo "❌ Invalid choice. Please try again."
            ;;
    esac
done
