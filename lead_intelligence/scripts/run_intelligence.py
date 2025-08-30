#!/usr/bin/env python3
"""
Lead Intelligence Runner
Command-line interface for the Lead Intelligence system
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.intelligence_engine import IntelligenceEngine, IntelligenceConfig
from core.beautiful_logger import beautiful_logger, log_header, log_separator

def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('lead_intelligence.log')
        ]
    )

def load_icp_options() -> Dict:
    """Load ICP configuration options"""
    icp_config_path = Path(__file__).parent.parent.parent / "configs" / "icp" / "options.yaml"
    try:
        import yaml
        with open(icp_config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"⚠️  Could not load ICP config: {e}")
        return {}

def print_icp_list():
    """Print list of available ICPs"""
    icp_options = load_icp_options()
    icps = icp_options.get('icp_options', [])

    if not icps:
        print("❌ No ICP options available")
        return

    print("🎯 Available ICPs (Ideal Customer Profiles):")
    print("=" * 70)
    print()

    for i, icp in enumerate(icps, 1):
        print(f"{i:2d}. {icp['id']}")
        print(f"    {icp['name']}")
        if 'personas' in icp:
            personas = icp['personas']
            if isinstance(personas, list) and personas:
                if 'title_contains' in personas[0]:
                    titles = personas[0]['title_contains']
                    print(f"    🎭 Target: {', '.join(titles[:3])}")
        if 'technographics' in icp:
            tech = icp['technographics']
            if 'language' in tech:
                print(f"    💻 Tech: {', '.join(tech['language'])}")
        print()

def parse_simple_args(args_list):
    """Parse simple natural language style arguments"""
    config = {
        'max_repos': 50,
        'max_leads': 200,
        'search_days': 60,
        'icp': None,
        'interactive': False
    }

    i = 0
    while i < len(args_list):
        arg = args_list[i].lower()

        # Handle number + unit patterns
        if arg.isdigit():
            num = int(arg)
            if i + 1 < len(args_list):
                next_arg = args_list[i + 1].lower()

                # Handle "50 repos", "100 leads", "30 days" patterns
                if 'repo' in next_arg:
                    config['max_repos'] = num
                    i += 2
                    continue
                elif 'lead' in next_arg:
                    config['max_leads'] = num
                    i += 2
                    continue
                elif 'day' in next_arg:
                    config['search_days'] = num
                    i += 2
                    continue

        # Handle ICP patterns
        if arg in ['icp', 'target']:
            if i + 1 < len(args_list):
                icp_name = args_list[i + 1]
                # Map common names to ICP IDs
                icp_mapping = {
                    'pypi': 'icp01_pypi_maintainers',
                    'python': 'icp01_pypi_maintainers',
                    'ml': 'icp02_ml_ds_maintainers',
                    'ai': 'icp02_ml_ds_maintainers',
                    'saas': 'icp03_seed_series_a_python_saas',
                    'api': 'icp04_api_sdk_tooling',
                    'academic': 'icp05_academic_labs',
                    'university': 'icp05_academic_labs',
                    'django': 'icp06_django_flask_products',
                    'flask': 'icp06_django_flask_products',
                    'fintech': 'icp07_regulated_startups',
                    'agency': 'icp08_agencies_consultancies',
                    'pytest': 'icp09_pytest_ci_plugin_authors',
                    'flaky': 'icp10_explicit_flaky_signals'
                }

                # Check if it's a direct ICP ID or mapped name
                if icp_name.startswith('icp'):
                    config['icp'] = icp_name
                else:
                    config['icp'] = icp_mapping.get(icp_name, icp_name)
                i += 2
                continue

        # Handle simple commands
        if arg in ['interactive', 'i']:
            config['interactive'] = True
            i += 1
            continue
        elif arg == 'help':
            return None  # Will show help
        elif arg == 'list':
            if i + 1 < len(args_list) and args_list[i + 1].lower() == 'icps':
                return {'command': 'list_icps'}
            i += 1
            continue

        # Handle direct ICP names (like "pypi", "ml", etc.)
        if arg in ['pypi', 'python', 'ml', 'ai', 'saas', 'api', 'academic', 'university',
                  'django', 'flask', 'fintech', 'agency', 'pytest', 'flaky']:
            icp_mapping = {
                'pypi': 'icp01_pypi_maintainers',
                'python': 'icp01_pypi_maintainers',
                'ml': 'icp02_ml_ds_maintainers',
                'ai': 'icp02_ml_ds_maintainers',
                'saas': 'icp03_seed_series_a_python_saas',
                'api': 'icp04_api_sdk_tooling',
                'academic': 'icp05_academic_labs',
                'university': 'icp05_academic_labs',
                'django': 'icp06_django_flask_products',
                'flask': 'icp06_django_flask_products',
                'fintech': 'icp07_regulated_startups',
                'agency': 'icp08_agencies_consultancies',
                'pytest': 'icp09_pytest_ci_plugin_authors',
                'flaky': 'icp10_explicit_flaky_signals'
            }
            config['icp'] = icp_mapping.get(arg, arg)
            i += 1
            continue

        i += 1

    return config

def print_simple_help():
    """Print simple usage help"""
    print("🚀 Lead Intelligence System - Super Simple Usage")
    print("=" * 55)
    print()
    print("NATURAL LANGUAGE COMMANDS:")
    print("  python run_intelligence.py 50 repos 100 leads")
    print("  python run_intelligence.py pypi 25 repos")
    print("  python run_intelligence.py ml 90 days")
    print("  python run_intelligence.py interactive")
    print("  python run_intelligence.py list icps")
    print()
    print("TRADITIONAL FLAGS:")
    print("  python run_intelligence.py --interactive")
    print("  python run_intelligence.py --list-icps")
    print("  python run_intelligence.py --max-repos 100 --icp icp01_pypi_maintainers")
    print()
    print("GETTING STARTED:")
    print("  1. export GITHUB_TOKEN=your_github_token")
    print("  2. python run_intelligence.py 50 repos pypi")

def main():
    import sys

    # Initialize variables for both code paths
    simple_config = None
    pipeline_already_run = False

    # Check if we have simple arguments (no dashes) or help
    if len(sys.argv) == 1:
        # No arguments - show help
        print_simple_help()
        return
    elif len(sys.argv) > 1:
        # Check if we have mixed arguments (some with -, some without)
        args_with_dash = [arg for arg in sys.argv[1:] if arg.startswith('-')]
        args_without_dash = [arg for arg in sys.argv[1:] if not arg.startswith('-')]

        # Initialize simple_config
        simple_config = None

        if args_without_dash:
            # We have simple arguments - try to parse them
            simple_config = parse_simple_args(args_without_dash)
            if simple_config is None:
                # Show help for simple case
                print_simple_help()
                return
            elif isinstance(simple_config, dict) and simple_config.get('command') == 'list_icps':
                print_icp_list()
                return
            elif simple_config and simple_config.get('interactive'):
                return run_interactive_mode()

        # Create args object from simple config and dash arguments
        args = type('Args', (), {
            'interactive': False,
            'list_icps': '--list-icps' in sys.argv,
            'max_repos': simple_config.get('max_repos', 50) if simple_config else 50,
            'max_leads': simple_config.get('max_leads', 200) if simple_config else 200,
            'search_days': simple_config.get('search_days', 60) if simple_config else 60,
            'icp': simple_config.get('icp') if simple_config else None,
            'config': 'lead_intelligence/config/intelligence.yaml',
            'github_token': "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",
            'base_config': 'config.yaml',
            'output_dir': 'lead_intelligence/data',
            'verbose': False,
            'dry_run': False,
            'phase': 'all',
            'demo': False,
            'location': 'us',
            'language': 'english',
            'english_only': bool('--english-only' in args_with_dash),
            'us_only': bool('--us-only' in args_with_dash)
        })()
    else:
        # Use argparse for traditional arguments
        parser = argparse.ArgumentParser(
            description='Lead Intelligence System - Find and qualify leads from GitHub',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
🚀 Super Simple Usage:

  # Just run with defaults
  python run_intelligence.py

  # Natural language style (no dashes!)
  python run_intelligence.py 50 repos 100 leads 30 days
  python run_intelligence.py pypi 25 repos
  python run_intelligence.py ml 90 days

  # Traditional flags still work
  python run_intelligence.py --
  interactive
  python run_intelligence.py --list-icps

🔑 Getting Started:
  1. Set token: export GITHUB_TOKEN=your_token_here
  2. Run: python run_intelligence.py 50 repos pypi
            """
        )

        parser.add_argument('--interactive', '-i', action='store_true', help='Run in interactive mode')
        parser.add_argument('--list-icps', action='store_true', help='List all available ICPs')
        parser.add_argument('--max-repos', type=int, default=50, help='Maximum repos to process')
        parser.add_argument('--max-leads', type=int, default=200, help='Maximum leads to collect')
        parser.add_argument('--search-days', type=int, default=60, help='Search repos active within N days')
        parser.add_argument('--icp', help='Target specific ICP')
        parser.add_argument('--config', default='lead_intelligence/config/intelligence.yaml', help='Intelligence configuration file')
        parser.add_argument('--github-token', help='GitHub API token')
        parser.add_argument('--base-config', default='config.yaml', help='Base GitHub scraper configuration file')
        parser.add_argument('--output-dir', default='lead_intelligence/data', help='Output directory for intelligence data')
        parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
        parser.add_argument('--phase', choices=['collect', 'analyze', 'report', 'all'], default='all', help='Run specific phase')
        parser.add_argument('--demo', action='store_true', help='Run in demo mode')

        # Filtering options
        parser.add_argument('--location', default='us', help='Filter by location (default: us)')
        parser.add_argument('--language', default='english', help='Filter by language (default: english)')
        parser.add_argument('--english-only', action='store_true', help='Only include English profiles')
        parser.add_argument('--us-only', action='store_true', help='Only include US-based profiles')

        args = parser.parse_args()

    # Handle special modes
    if hasattr(args, 'list_icps') and args.list_icps:
        print_icp_list()
        return

    if hasattr(args, 'interactive') and args.interactive:
        return run_interactive_mode()

    # Setup logging
    setup_logging(getattr(args, 'verbose', False))
    logger = logging.getLogger(__name__)

    # Check for GitHub token
    # HARDCODED TOKEN - Replace 'YOUR_ACTUAL_TOKEN_HERE' with your real token
    HARDCODED_TOKEN = "YOUR_ACTUAL_TOKEN_HERE"
    
    github_token = args.github_token or "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"
    if not github_token or github_token == "YOUR_ACTUAL_TOKEN_HERE":
        logger.error("❌ GitHub token required. Please update the HARDCODED_TOKEN variable")
        print("\nTo get a GitHub token:")
        print("1. Go to https://github.com/settings/tokens")
        print("2. Generate a new token with 'repo' and 'user:email' scopes")
        print("3. Replace 'YOUR_ACTUAL_TOKEN_HERE' with your actual token")
        sys.exit(1)

    # Check for base config
    base_config_path = getattr(args, 'base_config', 'config.yaml')
    if not Path(base_config_path).exists():
        logger.error(f"❌ Base config file not found: {base_config_path}")
        sys.exit(1)

    # Merge simple config with args
    if simple_config:
        if simple_config.get('max_repos') != 50:
            args.max_repos = simple_config['max_repos']
            logger.info(f"🔧 Setting max_repos to {args.max_repos}")
        if simple_config.get('max_leads') != 200:
            args.max_leads = simple_config['max_leads']
            logger.info(f"🔧 Setting max_leads to {args.max_leads}")
        if simple_config.get('search_days') != 60:
            args.search_days = simple_config['search_days']
            logger.info(f"🔧 Setting search_days to {args.search_days}")
        if simple_config.get('icp'):
            args.icp = simple_config['icp']
            logger.info(f"🎯 Targeting ICP: {args.icp}")

    # Override config with command line parameters
    if hasattr(args, 'max_repos') and args.max_repos != 50:
        logger.info(f"🔧 Overriding max_repos to {args.max_repos}")
    if hasattr(args, 'max_leads') and args.max_leads != 200:
        logger.info(f"🔧 Overriding max_leads to {args.max_leads}")
    if hasattr(args, 'search_days') and args.search_days != 60:
        logger.info(f"🔧 Overriding search_days to {args.search_days}")

    # Load intelligence config if it exists
    intelligence_config_data = {}
    config_path = getattr(args, 'config', 'lead_intelligence/config/intelligence.yaml')
    if Path(config_path).exists():
        try:
            import yaml
            with open(config_path, 'r') as f:
                intelligence_config_data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load intelligence config: {e}")

    # Get Attio credentials from environment
    attio_token = os.environ.get(intelligence_config_data.get('attio_api_token_env', 'ATTIO_API_TOKEN'), '')
    attio_workspace = os.environ.get(intelligence_config_data.get('attio_workspace_id_env', 'ATTIO_WORKSPACE_ID'), '')

    # Create intelligence config
    config = IntelligenceConfig(
        github_token=github_token,
        base_config_path=base_config_path,
        output_dir=getattr(args, 'output_dir', 'lead_intelligence/data'),
        analysis_dir=intelligence_config_data.get('analysis_dir', 'lead_intelligence/analysis'),
        reporting_dir=intelligence_config_data.get('reporting_dir', 'lead_intelligence/reporting'),
        enrichment_enabled=intelligence_config_data.get('enrichment_enabled', True),
        scoring_enabled=intelligence_config_data.get('scoring_enabled', True),
        max_workers=intelligence_config_data.get('max_workers', 4),
        cache_ttl_hours=intelligence_config_data.get('cache_ttl_hours', 24),
        validation_enabled=intelligence_config_data.get('validation_enabled', True),
        error_handling_enabled=intelligence_config_data.get('error_handling_enabled', True),
        attio_integration_enabled=intelligence_config_data.get('attio_integration_enabled', bool(attio_token)),
        attio_api_token=attio_token,
        backup_enabled=intelligence_config_data.get('backup_enabled', True),
        logging_level=intelligence_config_data.get('logging_level', 'INFO'),
        max_repos=getattr(args, 'max_repos', 50),
        max_leads=getattr(args, 'max_leads', 200),
        # Filtering options
        location_filter=getattr(args, 'location', 'us'),
        language_filter=getattr(args, 'language', 'english'),
        english_only=getattr(args, 'english_only', True),
        us_only=getattr(args, 'us_only', True)
    )

    if args.dry_run:
        print("🔍 DRY RUN MODE")
        print("Configuration:")
        print(f"  GitHub Token: {'*' * 20}...{github_token[-4:] if github_token else 'None'}")
        print(f"  Base Config: {base_config_path}")
        print(f"  Intelligence Config: {config_path}")
        print(f"  Output Directory: {getattr(args, 'output_dir', 'lead_intelligence/data')}")
        print(f"  Phase: {getattr(args, 'phase', 'all')}")
        print(f"  Enrichment: {config.enrichment_enabled}")
        print(f"  Scoring: {config.scoring_enabled}")
        print("Would run intelligence engine with above configuration.")
        return

    log_header("🚀 Lead Intelligence System v2.0")
    beautiful_logger.logger.info(f"Phase: {args.phase}")
    beautiful_logger.logger.info(f"Output Directory: {args.output_dir}")

    try:
        # Create and run intelligence engine
        engine = IntelligenceEngine(config)

        if args.phase == 'collect':
            logger.info("📊 Running data collection phase only")
            import asyncio
            prospects = asyncio.run(engine.collect_data())
            logger.info(f"✅ Collected {len(prospects)} prospects")
            return 0
        elif args.phase == 'analyze':
            logger.info("🧠 Running analysis phase only")
            # Load latest collected data and analyze
            latest_data_file = engine.data_manager.get_latest_file("raw_prospects_*.json", "raw")
            if not latest_data_file:
                logger.error("❌ No collected data found. Run collection phase first.")
                return 1

            with open(latest_data_file, 'r') as f:
                raw_data = json.load(f)

            # Convert back to Prospect objects (simplified)
            prospects = []
            for item in raw_data:
                # This is a simplified conversion - in practice you'd want full Prospect reconstruction
                from github_prospect_scraper import Prospect
                # Create basic prospect from dict - this would need more work for full fidelity
                prospect = Prospect(
                    lead_id=item.get('lead_id', ''),
                    login=item.get('login', ''),
                    repo_full_name=item.get('repo_full_name', ''),
                    signal=item.get('signal', ''),
                    signal_type=item.get('signal_type', ''),
                    signal_at=item.get('signal_at', ''),
                    github_user_url=item.get('github_user_url', ''),
                    github_repo_url=item.get('github_repo_url', '')
                )
                prospects.append(prospect)

            import asyncio
            intelligent_leads = asyncio.run(engine.analyze_and_enrich(prospects))
            logger.info(f"✅ Analyzed {len(intelligent_leads)} leads")
            return 0
        elif args.phase == 'report':
            logger.info("📊 Running reporting phase only")
            # Load latest analyzed data and generate reports
            latest_data_file = engine.data_manager.get_latest_file("intelligent_leads.json", "processed")
            if not latest_data_file:
                logger.error("❌ No analyzed data found. Run analysis phase first.")
                return 1

            with open(latest_data_file, 'r') as f:
                intelligent_leads_data = json.load(f)

            # Convert back to LeadIntelligence objects (simplified)
            intelligent_leads = []
            for item in intelligent_leads_data:
                # This would need full reconstruction logic
                pass

            import asyncio
            report_results = asyncio.run(engine.generate_reports(intelligent_leads))
            logger.info("✅ Generated reports")
            return 0
        elif args.phase == 'all':
            if args.demo:
                logger.info("🎭 Running in DEMO mode with sample data")
                import asyncio
                result = asyncio.run(engine.run_demo_cycle())
            else:
                logger.info("🔄 Running comprehensive intelligence pipeline")
                import asyncio
                result = asyncio.run(engine.run_intelligence_cycle())

            if result['success']:
                logger.info("✅ Lead Intelligence Pipeline completed successfully!")

                # Show detailed results
                metadata = result.get('pipeline_metadata', {})
                summary = metadata.get('summary', {})

                logger.info("📊 Pipeline Summary:")
                logger.info(f"   • Total leads processed: {summary.get('total_leads_processed', 0)}")
                logger.info(f"   • Monday wave qualified: {summary.get('monday_wave_size', 0)}")
                logger.info(f"   • Conversion rate: {summary.get('conversion_rate', 0)*100:.1f}%")

                # Mark that pipeline has been run
                pipeline_already_run = True

                # Return to prevent argparse path from running
                return 0

                # Show phase results
                phases = metadata.get('phases', {})
                if phases.get('enrichment'):
                    logger.info(f"   • Repos enriched: {phases['enrichment'].get('repos_snapshots_created', 0)}")
                if phases.get('scoring'):
                    high_priority = phases['scoring'].get('high_priority_count', 0)
                    logger.info(f"   • High-priority leads: {high_priority}")
                if phases.get('export'):
                    files_created = len(phases['export'].get('files', []))
                    logger.info(f"   • Export files created: {files_created}")

                # Show export results
                export_results = result.get('export_results', {})
                if export_results.get('success'):
                    logger.info("📁 Export files created:")
                    files = export_results.get('files', {})
                    for file_type, filename in files.items():
                        logger.info(f"   • {file_type}: {filename}")

                    campaign_dir = export_results.get('campaign_dir', '')
                    if campaign_dir:
                        logger.info(f"   • Campaign directory: {campaign_dir}")

                # Show CRM integration results
                if phases.get('crm_integration'):
                    crm = phases['crm_integration']
                    if crm.get('attio_push_attempted'):
                        logger.info("🔗 Attio integration attempted")
                    linear_tasks = crm.get('linear_tasks_prepared', 0)
                    if linear_tasks > 0:
                        logger.info(f"📋 Linear tasks prepared: {linear_tasks}")

            else:
                logger.error("❌ Intelligence pipeline failed")
                metadata = result.get('pipeline_metadata', {})
                errors = metadata.get('errors', [])
                if errors:
                    logger.error("Pipeline errors:")
                    for error in errors[:3]:  # Show first 3 errors
                        logger.error(f"   • {error.get('error', 'Unknown error')}")
                return 1

    except KeyboardInterrupt:
        logger.info("⏹️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error running intelligence system: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def get_user_input(prompt: str, default: str = "", validator=None) -> str:
    """Get user input with validation"""
    while True:
        try:
            value = input(f"{prompt} [{default}]: ").strip()
            if not value:
                value = default
            if validator and not validator(value):
                continue
            return value
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            sys.exit(1)
        except EOFError:
            return default

def get_user_choice(prompt: str, options: List[str], default_idx: int = 0) -> str:
    """Get user choice from list of options"""
    print(f"\n{prompt}")
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    print(f"  0. Cancel")

    while True:
        try:
            choice = input(f"Choose (1-{len(options)}) [{default_idx + 1}]: ").strip()
            if not choice:
                return options[default_idx]
            idx = int(choice) - 1
            if idx == -1:
                print("❌ Cancelled")
                sys.exit(1)
            if 0 <= idx < len(options):
                return options[idx]
        except (ValueError, IndexError):
            print(f"❌ Please enter a number between 1 and {len(options)}")
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            sys.exit(1)

def interactive_icp_selection(icp_options: Dict) -> Optional[Dict]:
    """Interactive ICP selection"""
    icps = icp_options.get('icp_options', [])
    if not icps:
        print("❌ No ICP options available")
        return None

    print("\n🎯 Available ICPs (Ideal Customer Profiles):")
    print("=" * 60)

    options = []
    for icp in icps:
        options.append(f"{icp['id']}: {icp['name']}")

    selected_icp_name = get_user_choice("Select an ICP to target:", options)
    selected_icp_id = selected_icp_name.split(':')[0]

    # Find the selected ICP
    for icp in icps:
        if icp['id'] == selected_icp_id:
            return icp

    return None

def interactive_config_setup() -> Dict:
    """Interactive configuration setup"""
    print("🚀 Lead Intelligence System - Interactive Setup")
    print("=" * 50)

    config = {}

    # GitHub token
    github_token = "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"
    if not github_token:
        print("\n🔑 GitHub Token Setup:")
        print("You need a GitHub token to collect data.")
        print("Get one at: https://github.com/settings/tokens")
        github_token = get_user_input("Enter your GitHub token", "")

    if github_token:
        config['github_token'] = github_token

    # Load ICP options
    icp_options = load_icp_options()

    # ICP Selection
    selected_icp = interactive_icp_selection(icp_options)
    if selected_icp:
        config['selected_icp'] = selected_icp

    # Parameters
    print("\n⚙️  Collection Parameters:")

    # Max repos
    max_repos = get_user_input("Maximum repos to process", "50",
                              lambda x: x.isdigit() and 1 <= int(x) <= 1000)
    config['max_repos'] = int(max_repos)

    # Max leads
    max_leads = get_user_input("Maximum leads to collect", "200",
                              lambda x: x.isdigit() and 1 <= int(x) <= 2000)
    config['max_leads'] = int(max_leads)

    # Search days
    search_days = get_user_input("Search repos active within last N days", "60",
                                lambda x: x.isdigit() and 1 <= int(x) <= 365)
    config['search_days'] = int(search_days)

    # Output directory
    output_dir = get_user_input("Output directory", "lead_intelligence/data")
    config['output_dir'] = output_dir

    return config

def run_interactive_mode():
    """Run the system in interactive mode"""
    print("🎭 Starting Interactive Mode...")

    # Setup interactive config
    config = interactive_config_setup()

    if not config.get('github_token'):
        print("❌ GitHub token required. Please set GITHUB_TOKEN environment variable.")
        return

    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    print("\n🚀 Starting Lead Intelligence with your configuration:")
    print(f"  • GitHub Token: {'*' * 20}...{config['github_token'][-4:]}")
    print(f"  • Max Repos: {config['max_repos']}")
    print(f"  • Max Leads: {config['max_leads']}")
    print(f"  • Search Window: {config['search_days']} days")
    print(f"  • Output: {config['output_dir']}")

    if config.get('selected_icp'):
        icp = config['selected_icp']
        print(f"  • ICP: {icp['name']} ({icp['id']})")

    # Confirm
    confirm = get_user_input("\nReady to start? (y/N)", "y")
    if confirm.lower() not in ['y', 'yes']:
        print("❌ Cancelled")
        return

    # Create intelligence config
    intelligence_config_data = {}
    intelligence_config_path = Path("lead_intelligence/config/intelligence.yaml")
    if intelligence_config_path.exists():
        try:
            import yaml
            with open(intelligence_config_path, 'r') as f:
                intelligence_config_data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load intelligence config: {e}")

    # Override with user selections
    if config.get('selected_icp'):
        # Apply ICP-specific settings to base config
        icp = config['selected_icp']
        if 'github' in icp and 'repo_queries' in icp['github']:
            # This would modify the base config with ICP-specific queries
            logger.info(f"Applying ICP: {icp['name']}")

    # Create and run engine
    intel_config = IntelligenceConfig(
        github_token=config['github_token'],
        base_config_path='config.yaml',
        output_dir=config['output_dir'],
        enrichment_enabled=True,
        scoring_enabled=True,
        max_workers=4,
        validation_enabled=True,
        error_handling_enabled=True,
        logging_level='INFO',
        # Filtering options - default to US and English only
        location_filter='us',
        language_filter='english',
        english_only=True,
        us_only=True
    )

    try:
        engine = IntelligenceEngine(intel_config)
        logger.info("🔄 Running intelligence pipeline...")

        import asyncio
        result = asyncio.run(engine.run_intelligence_cycle())

        if result['success']:
            print("\n✅ Success! Intelligence pipeline completed.")
            metadata = result.get('pipeline_metadata', {})
            summary = metadata.get('summary', {})
            print(f"📊 Results: {summary.get('total_leads_processed', 0)} leads processed")
        else:
            print("\n❌ Pipeline failed")
            return 1

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return 1

if __name__ == '__main__':
    main()
