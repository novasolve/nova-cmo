#!/bin/bash

echo "🔗 Attio CRM Setup Helper"
echo "========================"
echo ""

# Check current status
if [ -n "$ATTIO_API_TOKEN" ] && [ -n "$ATTIO_WORKSPACE_ID" ]; then
    echo "✅ Attio is already configured!"
    echo "- API Token: ${ATTIO_API_TOKEN:0:10}...${ATTIO_API_TOKEN: -4}"
    echo "- Workspace ID: ${ATTIO_WORKSPACE_ID:0:10}...${ATTIO_WORKSPACE_ID: -4}"
    echo ""
    echo "To test the connection:"
    echo "   python -c \"from lead_intelligence.core.attio_integrator import AttioIntegrator; ai = AttioIntegrator(); print('✅ Connected!' if ai.validate_connection() else '❌ Connection failed!')\""
    exit 0
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
echo "Run these commands with your credentials:"
echo ""
echo "   export ATTIO_API_TOKEN='your_attio_api_key_here'"
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
cd /Users/seb/leads
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
