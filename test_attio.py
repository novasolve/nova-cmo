#!/usr/bin/env python3
"""
Test Attio API connection and integration
"""

import os
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_attio_connection():
    """Test Attio API connection"""
    print("🔗 Testing Attio API connection...")

    # Check environment variables
    attio_token = os.environ.get('ATTIO_API_TOKEN', '')
    attio_workspace = os.environ.get('ATTIO_WORKSPACE_ID', '')

    if not attio_token:
        print("❌ ATTIO_API_TOKEN environment variable not set")
        return False

    if not attio_workspace:
        print("⚠️  ATTIO_WORKSPACE_ID environment variable not set")
        print("   (This is optional but recommended)")

    try:
        from lead_intelligence.core.attio_integrator import AttioIntegrator

        # Initialize Attio integrator
        config = {
            'api_token': attio_token,
            'workspace_id': attio_workspace
        }

        integrator = AttioIntegrator(config)

        # Test connection
        if integrator.validate_connection():
            print("✅ Attio API connection successful!")
            return True
        else:
            print("❌ Attio API connection failed")
            return False

    except ImportError as e:
        print(f"❌ Cannot import Attio integrator: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing Attio connection: {e}")
        return False

def test_attio_integration():
    """Test Attio integration with sample data"""
    print("\n🔄 Testing Attio integration with sample data...")

    try:
        from lead_intelligence.core.attio_integrator import AttioIntegrator

        attio_token = os.environ.get('ATTIO_API_TOKEN', '')
        if not attio_token:
            print("❌ No Attio token - skipping integration test")
            return False

        integrator = AttioIntegrator({'api_token': attio_token})

        if not integrator.validate_connection():
            print("❌ Attio connection failed - skipping integration test")
            return False

        # Test with sample data
        sample_people = [{
            'login': 'testuser',
            'name': 'Test User',
            'email_profile': 'test@example.com',
            'company': 'Test Company',
            'location': 'Test City',
            'bio': 'Test bio for integration testing',
            'public_repos': 5,
            'followers': 10,
            'html_url': 'https://github.com/testuser',
            'github_user_url': 'https://github.com/testuser'
        }]

        print("📤 Testing people import...")
        result = integrator.import_people(sample_people)

        if result['successful'] > 0:
            print(f"✅ Successfully imported {result['successful']} test people")
            return True
        else:
            print(f"❌ Failed to import test people: {result.get('errors', [])}")
            return False

    except Exception as e:
        print(f"❌ Error testing Attio integration: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Attio Integration Test Suite")
    print("=" * 40)

    # Test connection
    connection_ok = test_attio_connection()

    if connection_ok:
        # Test integration
        integration_ok = test_attio_integration()

        if integration_ok:
            print("\n🎉 All Attio tests passed!")
            print("✅ Your Attio integration is ready to use with 'make intelligence'")
            return True
        else:
            print("\n⚠️  Connection works but integration test failed")
            print("   Check your Attio permissions and object configuration")
            return False
    else:
        print("\n❌ Attio connection failed")
        print("💡 Run './setup_attio.sh' for setup instructions")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
