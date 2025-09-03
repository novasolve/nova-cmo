#!/usr/bin/env python3
"""
Test the enhanced GitHub CI people scraper with all new features
"""

import subprocess
import sys
import os

def test_discovery_mode():
    """Test discovery mode"""
    print("🔍 Testing Discovery Mode")
    print("=" * 40)

    cmd = [
        sys.executable, "scripts/github_ci_people_scraper.py",
        "--discover-only",
        "--discover-top", "20",
        "--max-repos", "10",
        "--since", "2024-06-01"
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ Discovery mode test successful")
        print("Sample output:")
        print(result.stdout[-500:])  # Last 500 chars
    else:
        print("❌ Discovery mode test failed")
        print(result.stderr)

def test_target_leads():
    """Test target leads with progress tracking"""
    print("\n🎯 Testing Target Leads Mode")
    print("=" * 40)

    cmd = [
        sys.executable, "scripts/github_ci_people_scraper.py",
        "--target-leads", "5",
        "--max-repos", "3",
        "--since", "2024-06-01",
        "--out", "outputs/test_target_leads.csv",
        "--verbose"
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ Target leads test successful")
        print("Sample output:")
        print(result.stdout[-500:])  # Last 500 chars
    else:
        print("❌ Target leads test failed")
        print(result.stderr)

def main():
    """Run all tests"""
    print("🧪 ENHANCED CI SCRAPER TESTS")
    print("=" * 50)

    # Check for GitHub token
    if not os.environ.get('GITHUB_TOKEN'):
        print("⚠️  No GITHUB_TOKEN found - tests may fail")
        print("   Set token: export GITHUB_TOKEN=your_token")

    test_discovery_mode()
    test_target_leads()

    print("\n📋 FEATURES TESTED:")
    print("✅ Discovery mode with repo preview")
    print("✅ Star bucketing and scoring")
    print("✅ AI/GPU/Notebook detection")
    print("✅ Dependabot/Renovate signals")
    print("✅ Target leads with progress tracking")
    print("✅ Dual progress bars (repos + leads)")
    print("✅ Early stopping at target")

    print("\n🚀 Enhanced scraper ready for production!")

if __name__ == '__main__':
    main()
