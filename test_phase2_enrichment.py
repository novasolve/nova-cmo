#!/usr/bin/env python3
"""
Test script to verify Phase 2 (Repository Enrichment) works independently
"""

import os
import sys
import json
from pathlib import Path

# Add the lead_intelligence directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from lead_intelligence.core.repo_enricher import RepoEnricher

def test_phase2_enrichment():
    """Test the repository enrichment functionality"""
    
    # Get GitHub token from environment
    # Get token from environment
    github_token = os.environ.get('GITHUB_TOKEN', '')
    if not github_token:
        print("❌ No GITHUB_TOKEN environment variable set!")
        print("Please run: export GITHUB_TOKEN=your_token_here")
        return False
    
    print("🚀 Testing Phase 2: Repository Enrichment")
    print("=" * 50)
    
    # Initialize the RepoEnricher
    print("📦 Initializing RepoEnricher...")
    try:
        enricher = RepoEnricher(github_token)
        print("✅ RepoEnricher initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize RepoEnricher: {e}")
        return False
    
    # Test repositories
    test_repos = [
        "python/cpython",  # Large, active Python repo
        "pallets/flask",   # Popular Python web framework
        "psf/black",       # Python formatter with CI
    ]
    
    print(f"\n🔍 Testing enrichment on {len(test_repos)} repositories...")
    
    success_count = 0
    for repo in test_repos:
        print(f"\n📊 Enriching: {repo}")
        try:
            enrichment = enricher.enrich_repo(repo)
            
            if enrichment.get('error'):
                print(f"  ⚠️  Enrichment failed: {enrichment['error']}")
                if 'authentication' in enrichment['error'].lower():
                    print("  🔑 This appears to be an authentication issue")
            else:
                print(f"  ✅ Successfully enriched!")
                print(f"  📈 Stars: {enrichment.get('stars', 0)}")
                print(f"  🍴 Forks: {enrichment.get('forks', 0)}")
                
                # Check CI info
                ci_info = enrichment.get('ci', {})
                if ci_info.get('provider'):
                    print(f"  🔧 CI Provider: {ci_info['provider']}")
                
                # Check test info
                test_info = enrichment.get('tests', {})
                if test_info.get('has_tests'):
                    print(f"  🧪 Has tests: Yes")
                    if test_info.get('framework'):
                        print(f"  🧪 Test framework: {test_info['framework']}")
                
                success_count += 1
                
                # Save sample enrichment for inspection
                if success_count == 1:
                    output_file = "sample_enrichment.json"
                    with open(output_file, 'w') as f:
                        json.dump(enrichment, f, indent=2)
                    print(f"\n  💾 Sample enrichment saved to: {output_file}")
                    
        except Exception as e:
            print(f"  ❌ Exception during enrichment: {e}")
    
    print(f"\n📊 Summary: {success_count}/{len(test_repos)} repositories enriched successfully")
    
    if success_count == 0:
        print("\n❌ Phase 2 test failed - no repositories could be enriched")
        print("\n🔍 Common issues:")
        print("  1. Invalid or expired GitHub token")
        print("  2. Token lacks required permissions (needs 'repo' scope)")
        print("  3. Network connectivity issues")
        print("  4. GitHub API rate limits")
        return False
    else:
        print(f"\n✅ Phase 2 test successful - enrichment is working!")
        return True

if __name__ == "__main__":
    success = test_phase2_enrichment()
    sys.exit(0 if success else 1)
