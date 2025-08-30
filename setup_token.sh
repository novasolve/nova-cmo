#!/bin/bash

echo "🔐 GitHub Token Setup Helper"
echo "=========================="
echo ""
echo "Your current token is invalid (401: Bad credentials)"
echo ""
echo "To fix this, choose ONE of the following token types:"
echo ""
echo "=== OPTION 1: Classic Personal Access Token ==="
echo "1. Go to: https://github.com/settings/tokens"
echo "2. Click 'Generate new token (classic)'"
echo "3. Name it: 'Growth Scraper'"
echo "4. Select these scopes:"
echo "   ✓ repo (Full control of private repositories)"
echo "   ✓ user (Update ALL user data)"
echo "   - This includes: read:user, user:email, user:follow"
echo "5. Click 'Generate token'"
echo "6. Copy the token (starts with 'ghp_')"
echo ""
echo "=== OPTION 2: Fine-grained Personal Access Token ==="
echo "1. Go to: https://github.com/settings/tokens"
echo "2. Click 'Generate new token'"
echo "3. Click 'Generate new token (fine-grained)'"
echo "4. Name it: 'Growth Scraper'"
echo "5. Select repository access: 'All repositories'"
echo "6. Select permissions:"
echo "   ✓ Repository permissions:"
echo "     - Contents: Read"
echo "     - Metadata: Read"
echo "     - Pull requests: Read"
echo "   ✓ Account permissions:"
echo "     - Email addresses: Read"
echo "7. Click 'Generate token'"
echo "8. Copy the token (starts with 'github_token_')"
echo ""
echo "=== SETTING UP THE TOKEN ==="
echo "Run this command with your token:"
echo ""
echo "   export GITHUB_TOKEN='your_new_token_here'"
echo ""
echo "8. Test it works:"
echo "   python test_token.py"
echo ""
echo "9. Then run the scraper:"
echo "   ./run_scraper.sh -n 2"
echo ""
echo "Current token status:"
echo "- Token: ${GITHUB_TOKEN:0:10}...${GITHUB_TOKEN: -4}"
echo "- Length: ${#GITHUB_TOKEN}"
echo ""

# Quick test

# Attio setup section
if [ -z "$ATTIO_API_TOKEN" ] || [ -z "$ATTIO_WORKSPACE_ID" ]; then
    echo ""
    echo "=== ATTIO SETUP (Optional but recommended) ==="
    echo "To enable CRM integration with Attio:"
    echo "1. Go to: https://app.attio.com/settings/developers/api-keys"
    echo "2. Create a new API key with the following scopes:"
    echo "   ✓ objects:read"
    echo "   ✓ objects:write"
    echo "   ✓ records:read"
    echo "   ✓ records:write"
    echo "3. Copy your API key and Workspace ID"
    echo ""
    echo "Set up with these commands:"
    echo "   export ATTIO_API_TOKEN='your_attio_api_key_here'"
    echo "   export ATTIO_WORKSPACE_ID='your_workspace_id_here'"
    echo ""
    echo "Current Attio status:"
    echo "- API Token: ${ATTIO_API_TOKEN:0:10}...${ATTIO_API_TOKEN: -4}"
    echo "- Workspace ID: ${ATTIO_WORKSPACE_ID:0:10}...${ATTIO_WORKSPACE_ID: -4}"
else
    echo ""
    echo "✅ Attio is configured!"
    echo "- API Token: ${ATTIO_API_TOKEN:0:10}...${ATTIO_API_TOKEN: -4}"
    echo "- Workspace ID: ${ATTIO_WORKSPACE_ID:0:10}...${ATTIO_WORKSPACE_ID: -4}"
fi
echo "Testing current token..."

# Detect token format and use appropriate auth method
if [[ $GITHUB_TOKEN == ghp_* ]]; then
    echo "📝 Detected classic token (ghp_), using 'token' auth..."
    resp=$(curl -s -H "Authorization: token $GITHUB_TOKEN" -H "User-Agent: leads-scraper/1.0" https://api.github.com/user)
elif [[ $GITHUB_TOKEN == github_token_* ]]; then
    echo "📝 Detected fine-grained token (github_token_), using 'Bearer' auth..."
    resp=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" -H "User-Agent: leads-scraper/1.0" https://api.github.com/user)
else
    echo "📝 Unknown token format, trying 'Bearer' auth first..."
    resp=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" -H "User-Agent: leads-scraper/1.0" https://api.github.com/user)
    if echo "$resp" | grep -q 'Bad credentials'; then
        echo "📝 Bearer auth failed, trying 'token' auth..."
        resp=$(curl -s -H "Authorization: token $GITHUB_TOKEN" -H "User-Agent: leads-scraper/1.0" https://api.github.com/user)
    fi
fi

# Show result
if echo "$resp" | grep -q 'Bad credentials'; then
    echo "❌ Token validation failed: Bad credentials"
    echo "💡 Make sure your token has the required permissions and hasn't expired"
elif echo "$resp" | grep -q '"login":'; then
    username=$(echo "$resp" | jq -r '.login // "unknown"')
    echo "✅ Token is valid! Authenticated as: $username"
else
    echo "❓ Unexpected response from GitHub API"
    echo "Response: $resp"
fi
