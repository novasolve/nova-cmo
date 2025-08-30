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
    cmd = [sys.executable, "lead_intelligence/scripts/run_intelligence.py"]

    # Parse simple arguments
    i = 0
    while i < len(args):
        arg = args[i].lower()
        if arg.isdigit():
            num = int(arg)
            if i + 1 < len(args):
                next_arg = args[i + 1].lower()
                if 'repo' in next_arg:
                    cmd.extend(['--max-repos', str(num)])
                    i += 2
                    continue
                elif 'lead' in next_arg:
                    cmd.extend(['--max-leads', str(num)])
                    i += 2
                    continue
                elif 'day' in next_arg:
                    cmd.extend(['--search-days', str(num)])
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
            cmd.extend(['--icp', icp_mapping[arg]])
        elif arg == 'interactive':
            cmd.append('--interactive')
        elif arg == 'list' and i + 1 < len(args) and args[i + 1].lower() == 'icps':
            cmd.append('--list-icps')
            i += 1
        elif arg == 'dry':
            cmd.append('--dry-run')

        i += 1

    return cmd

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

    # Convert simple args to proper command
    cmd = run_simple_command(sys.argv[1:])

    print(f"🚀 Running: {' '.join(cmd)}")
    print()

    # Execute the command
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()
