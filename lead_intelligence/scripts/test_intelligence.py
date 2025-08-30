#!/usr/bin/env python3
"""
Test script for Lead Intelligence System
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.intelligence_engine import IntelligenceEngine, IntelligenceConfig
from analysis.lead_analyzer import LeadAnalyzer

def test_analyzer():
    """Test the lead analyzer with sample data"""
    print("🧪 Testing Lead Analyzer...")

    analyzer = LeadAnalyzer()

    # Sample lead data
    sample_lead = {
        'login': 'testuser',
        'name': 'Test User',
        'company': 'Test Company',
        'email_profile': 'test@example.com',
        'email_public_commit': None,
        'location': 'San Francisco, CA',
        'bio': 'Senior Python developer with 5+ years experience',
        'language': 'python',
        'followers': 150,
        'following': 50,
        'public_repos': 25,
        'contributions_last_year': 200,
        'stars': 500,
        'hireable': True,
        'created_at': '2018-01-01T00:00:00Z'
    }

    score = analyzer.analyze_lead(sample_lead)

    print("✅ Analysis completed:")
    print(f"   • Total Score: {score.total_score}")
    print(f"   • Confidence Level: {score.confidence_level}")
    print(f"   • Quality Signals: {len(score.quality_signals)}")
    print(f"   • Risk Signals: {len(score.risk_signals)}")
    print(f"   • Opportunity Signals: {len(score.opportunity_signals)}")

    return True

def test_configuration():
    """Test configuration loading"""
    print("⚙️  Testing Configuration...")

    config = IntelligenceConfig(
        github_token="test_token",
        base_config_path="config.yaml",
        output_dir="lead_intelligence/data"
    )

    print("✅ Configuration created:")
    print(f"   • Output Directory: {config.output_dir}")
    print(f"   • Enrichment Enabled: {config.enrichment_enabled}")
    print(f"   • Max Workers: {config.max_workers}")

    return True

def test_file_structure():
    """Test that all required files exist"""
    print("📁 Testing File Structure...")

    required_files = [
        'core/intelligence_engine.py',
        'analysis/lead_analyzer.py',
        'reporting/dashboard.py',
        'config/intelligence.yaml',
        'scripts/run_intelligence.py',
        'README.md'
    ]

    missing_files = []
    for file_path in required_files:
        full_path = Path(__file__).parent.parent / file_path
        if not full_path.exists():
            missing_files.append(file_path)
        else:
            print(f"   ✅ {file_path}")

    if missing_files:
        print("❌ Missing files:")
        for file_path in missing_files:
            print(f"   • {file_path}")
        return False

    print("✅ All required files present")
    return True

def main():
    """Run all tests"""
    print("🚀 Lead Intelligence System - Test Suite")
    print("=" * 50)

    tests = [
        ("File Structure", test_file_structure),
        ("Configuration", test_configuration),
        ("Lead Analyzer", test_analyzer)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            print(f"\n🔍 Running {test_name} test...")
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results:")

    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if result:
            passed += 1

    print(f"\n📈 Summary: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("🎉 All tests passed! Lead Intelligence System is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
