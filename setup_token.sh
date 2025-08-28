#!/bin/bash

echo "🔐 GitHub Token Setup Helper"
echo "=========================="
echo ""
echo "Your current token is invalid (401: Bad credentials)"
echo ""
echo "To fix this:"
echo ""
echo "1. Go to: https://github.com/settings/tokens"
echo "2. Click 'Generate new token (classic)'"
echo "3. Name it: 'Growth Scraper'"
echo "4. Select these scopes:"
echo "   ✓ repo (Full control of private repositories)"
echo "   ✓ user (Update ALL user data)"
echo "   - This includes: read:user, user:email, user:follow"
echo ""
echo "5. Click 'Generate token' at the bottom"
echo "6. Copy the token (starts with ghp_)"
echo ""
echo "7. Run this command with your token (classic or fine-grained):"
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
echo "Testing current token..."
resp=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" -H "User-Agent: leads-scraper/1.0" https://api.github.com/user)
if echo "$resp" | grep -q 'Bad credentials'; then
  resp=$(curl -s -H "Authorization: token $GITHUB_TOKEN" -H "User-Agent: leads-scraper/1.0" https://api.github.com/user)
fi
echo "$resp" | jq -r '.message // "✅ Token is valid!"'
