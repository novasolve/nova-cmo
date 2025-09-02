#!/usr/bin/env python3
"""
Estimate the total addressable market for CI/DevOps leads using GitHub search queries
"""

import requests
import time
import os
from typing import Dict, List, Tuple
import json
from datetime import datetime


class GitHubMarketEstimator:
    """Estimate the size of CI/DevOps market on GitHub"""
    
    def __init__(self, token: str = None):
        self.token = token or os.environ.get('GITHUB_TOKEN')
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'ci-market-estimator/1.0'
        }
        if self.token:
            self.headers['Authorization'] = f'Bearer {self.token}'
    
    def search_repositories(self, query: str) -> Dict:
        """Search GitHub repositories and return count info"""
        try:
            url = "https://api.github.com/search/repositories"
            params = {
                'q': query,
                'per_page': 1  # We only need the count
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'total_count': data.get('total_count', 0),
                    'query': query,
                    'status': 'success'
                }
            else:
                return {
                    'total_count': 0,
                    'query': query,
                    'status': f'error_{response.status_code}',
                    'message': response.text[:200] if response.text else ''
                }
        except Exception as e:
            return {
                'total_count': 0,
                'query': query,
                'status': 'error',
                'message': str(e)
            }
    
    def estimate_people_per_repo(self) -> Dict[str, int]:
        """Estimate average number of people per repository type"""
        return {
            'workflow_authors': 3,      # Average workflow contributors per repo
            'test_committers': 5,       # Average test contributors per repo  
            'codeowners': 2,            # Average CODEOWNERS entries per repo
            'maintainers': 2,           # Average maintainers per repo
            'total_unique_per_repo': 8  # Estimated unique people per repo (with overlap)
        }
    
    def estimate_role_distribution(self) -> Dict[str, float]:
        """Estimate percentage distribution of roles"""
        return {
            'directors': 0.15,      # 15% are decision makers
            'maintainers': 0.45,    # 45% are maintainers/practitioners
            'contributors': 0.40    # 40% are regular contributors
        }
    
    def estimate_contactable_rate(self) -> float:
        """Estimate percentage of people with contact information"""
        return 0.35  # 35% have discoverable email/contact info
    
    def run_market_analysis(self):
        """Run complete market size analysis"""
        
        print("🔍 GitHub CI/DevOps Market Size Analysis")
        print("=" * 60)
        print("Analyzing the queries from your bottom-up strategy...\n")
        
        # The exact queries from the user's strategy
        ci_queries = [
            'path:.github/workflows language:YAML pytest pushed:>=2024-06-01',
            'path:.github/workflows language:YAML "pytest -q" pushed:>=2024-06-01',
            'path:.github/workflows language:YAML tox pushed:>=2024-06-01',
            'filename:CODEOWNERS ".github/workflows"',
            'filename:CODEOWNERS "tests/"'
        ]
        
        # Additional related queries to estimate broader market
        extended_queries = [
            'path:.github/workflows language:YAML python pushed:>=2024-06-01',
            'path:.github/workflows language:YAML "github-actions" pushed:>=2024-06-01',
            'path:.github/workflows language:YAML "ci" pushed:>=2024-06-01',
            'path:.github/workflows language:YAML "test" pushed:>=2024-06-01',
            'filename:CODEOWNERS language:Text',
            'path:.github/workflows language:YAML pushed:>=2024-06-01'
        ]
        
        print("📊 Core CI Queries (Your Target Market):")
        core_results = []
        total_core_repos = 0
        
        for query in ci_queries:
            print(f"   Searching: {query[:60]}...")
            result = self.search_repositories(query)
            core_results.append(result)
            
            if result['status'] == 'success':
                count = result['total_count']
                total_core_repos += count
                print(f"   ✅ Found: {count:,} repositories")
            else:
                print(f"   ❌ Error: {result['status']} - {result.get('message', '')}")
            
            time.sleep(1)  # Rate limiting
        
        print(f"\n📈 Extended Market Queries (Broader Opportunity):")
        extended_results = []
        total_extended_repos = 0
        
        for query in extended_queries:
            print(f"   Searching: {query[:60]}...")
            result = self.search_repositories(query)
            extended_results.append(result)
            
            if result['status'] == 'success':
                count = result['total_count']
                total_extended_repos += count
                print(f"   ✅ Found: {count:,} repositories")
            else:
                print(f"   ❌ Error: {result['status']} - {result.get('message', '')}")
            
            time.sleep(1)  # Rate limiting
        
        # Calculate estimates
        people_per_repo = self.estimate_people_per_repo()
        role_distribution = self.estimate_role_distribution()
        contactable_rate = self.estimate_contactable_rate()
        
        # Core market estimates (your target queries)
        core_unique_repos = int(total_core_repos * 0.7)  # Assume 30% overlap
        core_total_people = core_unique_repos * people_per_repo['total_unique_per_repo']
        core_directors = int(core_total_people * role_distribution['directors'])
        core_maintainers = int(core_total_people * role_distribution['maintainers'])
        core_contactable = int(core_total_people * contactable_rate)
        
        # Extended market estimates
        extended_unique_repos = int(total_extended_repos * 0.6)  # Higher overlap in broader search
        extended_total_people = extended_unique_repos * people_per_repo['total_unique_per_repo']
        extended_directors = int(extended_total_people * role_distribution['directors'])
        extended_maintainers = int(extended_total_people * role_distribution['maintainers'])
        extended_contactable = int(extended_total_people * contactable_rate)
        
        # Print comprehensive analysis
        print(f"\n" + "=" * 60)
        print(f"🎯 MARKET SIZE ESTIMATES")
        print(f"=" * 60)
        
        print(f"\n📊 CORE TARGET MARKET (Your Specific Queries):")
        print(f"   • Total Repositories: {total_core_repos:,} (raw)")
        print(f"   • Unique Repositories: {core_unique_repos:,} (after dedup)")
        print(f"   • Total People: {core_total_people:,}")
        print(f"   • Directors (Decision Makers): {core_directors:,}")
        print(f"   • Maintainers (Practitioners): {core_maintainers:,}")
        print(f"   • Contactable People: {core_contactable:,}")
        
        print(f"\n🌐 EXTENDED MARKET (Broader CI/DevOps):")
        print(f"   • Total Repositories: {total_extended_repos:,} (raw)")
        print(f"   • Unique Repositories: {extended_unique_repos:,} (after dedup)")
        print(f"   • Total People: {extended_total_people:,}")
        print(f"   • Directors (Decision Makers): {extended_directors:,}")
        print(f"   • Maintainers (Practitioners): {extended_maintainers:,}")
        print(f"   • Contactable People: {extended_contactable:,}")
        
        print(f"\n💡 ASSUMPTIONS USED:")
        print(f"   • People per repo: {people_per_repo['total_unique_per_repo']} unique")
        print(f"   • Directors: {role_distribution['directors']*100:.0f}% of people")
        print(f"   • Maintainers: {role_distribution['maintainers']*100:.0f}% of people") 
        print(f"   • Contactable rate: {contactable_rate*100:.0f}%")
        print(f"   • Core overlap: 30% (specific CI queries)")
        print(f"   • Extended overlap: 40% (broader queries)")
        
        print(f"\n🚀 ACTIONABLE INSIGHTS:")
        print(f"   • Immediate Target: {core_contactable:,} contactable people")
        print(f"   • Priority Directors: {int(core_directors * contactable_rate):,}")
        print(f"   • Supporting Maintainers: {int(core_maintainers * contactable_rate):,}")
        print(f"   • Growth Opportunity: {extended_contactable - core_contactable:,} additional")
        
        print(f"\n📈 CAMPAIGN SIZING:")
        if core_contactable > 0:
            print(f"   • Small Campaign: {min(1000, core_contactable):,} leads")
            print(f"   • Medium Campaign: {min(5000, core_contactable):,} leads") 
            print(f"   • Large Campaign: {min(20000, core_contactable):,} leads")
            print(f"   • Total Addressable: {core_contactable:,} leads")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"market_analysis_{timestamp}.json"
        
        analysis_results = {
            'timestamp': timestamp,
            'core_queries': ci_queries,
            'extended_queries': extended_queries,
            'core_results': core_results,
            'extended_results': extended_results,
            'estimates': {
                'core_market': {
                    'total_repos': total_core_repos,
                    'unique_repos': core_unique_repos,
                    'total_people': core_total_people,
                    'directors': core_directors,
                    'maintainers': core_maintainers,
                    'contactable': core_contactable
                },
                'extended_market': {
                    'total_repos': total_extended_repos,
                    'unique_repos': extended_unique_repos,
                    'total_people': extended_total_people,
                    'directors': extended_directors,
                    'maintainers': extended_maintainers,
                    'contactable': extended_contactable
                }
            },
            'assumptions': {
                'people_per_repo': people_per_repo,
                'role_distribution': role_distribution,
                'contactable_rate': contactable_rate
            }
        }
        
        with open(results_file, 'w') as f:
            json.dump(analysis_results, f, indent=2)
        
        print(f"\n💾 Detailed analysis saved to: {results_file}")
        print(f"=" * 60)
        
        return analysis_results


def main():
    """Run the market analysis"""
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("⚠️  Warning: No GITHUB_TOKEN found. Results may be limited.")
        print("   Set token for full API access: export GITHUB_TOKEN=your_token")
    
    estimator = GitHubMarketEstimator(token)
    estimator.run_market_analysis()


if __name__ == '__main__':
    main()
