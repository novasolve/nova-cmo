#!/usr/bin/env python3
"""
Setup script for Copy Factory
"""

import sys
import os
from pathlib import Path
import argparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.factory import CopyFactory


def setup_copy_factory(args):
    """Initialize Copy Factory with existing data"""

    print("🚀 Setting up Copy Factory...")
    factory = CopyFactory(args.data_dir)

    # Step 1: Import ICP profiles
    if args.icp_yaml:
        print("\n📥 Importing ICP profiles...")
        imported_icps = factory.import_icp_from_yaml(args.icp_yaml)
        print(f"✅ Imported {imported_icps} ICP profiles")
    else:
        print("⚠️  No ICP YAML file specified, skipping ICP import")

    # Step 2: Import prospects
    if args.prospects_csv:
        print("\n📥 Importing prospects...")
        imported_prospects = factory.import_prospects_from_csv(args.prospects_csv)
        print(f"✅ Imported {imported_prospects} prospects")
    else:
        print("⚠️  No prospects CSV file specified, skipping prospect import")

    # Step 3: Match prospects to ICPs
    if args.match_prospects:
        print("\n🔗 Matching prospects to ICPs...")
        matches = factory.match_prospects_to_icps()
        print(f"✅ Matched {len(matches)} prospects to ICPs")

    # Step 4: Create default templates
    if args.create_templates:
        print("\n📝 Creating default templates...")
        icps = factory.storage.list_icps()
        templates_created = 0

        for icp in icps:
            try:
                factory.create_icp_template(icp, "email")
                templates_created += 1
            except Exception as e:
                print(f"⚠️  Failed to create template for {icp.name}: {e}")

        print(f"✅ Created {templates_created} default templates")

    # Step 5: Validation
    print("\n🔍 Validating setup...")
    validation = factory.validate_setup()

    if validation['valid']:
        print("✅ Copy Factory setup completed successfully!")
    else:
        print("⚠️  Setup completed with some issues:")
        for issue in validation['issues']:
            print(f"  - {issue}")

    print("\n📊 Final Statistics:")
    for key, value in validation['stats'].items():
        print(f"  {key}: {value}")

    return validation['valid']


def create_example_data(args):
    """Create example data for testing"""
    print("🎭 Creating example data...")

    factory = CopyFactory(args.data_dir)

    # Create example ICP
    from core.models import ICPProfile
    example_icp = ICPProfile(
        id="example_python_dev",
        name="Python Developer",
        description="Individual Python developers and maintainers",
        technographics={
            "language": ["Python"],
            "frameworks": ["Django", "Flask", "FastAPI"]
        },
        firmographics={
            "size": "1-50 employees",
            "geo": ["Global"]
        },
        triggers=[
            "Recent Python repository activity",
            "Open source contributions",
            "Python package maintenance"
        ]
    )

    factory.storage.save_icp(example_icp)
    print("✅ Created example ICP profile")

    # Create example template
    factory.create_icp_template(example_icp, "email")
    print("✅ Created example template")

    print("🎭 Example data created successfully!")


def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description="Setup Copy Factory")
    parser.add_argument('--data-dir', default='copy_factory/data',
                       help='Data directory for Copy Factory')
    parser.add_argument('--icp-yaml', default='configs/icp/options.yaml',
                       help='ICP configuration YAML file')
    parser.add_argument('--prospects-csv', default='data/prospects_latest.csv',
                       help='Prospects CSV file')
    parser.add_argument('--match-prospects', action='store_true',
                       help='Match prospects to ICPs after import')
    parser.add_argument('--create-templates', action='store_true',
                       help='Create default templates for ICPs')
    parser.add_argument('--example-data', action='store_true',
                       help='Create example data instead of importing')

    args = parser.parse_args()

    # Check if files exist
    if not args.example_data:
        if args.icp_yaml and not Path(args.icp_yaml).exists():
            print(f"❌ ICP YAML file not found: {args.icp_yaml}")
            sys.exit(1)

        if args.prospects_csv and not Path(args.prospects_csv).exists():
            print(f"❌ Prospects CSV file not found: {args.prospects_csv}")
            sys.exit(1)

    try:
        if args.example_data:
            create_example_data(args)
        else:
            success = setup_copy_factory(args)
            if not success:
                sys.exit(1)

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
