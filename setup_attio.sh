#!/bin/bash

echo "🔗 Attio CRM Setup Helper"
echo "========================"
echo ""

# Resolve script dir and normalize env var aliases
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ -n "$ATTIO_API_TOKEN" ] && [ -z "$ATTIO_ACCESS_TOKEN" ]; then export ATTIO_ACCESS_TOKEN="$ATTIO_API_TOKEN"; fi
if [ -n "$ATTIO_ACCESS_TOKEN" ] && [ -z "$ATTIO_API_TOKEN" ]; then export ATTIO_API_TOKEN="$ATTIO_ACCESS_TOKEN"; fi

# Check current status (do not exit so sourcing won't kill the shell)
if [ -n "$ATTIO_API_TOKEN" ] && [ -n "$ATTIO_WORKSPACE_ID" ]; then
    echo "✅ Attio is configured"
    echo "- API Token: ${ATTIO_API_TOKEN:0:10}...${ATTIO_API_TOKEN: -4}"
    echo "- Workspace ID: ${ATTIO_WORKSPACE_ID:0:10}...${ATTIO_WORKSPACE_ID: -4}"
fi

echo "Attio is not configured yet."
echo ""
echo "=== ATTIO SETUP INSTRUCTIONS ==="
echo "1. Go to: https://app.attio.com/settings/developers/api-keys"
echo "2. Create a new API key with the following scopes:"
echo "   ✓ objects:read"
echo "   ✓ objects:write"
echo "   ✓ records:read"
echo "   ✓ records:write"
echo ""
echo "3. Get your Workspace ID from: https://app.attio.com/settings/workspace"
echo ""
echo "=== SETTING UP ATTIO ==="
echo "Run these commands with your credentials (exports all supported env var names):"
echo ""
echo "   export ATTIO_API_TOKEN='your_attio_api_key_here'"
echo "   export ATTIO_API_KEY=\"$ATTIO_API_TOKEN\""
echo "   export ATTIO_ACCESS_TOKEN=\"$ATTIO_API_TOKEN\""
echo "   export ATTIO_WORKSPACE_ID='your_workspace_id_here'"
echo ""
echo "=== TESTING THE CONNECTION ==="
echo "After setting up, test it:"
echo ""
echo "   source setup_attio.sh"
echo "   python -c \"from lead_intelligence.core.attio_integrator import AttioIntegrator; ai = AttioIntegrator(); print('✅ Connected!' if ai.validate_connection() else '❌ Connection failed!')\""
echo ""
echo "=== INTEGRATION WITH INTELLIGENCE SYSTEM ==="
echo "Once configured, 'make intelligence' will automatically push leads to Attio."
echo ""

# Test if we can import the Attio integrator
echo "Testing Attio integration code..."
cd "$SCRIPT_DIR/.." 2>/dev/null || true
python -c "
try:
    from lead_intelligence.core.attio_integrator import AttioIntegrator
    print('✅ Attio integration code is available')
    if '$ATTIO_API_TOKEN':
        ai = AttioIntegrator()
        if ai.validate_connection():
            print('✅ Attio API connection successful!')
        else:
            print('❌ Attio API connection failed')
    else:
        print('⚠️  No Attio token set - integration will be skipped')
except ImportError as e:
    print(f'❌ Cannot import Attio integrator: {e}')
except Exception as e:
    print(f'❌ Error testing Attio: {e}')
"
