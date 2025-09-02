#!/usr/bin/env python3
"""
Runner script for GitHub CI Scraper
Implements the bottom-up approach for finding CI/DevOps decision makers and practitioners
"""

import os
import sys
import argparse
from datetime import datetime
import yaml

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from github_ci_scraper import GitHubCIScraper


def create_default_config():
    """Create a default configuration for CI scraping"""
    return {
        'limits': {
            'max_repos': 100,
            'max_leads_per_repo': 20
        },
        'delay': 1.0,
        'signals': {
            'workflow_commits': {'enabled': True, 'lookback_days': 90},
            'test_commits': {'enabled': True, 'lookback_days': 90},
            'codeowners': {'enabled': True}
        }
    }


def run_bottom_up_search():
    """Run the bottom-up search as described in the user query"""
    
    print("🔍 GitHub Bottom-up CI/DevOps Lead Discovery")
    print("=" * 60)
    print("\nStrategy: Find Python repos with real CI activity, then map to people")
    print("\nSearch queries being used:")
    
    # The exact queries from the user's request
    queries = [
        'path:.github/workflows language:YAML pytest pushed:>=2024-06-01',
        'path:.github/workflows language:YAML "pytest -q" pushed:>=2024-06-01', 
        'path:.github/workflows language:YAML tox pushed:>=2024-06-01',
        'filename:CODEOWNERS ".github/workflows"',
        'filename:CODEOWNERS "tests/"'
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"  {i}. {query}")
    
    print("\nFor each repo/org, extracting:")
    print("  • Workflow file authors (commits to .github/workflows/** last 90 days)")
    print("  • Top committers to tests/**")
    print("  • CODEOWNERS for .github/workflows or tests/**")
    print("  • Map GitHub handles → LinkedIn/Company via metadata")
    print("\nResult: Director list (deciders) + Maintainer list (practitioners)")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='GitHub CI/DevOps Lead Scraper - Bottom-up Discovery',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic run with default settings
  python run_ci_scraper.py
  
  # Custom output and limits  
  python run_ci_scraper.py --out directors_maintainers.csv --max-repos 50
  
  # Use specific config file
  python run_ci_scraper.py --config configs/ci_scraper.yaml
  
  # Dry run to see what would be processed
  python run_ci_scraper.py --dry-run
        """
    )
    
    parser.add_argument('--config', help='Config YAML file path')
    parser.add_argument('--out', default=f'data/ci_leads_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv', 
                       help='Output CSV file path')
    parser.add_argument('--max-repos', type=int, default=100, 
                       help='Maximum repositories to process')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay between API requests (seconds)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be processed without executing')
    parser.add_argument('--print-only', action='store_true',
                       help='Only print results, do not save to file')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Show the strategy
    run_bottom_up_search()
    
    if args.dry_run:
        print("\n🧪 DRY RUN MODE - No actual scraping will be performed")
        return
    
    # Check for GitHub token
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        print("\n❌ Error: GitHub token required")
        print("Set environment variable: export GITHUB_TOKEN=your_token_here")
        print("Get a token at: https://github.com/settings/tokens")
        print("Required scopes: repo, read:user, read:org")
        sys.exit(1)
    
    # Load or create config
    if args.config and os.path.exists(args.config):
        print(f"\n📄 Loading config from {args.config}")
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    else:
        print("\n⚙️  Using default configuration")
        config = create_default_config()
    
    # Override config with command line args
    config['limits']['max_repos'] = args.max_repos
    config['delay'] = args.delay
    
    # Create output directory
    output_path = None if args.print_only else args.out
    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        print(f"📁 Output will be saved to: {output_path}")
    
    # Initialize and run scraper
    print(f"\n🚀 Starting scraper...")
    print(f"   Max repos: {config['limits']['max_repos']}")
    print(f"   Delay: {config['delay']}s")
    print(f"   Token: {token[:8]}..." if token else "   No token")
    
    try:
        scraper = GitHubCIScraper(token, config, output_path)
        scraper.scrape()
        
        if output_path:
            scraper._close_csv_file()
            
        print(f"\n✅ Scraping completed successfully!")
        
        # Print actionable summary
        print(f"\n📋 NEXT STEPS:")
        print(f"   1. Review the results in {output_path}")
        print(f"   2. Filter directors (decision makers) for initial outreach")
        print(f"   3. Use maintainer data to personalize director emails")
        print(f"   4. Map GitHub handles to LinkedIn profiles")
        print(f"   5. Research company domains for corporate email patterns")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Scraping interrupted by user")
        if output_path:
            scraper._close_csv_file()
    except Exception as e:
        print(f"\n❌ Error during scraping: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
