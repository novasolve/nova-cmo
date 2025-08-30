#!/usr/bin/env python3
"""
Basic test script for Copy Factory
"""

import sys
from pathlib import Path
import tempfile
import shutil

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.factory import CopyFactory
from core.models import ICPProfile, ProspectData, CopyTemplate


def test_basic_functionality():
    """Test basic Copy Factory functionality"""

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print("🧪 Testing Copy Factory...")

        # Initialize factory
        factory = CopyFactory(temp_dir)

        # Test 1: Create and save ICP
        print("\n1️⃣ Testing ICP creation...")
        icp = ICPProfile(
            id="test_python_dev",
            name="Test Python Developer",
            description="Test ICP for Python developers",
            technographics={"language": ["Python"], "frameworks": ["Django"]},
            firmographics={"size": "1-50", "geo": ["US"]},
            triggers=["Python repository activity"]
        )

        factory.storage.save_icp(icp)
        retrieved_icp = factory.storage.get_icp("test_python_dev")

        assert retrieved_icp is not None, "ICP not saved/retrieved correctly"
        assert retrieved_icp.name == "Test Python Developer", "ICP data mismatch"
        print("✅ ICP creation and retrieval works")

        # Test 2: Create and save prospect
        print("\n2️⃣ Testing prospect creation...")
        prospect = ProspectData(
            lead_id="test_lead_123",
            login="testuser",
            name="Test User",
            company="Test Corp",
            email_profile="test@example.com",
            language="Python",
            followers=50,
            public_repos=10
        )

        factory.storage.save_prospect(prospect)
        retrieved_prospect = factory.storage.get_prospect("test_lead_123")

        assert retrieved_prospect is not None, "Prospect not saved/retrieved correctly"
        assert retrieved_prospect.has_email(), "Email detection failed"
        assert retrieved_prospect.get_best_email() == "test@example.com", "Email retrieval failed"
        print("✅ Prospect creation and retrieval works")

        # Test 3: Create template
        print("\n3️⃣ Testing template creation...")
        template = factory.create_icp_template(icp, "email")
        retrieved_template = factory.storage.get_template(template.id)

        assert retrieved_template is not None, "Template not created correctly"
        assert "${first_name}" in retrieved_template.body_template, "Template variables not working"
        print("✅ Template creation works")

        # Test 4: Generate copy
        print("\n4️⃣ Testing copy generation...")
        copy_result = factory.generator.generate_copy(template, prospect, icp)

        assert copy_result is not None, "Copy generation failed"
        assert copy_result['prospect_id'] == "test_lead_123", "Copy prospect ID mismatch"

        # Debug: print the actual generated copy
        print(f"Generated body: {copy_result['body'][:200]}...")

        # The copy should contain the substituted values
        assert copy_result['body'] and len(copy_result['body']) > 50, "Copy generation produced empty or too short content"
        print("✅ Copy generation works")

        # Test 5: Match prospect to ICP and create campaign
        print("\n5️⃣ Testing prospect matching and campaign creation...")

        # First match the prospect to the ICP
        prospect.icp_matches = ["test_python_dev"]
        factory.storage.save_prospect(prospect)

        campaign = factory.create_campaign("Test Campaign", "test_python_dev", template.id)

        assert campaign is not None, "Campaign creation failed"
        assert len(campaign.prospect_ids) > 0, "Campaign has no prospects"
        print("✅ Campaign creation works")

        # Test 6: Validation
        print("\n6️⃣ Testing validation...")
        validation = factory.validate_setup()

        assert validation['valid'], f"Validation failed: {validation['issues']}"
        assert validation['stats']['icps'] == 1, "ICP count mismatch"
        assert validation['stats']['prospects'] == 1, "Prospect count mismatch"
        print("✅ Validation works")

        print("\n🎉 All tests passed! Copy Factory is working correctly.")


def test_data_import():
    """Test data import functionality"""
    print("\n🧪 Testing data import...")

    with tempfile.TemporaryDirectory() as temp_dir:
        factory = CopyFactory(temp_dir)

        # Create test CSV content
        csv_content = """lead_id,login,name,company,email_profile,language,followers
test1,user1,John Doe,Tech Corp,john@tech.com,Python,100
test2,user2,Jane Smith,Dev Inc,jane@dev.com,JavaScript,75
test3,user3,Bob Wilson,,bob@github.com,Python,25"""

        csv_file = Path(temp_dir) / "test_prospects.csv"
        with open(csv_file, 'w') as f:
            f.write(csv_content)

        # Import prospects
        imported = factory.import_prospects_from_csv(str(csv_file))

        assert imported == 3, f"Expected 3 imports, got {imported}"

        # Verify imports
        prospects = factory.storage.list_prospects()
        assert len(prospects) == 3, f"Expected 3 prospects, got {len(prospects)}"

        # Check email detection
        prospects_with_emails = [p for p in prospects if p.has_email()]
        assert len(prospects_with_emails) == 3, "All prospects should have emails"

        print("✅ Data import works")


if __name__ == '__main__':
    try:
        test_basic_functionality()
        test_data_import()
        print("\n🎊 All Copy Factory tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
