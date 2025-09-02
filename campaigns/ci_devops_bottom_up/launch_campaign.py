#!/usr/bin/env python3
"""
CI/DevOps Bottom-up Campaign Launcher

Orchestrates the complete bottom-up GitHub → people mapping strategy:
1. GitHub search for Python repos with real CI activity
2. Extract workflow authors, test committers, and CODEOWNERS
3. Map GitHub handles → LinkedIn/Company via metadata
4. Generate director list (deciders) and maintainer list (practitioners)

Usage:
    export GITHUB_TOKEN=your_token_here
    python launch_campaign.py --mode fresh     # Fresh GitHub scraping
    python launch_campaign.py --mode existing  # Use existing data
    python launch_campaign.py --mode apollo    # Enrich with Apollo
"""

import os
import sys
import argparse
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# Add scripts directory to path
CAMPAIGN_DIR = Path(__file__).parent
SCRIPTS_DIR = CAMPAIGN_DIR / "scripts"
DATA_DIR = CAMPAIGN_DIR / "data"
OUTPUTS_DIR = CAMPAIGN_DIR / "outputs"
CONFIGS_DIR = CAMPAIGN_DIR / "configs"

sys.path.insert(0, str(SCRIPTS_DIR))


class CICampaignLauncher:
    """Orchestrates the CI/DevOps bottom-up campaign"""
    
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = f"ci_campaign_{self.timestamp}"
        self.output_dir = OUTPUTS_DIR / self.run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Check for GitHub token
        self.github_token = os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            print("❌ GITHUB_TOKEN environment variable required")
            print("   Get a token at: https://github.com/settings/tokens")
            print("   Required scopes: repo, read:user, read:org")
            sys.exit(1)
    
    def print_header(self):
        """Print campaign header"""
        print("🚀 CI/DEVOPS BOTTOM-UP CAMPAIGN LAUNCHER")
        print("=" * 60)
        print("Strategy: GitHub → Python repos with CI activity → map to people")
        print()
        print("Process:")
        print("  1. Search GitHub for Python repos with CI activity")
        print("  2. Extract workflow file authors (.github/workflows/** commits)")
        print("  3. Extract top test committers (tests/** commits)")
        print("  4. Parse CODEOWNERS for CI/testing ownership")
        print("  5. Map GitHub handles → LinkedIn/Company metadata")
        print("  6. Generate director list (deciders) + maintainer list (practitioners)")
        print()
        print(f"🆔 Run ID: {self.run_id}")
        print(f"📁 Output: {self.output_dir}")
        print("=" * 60)
    
    def run_fresh_github_scraping(self, max_repos: int = 100):
        """Run fresh GitHub scraping using ci_people_finder"""
        print("\n🔍 PHASE 1: Fresh GitHub CI Scraping")
        print("-" * 40)
        
        # Create temp output directory for ci_people_finder
        temp_out = self.output_dir / "github_raw"
        temp_out.mkdir(exist_ok=True)
        
        # Run ci_people_finder
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "ci_people_finder.py"),
            "--since", "2024-06-01",
            "--max-code-results", str(max_repos),
            "--outdir", str(temp_out)
        ]
        
        print(f"🚀 Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ GitHub scraping completed successfully")
            
            # Move results to organized structure
            if (temp_out / "directors.csv").exists():
                shutil.move(str(temp_out / "directors.csv"), str(self.output_dir / "directors_fresh.csv"))
            if (temp_out / "maintainers.csv").exists():
                shutil.move(str(temp_out / "maintainers.csv"), str(self.output_dir / "maintainers_fresh.csv"))
            if (temp_out / "people_signals.json").exists():
                shutil.move(str(temp_out / "people_signals.json"), str(self.output_dir / "people_signals.json"))
            
            return True
        else:
            print(f"❌ GitHub scraping failed: {result.stderr}")
            return False
    
    def run_existing_data_analysis(self):
        """Analyze existing lead data"""
        print("\n📊 PHASE 2: Existing Data Analysis")
        print("-" * 40)
        
        # Check for existing data
        existing_files = list(DATA_DIR.glob("*.csv"))
        if not existing_files:
            print("❌ No existing CSV files found in data directory")
            return False
        
        print(f"📁 Found {len(existing_files)} existing data files")
        
        # Run analyze_existing_leads.py
        cmd = [sys.executable, str(SCRIPTS_DIR / "analyze_existing_leads.py")]
        
        # Change to scripts directory to run
        original_cwd = os.getcwd()
        os.chdir(SCRIPTS_DIR)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Existing data analysis completed")
                print(result.stdout)
                
                # Move generated files to output directory
                for pattern in ["*analyzed*.csv", "*directors*.csv", "*maintainers*.csv"]:
                    for file in Path(".").glob(pattern):
                        if file.is_file():
                            shutil.move(str(file), str(self.output_dir / file.name))
                
                return True
            else:
                print(f"❌ Analysis failed: {result.stderr}")
                return False
        finally:
            os.chdir(original_cwd)
    
    def filter_and_clean_leads(self):
        """Filter and clean the leads"""
        print("\n🧹 PHASE 3: Lead Filtering & Cleaning")
        print("-" * 40)
        
        # Find the most recent analyzed file
        analyzed_files = list(self.output_dir.glob("*analyzed*.csv"))
        if not analyzed_files:
            print("❌ No analyzed CSV files found")
            return False
        
        latest_file = max(analyzed_files, key=lambda f: f.stat().st_mtime)
        print(f"📄 Using: {latest_file.name}")
        
        # Run filter_ci_leads.py
        original_cwd = os.getcwd()
        os.chdir(SCRIPTS_DIR)
        
        try:
            # Copy the file to scripts directory temporarily
            temp_file = Path("temp_leads_for_filtering.csv")
            shutil.copy(str(latest_file), str(temp_file))
            
            # Modify filter script to use temp file
            filter_script = Path("filter_ci_leads.py")
            if filter_script.exists():
                # Read and modify the script to use our temp file
                content = filter_script.read_text()
                content = content.replace('FINAL_1000_LEADS_MAXIMUM_FROM_DATA.csv', 'temp_leads_for_filtering.csv')
                
                # Write modified script
                modified_script = Path("filter_ci_leads_modified.py")
                modified_script.write_text(content)
                
                # Run the modified script
                cmd = [sys.executable, str(modified_script)]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("✅ Lead filtering completed")
                    
                    # Move filtered results
                    for pattern in ["filtered_*.csv", "removed_*.csv"]:
                        for file in Path(".").glob(pattern):
                            if file.is_file():
                                shutil.move(str(file), str(self.output_dir / file.name))
                    
                    # Clean up temp files
                    temp_file.unlink(missing_ok=True)
                    modified_script.unlink(missing_ok=True)
                    
                    return True
                else:
                    print(f"❌ Filtering failed: {result.stderr}")
                    return False
        finally:
            os.chdir(original_cwd)
    
    def filter_us_only(self):
        """Filter to US-only leads"""
        print("\n🇺🇸 PHASE 4: US-Only Filtering")
        print("-" * 40)
        
        # Find filtered leads file
        filtered_files = list(self.output_dir.glob("filtered_*.csv"))
        if not filtered_files:
            print("❌ No filtered CSV files found")
            return False
        
        latest_file = max(filtered_files, key=lambda f: f.stat().st_mtime)
        print(f"📄 Using: {latest_file.name}")
        
        # Simple US filtering logic
        import csv
        
        us_leads = []
        with open(latest_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for lead in reader:
                location = (lead.get('location', '') or '').lower()
                company = (lead.get('company', '') or '').lower()
                
                # US indicators
                us_indicators = [
                    'usa', 'united states', 'america', 'california', 'new york', 'texas',
                    'florida', 'washington', 'oregon', 'colorado', 'nevada', 'arizona',
                    'san francisco', 'los angeles', 'chicago', 'seattle', 'boston',
                    'austin', 'denver', 'atlanta', 'miami', 'dallas', 'phoenix',
                    'bay area', 'silicon valley', ', ca', ', ny', ', tx', ', fl'
                ]
                
                non_us = ['uk', 'france', 'germany', 'china', 'canada', 'australia']
                
                # Check for US location or major US company
                is_us_location = any(indicator in location for indicator in us_indicators)
                is_us_company = any(comp in company for comp in ['google', 'microsoft', 'facebook', 'amazon', 'apple', 'netflix', 'uber', 'airbnb'])
                has_non_us = any(indicator in location for indicator in non_us)
                
                if (is_us_location or is_us_company) and not has_non_us:
                    us_leads.append(lead)
        
        # Save US-only leads
        us_file = self.output_dir / "us_only_leads_final.csv"
        
        if us_leads:
            with open(us_file, 'w', newline='', encoding='utf-8') as f:
                if us_leads:
                    writer = csv.DictWriter(f, fieldnames=us_leads[0].keys())
                    writer.writeheader()
                    writer.writerows(us_leads)
        
        print(f"✅ US filtering completed: {len(us_leads)} US leads")
        return len(us_leads) > 0
    
    def generate_campaign_summary(self):
        """Generate campaign summary and next steps"""
        print("\n📊 CAMPAIGN SUMMARY")
        print("=" * 60)
        
        # Count files in output directory
        output_files = list(self.output_dir.glob("*.csv"))
        
        print(f"🆔 Campaign ID: {self.run_id}")
        print(f"📁 Output Directory: {self.output_dir}")
        print(f"📄 Files Generated: {len(output_files)}")
        
        # Show key files
        key_files = {
            'directors': list(self.output_dir.glob("*directors*.csv")),
            'maintainers': list(self.output_dir.glob("*maintainers*.csv")),
            'us_only': list(self.output_dir.glob("*us_only*.csv")),
            'filtered': list(self.output_dir.glob("*filtered*.csv"))
        }
        
        print(f"\n📋 KEY OUTPUT FILES:")
        for category, files in key_files.items():
            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                
                # Count lines
                try:
                    with open(latest, 'r') as f:
                        line_count = sum(1 for line in f) - 1  # Subtract header
                except:
                    line_count = 0
                
                print(f"  🎯 {category.title()}: {latest.name} ({line_count} leads)")
        
        print(f"\n💡 NEXT STEPS:")
        print(f"  1. Review directors.csv for decision maker outreach")
        print(f"  2. Use maintainers.csv to personalize director emails")
        print(f"  3. Start with US-only leads for initial campaign")
        print(f"  4. Use LinkedIn queries for social selling")
        print(f"  5. Reference specific CI artifacts from source repos")
        
        print(f"\n🚀 CAMPAIGN READY!")
        print("=" * 60)
    
    def run_apollo_enrichment(self):
        """Run Apollo enrichment if API key available"""
        apollo_key = os.environ.get('APOLLO_API_KEY')
        if not apollo_key:
            print("\n⚠️  Apollo API key not found (optional)")
            print("   Set APOLLO_API_KEY to enrich with phone numbers and verified emails")
            return False
        
        print("\n🔍 PHASE 5: Apollo Enrichment")
        print("-" * 40)
        
        # Find US leads file
        us_files = list(self.output_dir.glob("*us_only*.csv"))
        if not us_files:
            print("❌ No US leads file found for Apollo enrichment")
            return False
        
        latest_us_file = max(us_files, key=lambda f: f.stat().st_mtime)
        
        # Run Apollo enrichment
        original_cwd = os.getcwd()
        os.chdir(SCRIPTS_DIR)
        
        try:
            # Copy US file to scripts directory
            temp_us_file = Path("US_ONLY_100_LEADS_FINAL.csv")
            shutil.copy(str(latest_us_file), str(temp_us_file))
            
            cmd = [sys.executable, "apollo_enrichment.py"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Apollo enrichment completed")
                
                # Move enriched results
                for file in Path(".").glob("*apollo_enriched*.csv"):
                    if file.is_file():
                        shutil.move(str(file), str(self.output_dir / file.name))
                
                # Clean up
                temp_us_file.unlink(missing_ok=True)
                return True
            else:
                print(f"❌ Apollo enrichment failed: {result.stderr}")
                return False
        finally:
            os.chdir(original_cwd)


def main():
    parser = argparse.ArgumentParser(
        description='CI/DevOps Bottom-up Campaign Launcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fresh GitHub scraping campaign
  python launch_campaign.py --mode fresh --max-repos 200
  
  # Use existing data
  python launch_campaign.py --mode existing
  
  # Full pipeline with Apollo enrichment
  python launch_campaign.py --mode full --apollo
  
  # US-only campaign
  python launch_campaign.py --mode existing --us-only
        """
    )
    
    parser.add_argument('--mode', choices=['fresh', 'existing', 'full'], required=True,
                       help='Campaign mode: fresh (GitHub scraping), existing (analyze current data), full (both)')
    parser.add_argument('--max-repos', type=int, default=100,
                       help='Maximum repositories to process (fresh mode)')
    parser.add_argument('--us-only', action='store_true',
                       help='Filter to US-only leads')
    parser.add_argument('--apollo', action='store_true',
                       help='Enrich with Apollo API (requires APOLLO_API_KEY)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without executing')
    
    args = parser.parse_args()
    
    # Initialize launcher
    launcher = CICampaignLauncher()
    launcher.print_header()
    
    if args.dry_run:
        print("\n🧪 DRY RUN MODE - No actual processing")
        print(f"Would run mode: {args.mode}")
        print(f"Would process max repos: {args.max_repos}")
        print(f"US-only filter: {args.us_only}")
        print(f"Apollo enrichment: {args.apollo}")
        return
    
    success = False
    
    try:
        if args.mode in ['fresh', 'full']:
            success = launcher.run_fresh_github_scraping(args.max_repos)
            if not success:
                print("❌ Fresh scraping failed, falling back to existing data")
        
        if args.mode in ['existing', 'full'] or not success:
            success = launcher.run_existing_data_analysis()
        
        if success:
            launcher.filter_and_clean_leads()
            
            if args.us_only:
                launcher.filter_us_only()
            
            if args.apollo:
                launcher.run_apollo_enrichment()
            
            launcher.generate_campaign_summary()
        
    except KeyboardInterrupt:
        print("\n⏹️  Campaign interrupted by user")
    except Exception as e:
        print(f"\n❌ Campaign error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
