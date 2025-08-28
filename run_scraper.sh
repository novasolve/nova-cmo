#!/bin/bash

# GitHub Prospect Scraper Runner
# This script runs the GitHub prospect scraper with common configurations

set -e  # Exit immediately on error

# Check if GITHUB_TOKEN is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Error: GITHUB_TOKEN not set"
    echo "Please run: export GITHUB_TOKEN=<your_github_token>"
    echo "Get a token at: https://github.com/settings/tokens"
    exit 1
fi

# Test if the GitHub token is valid
echo "🔑 Testing GitHub token..."
# Try Bearer first (fine-grained + classic), then fallback to token if needed
TOKEN_TEST=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github.v3+json" -H "User-Agent: leads-scraper/1.0" https://api.github.com/user)
if echo "$TOKEN_TEST" | grep -q 'Bad credentials'; then
    TOKEN_TEST=$(curl -s -H "Authorization: token $GITHUB_TOKEN" -H "Accept: application/vnd.github.v3+json" -H "User-Agent: leads-scraper/1.0" https://api.github.com/user)
fi

if echo "$TOKEN_TEST" | grep -q '"message": "Bad credentials"'; then
    echo "❌ Error: GitHub token is invalid (401 Bad credentials)"
    echo ""
    echo "🔧 To fix this:"
    echo "1. Go to: https://github.com/settings/tokens"
    echo "2. For classic token: 'Generate new token (classic)' with scopes 'repo' and 'user:email'"
    echo "   Or use a fine-grained token with 'Read-only access to public repositories' and 'Read user profile'"
    echo "4. Copy the new token"
    echo "5. Run: export GITHUB_TOKEN=your_new_token"
    echo ""
    echo "Or use the setup script: ./setup_token.sh"
    exit 1
elif echo "$TOKEN_TEST" | grep -q '"login"'; then
    TOKEN_USER=$(echo "$TOKEN_TEST" | grep -o '"login": "[^"]*"' | cut -d'"' -f4)
    echo "✅ Token valid for user: $TOKEN_USER"
else
    echo "❌ Error: Unable to validate GitHub token"
    echo "Response: $TOKEN_TEST"
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p data

# Default values
CONFIG_FILE="configs/main.yaml"
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
            echo "  -c, --config FILE    Config file (default: configs/main.yaml)"
            echo "  -o, --output FILE    Output CSV file (default: data/prospects_TIMESTAMP.csv)"
            echo "  -n, --max-repos N    Maximum number of repos to process (limit scope for testing)"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Example: $0 -n 3   # Process only first 3 repos and get a small sample of prospects"
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo "Run '$0 --help' for usage."
            exit 1
            ;;
    esac
done

# Check that the config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: Config file '$CONFIG_FILE' not found"
    exit 1
fi

# Show configuration being used
echo "🚀 GitHub Prospect Scraper"
echo "========================="
echo "📋 Config: $CONFIG_FILE"
echo "💾 Output: $OUTPUT_FILE"
if [ -n "$MAX_REPOS" ]; then
    echo "🔢 Max repos: $MAX_REPOS"
fi
echo ""

# Run the scraper (build arguments without using eval for safety)
if [ -n "$MAX_REPOS" ]; then
    python github_prospect_scraper.py --config "$CONFIG_FILE" --out "$OUTPUT_FILE" -n "$MAX_REPOS"
else
    python github_prospect_scraper.py --config "$CONFIG_FILE" --out "$OUTPUT_FILE"
fi

# Show results summary and preview
if [ -f "$OUTPUT_FILE" ]; then
    PROSPECT_COUNT=$(tail -n +2 "$OUTPUT_FILE" | wc -l)  # count lines excluding header
    echo ""
    echo "📊 Summary:"
    echo "- Total prospects: $PROSPECT_COUNT"
    echo "- Output file: $OUTPUT_FILE"
    # Create/update a symlink for easy access to the latest results
    ln -sf "$(basename "$OUTPUT_FILE")" data/prospects_latest.csv
    echo "- Latest symlink: data/prospects_latest.csv"

    # If prospects were found, display the first 3 for quick preview
    if [ "$PROSPECT_COUNT" -gt 0 ]; then
        echo ""
        echo "👀 First 3 prospects (preview):"
        echo "────────────────────────────────────────────────────────────────────────────────"
        
        # Extract and display key fields in a readable format
        tail -n +2 "$OUTPUT_FILE" | head -n 3 | while IFS=',' read -r lead_id login id node_id name company email_public_commit email_profile location bio pronouns repo_full_name repo_description signal signal_type signal_at topics language stars forks watchers github_user_url github_repo_url avatar_url html_url api_url followers_url following_url gists_url starred_url subscriptions_url organizations_url repos_url events_url received_events_url twitter_username blog linkedin_username hireable public_repos public_gists followers following total_private_repos owned_private_repos private_gists disk_usage collaborators contributions_last_year total_contributions longest_streak current_streak created_at updated_at type site_admin gravatar_id suspended_at plan_name plan_space plan_collaborators plan_private_repos two_factor_authentication has_organization_projects has_repository_projects; do
            echo "🧑 Name: ${name:-$login}"
            echo "🔗 Profile: $github_user_url"
            echo "🏢 Company: ${company:-"Not specified"}"
            echo "📧 Email: ${email_profile:-${email_public_commit:-"Not found"}}"
            echo "📍 Location: ${location:-"Not specified"}"
            echo "🔗 LinkedIn: ${linkedin_username:-"Not found"}"
            echo "⭐ GitHub Stats: $followers followers, $public_repos repos"
            echo "📦 Repository: $repo_full_name ($stars stars)"
            echo "🎯 Signal: $signal"
            echo "📅 Activity: $signal_at"
            echo ""
        done
        echo "────────────────────────────────────────────────────────────────────────────────"
    fi
fi

# Locate the latest Attio export folder and show per-object counts
LATEST_EXPORT_DIR=$(ls -dt data/export_* 2>/dev/null | head -1 || true)
if [ -n "$LATEST_EXPORT_DIR" ] && [ -d "$LATEST_EXPORT_DIR" ]; then
    echo ""
    echo "📦 Attio import package: $LATEST_EXPORT_DIR"
    ln -sfn "$LATEST_EXPORT_DIR" data/attio_latest
    echo "- Latest Attio symlink: data/attio_latest"

    PEOPLE_CSV="$LATEST_EXPORT_DIR/People/People.csv"
    REPOS_CSV="$LATEST_EXPORT_DIR/Repos/Repos.csv"
    MEMBERSHIP_CSV="$LATEST_EXPORT_DIR/Memberships/Membership.csv"
    SIGNALS_CSV="$LATEST_EXPORT_DIR/Signals/Signals.csv"

    count_csv() {
        if [ -f "$1" ]; then
            echo $(($(wc -l < "$1") - 1))
        else
            echo 0
        fi
    }

    echo "👥 People rows:       $(count_csv "$PEOPLE_CSV")  ($PEOPLE_CSV)"
    echo "📚 Repos rows:        $(count_csv "$REPOS_CSV")  ($REPOS_CSV)"
    echo "🔗 Membership rows:   $(count_csv "$MEMBERSHIP_CSV")  ($MEMBERSHIP_CSV)"
    echo "🔔 Signals rows:      $(count_csv "$SIGNALS_CSV")  ($SIGNALS_CSV)"
else
    echo ""
    echo "⚠️  No Attio export folder found. If this is unexpected, ensure the run did find any repos/prospects."
fi
