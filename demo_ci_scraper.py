#!/usr/bin/env python3
"""
Demo script for GitHub CI Scraper
Shows how to run a small sample to test the functionality
"""

import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from github_ci_scraper import GitHubCIScraper


def demo_ci_scraper():
    """Run a small demo of the CI scraper"""

    print("🎯 GitHub CI Scraper Demo")
    print("=" * 50)
    print("This demo will process a small number of repositories")
    print("to show how the bottom-up CI lead discovery works.")
    print()

    # Check for token
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        print("❌ Please set GITHUB_TOKEN environment variable")
        print("   export GITHUB_TOKEN=your_token_here")
        return

    # Create demo config - process only a few repos
    config = {
        'limits': {
            'max_repos': 5,  # Small number for demo
            'max_leads_per_repo': 10
        },
        'delay': 0.5  # Faster for demo
    }

    # Create output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"demo_ci_leads_{timestamp}.csv"

    print(f"📁 Demo results will be saved to: {output_path}")
    print(f"🔑 Using token: {token[:8]}...")
    print()

    try:
        # Initialize scraper
        scraper = GitHubCIScraper(token, config, output_path)

        print("🔍 Starting demo scraping...")
        scraper.scrape()

        # Close file
        scraper._close_csv_file()

        print()
        print("✅ Demo completed successfully!")
        print(f"📊 Found {len(scraper.all_leads)} leads")

        if scraper.all_leads:
            print("\n🎯 Sample results:")
            for i, lead in enumerate(scraper.all_leads[:3], 1):
                print(f"  {i}. {lead.login} ({lead.role_type}) - {lead.repo_full_name}")
                print(f"     Signal: {lead.signal_type}, Tier: {lead.tier}")
                if lead.company:
                    print(f"     Company: {lead.company}")

        print(f"\n📄 Full results saved to: {output_path}")
        print("\n💡 Next steps:")
        print("   1. Review the CSV file")
        print("   2. Run with --max-repos 100 for a full scrape")
        print("   3. Filter by role_type='director' for decision makers")
        print("   4. Use maintainer data to personalize director outreach")

    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted")
        scraper._close_csv_file()
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    demo_ci_scraper()
