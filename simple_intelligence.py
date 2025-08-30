#!/usr/bin/env python3
"""
Super Simple Lead Intelligence Runner
Natural language interface for the Lead Intelligence system
"""

import os
import sys
import subprocess

def run_simple_command(args):
    """Convert simple args to proper command"""
    import subprocess

    # Parse simple arguments into a config
    config = {
        'max_repos': 50,
        'max_leads': 200,
        'search_days': 60,
        'icp': None,
        'interactive': False,
        'list_icps': False,
        'dry_run': False
    }

    i = 0
    while i < len(args):
        arg = args[i].lower()

        # Handle number + unit patterns
        if arg.isdigit():
            num = int(arg)
            if i + 1 < len(args):
                next_arg = args[i + 1].lower()
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

        # ICP mapping
        icp_mapping = {
            'pypi': 'icp01_pypi_maintainers',
            'python': 'icp01_pypi_maintainers',
            'ml': 'icp02_ml_ds_maintainers',
            'ai': 'icp02_ml_ds_maintainers',
            'saas': 'icp03_seed_series_a_python_saas',
            'api': 'icp04_api_sdk_tooling',
            'academic': 'icp05_academic_labs',
            'django': 'icp06_django_flask_products',
            'flask': 'icp06_django_flask_products',
            'fintech': 'icp07_regulated_startups',
            'agency': 'icp08_agencies_consultancies',
            'pytest': 'icp09_pytest_ci_plugin_authors',
            'flaky': 'icp10_explicit_flaky_signals'
        }

        if arg in icp_mapping:
            config['icp'] = icp_mapping[arg]
        elif arg == 'interactive':
            config['interactive'] = True
        elif arg == 'list' and i + 1 < len(args) and args[i + 1].lower() == 'icps':
            config['list_icps'] = True
            i += 1
        elif arg == 'dry':
            config['dry_run'] = True

        i += 1

    # Execute directly instead of calling the complex script
    return run_intelligence_directly(config)

def run_intelligence_directly(config):
    """Run intelligence directly with the parsed config"""
    import os
    import json
    from pathlib import Path

    print("🚀 Lead Intelligence - Simple Mode")
    print(f"  • Max Repos: {config['max_repos']}")
    print(f"  • Max Leads: {config['max_leads']}")
    print(f"  • Search Days: {config['search_days']}")
    if config['icp']:
        print(f"  • ICP: {config['icp']}")
    print()

    if config['list_icps']:
        print("🎯 Available ICPs:")
        icps = [
            "icp01_pypi_maintainers - PyPI Maintainers",
            "icp02_ml_ds_maintainers - ML/Data Science",
            "icp03_seed_series_a_python_saas - Python SaaS",
            "icp04_api_sdk_tooling - API/SDK Teams",
            "icp05_academic_labs - University Labs",
            "icp06_django_flask_products - Django/Flask Teams",
            "icp07_regulated_startups - Fintech/Regulated",
            "icp08_agencies_consultancies - Agencies",
            "icp09_pytest_ci_plugin_authors - PyTest/CI Authors",
            "icp10_explicit_flaky_signals - Flaky Test Signals"
        ]
        for icp in icps:
            print(f"  {icp}")
        return

    if config['interactive']:
        print("🎭 Interactive mode not implemented in simple version")
        print("Use: python lead_intelligence/scripts/run_intelligence.py --interactive")
        return

    # Check for GitHub token
    github_token = "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"
    if not github_token:
        print("❌ Set your GitHub token:")
        print("  export GITHUB_TOKEN=your_github_token_here")
        return

    print("✅ Configuration looks good!")
    print("Ready to run intelligence with these settings.")
    print()
    print("To actually run, use:")
    print(f"  python lead_intelligence/scripts/run_intelligence.py --max-repos {config['max_repos']} --max-leads {config['max_leads']} --search-days {config['search_days']}" + (f" --icp {config['icp']}" if config['icp'] else ""))

def show_help():
    print("🚀 Lead Intelligence - Super Simple Interface")
    print("=" * 50)
    print()
    print("EXAMPLES:")
    print("  python simple_intelligence.py 50 repos 100 leads")
    print("  python simple_intelligence.py pypi 25 repos")
    print("  python simple_intelligence.py ml 90 days")
    print("  python simple_intelligence.py interactive")
    print("  python simple_intelligence.py list icps")
    print("  python simple_intelligence.py 30 repos saas dry")
    print()
    print("AVAILABLE TARGETS:")
    print("  pypi, python  → PyPI Maintainers")
    print("  ml, ai        → ML/AI Maintainers")
    print("  saas          → SaaS Companies")
    print("  api           → API/SDK Teams")
    print("  academic      → University Labs")
    print("  django, flask → Django/Flask Teams")
    print("  fintech       → Fintech/Regulated")
    print("  agency        → Agencies")
    print("  pytest        → PyTest/CI Authors")
    print("  flaky         → Flaky Test Signals")
    print()
    print("SETUP:")
    print("  export GITHUB_TOKEN=your_token_here")

def main():
    if len(sys.argv) == 1:
        show_help()
        return

    if sys.argv[1].lower() in ['help', '-h', '--help']:
        show_help()
        return

    # Execute simple command directly
    run_simple_command(sys.argv[1:])

if __name__ == '__main__':
    main()
