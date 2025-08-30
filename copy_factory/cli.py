#!/usr/bin/env python3
"""
Command Line Interface for Copy Factory
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Optional

from .core.factory import CopyFactory


class CopyFactoryCLI:
    """CLI for Copy Factory operations"""

    def __init__(self):
        self.factory = CopyFactory()

    def run(self):
        """Run the CLI"""
        parser = self._create_parser()
        args = parser.parse_args()

        if not hasattr(args, 'command'):
            parser.print_help()
            return

        try:
            getattr(self, f"cmd_{args.command}")(args)
        except AttributeError:
            print(f"Unknown command: {args.command}")
            parser.print_help()
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser"""
        parser = argparse.ArgumentParser(description="Copy Factory - ICP and Email Management System")
        parser.add_argument('--data-dir', default='copy_factory/data',
                           help='Data directory for Copy Factory')

        subparsers = parser.add_subparsers(dest='command', help='Available commands')

        # Import commands
        self._add_import_parsers(subparsers)

        # List commands
        self._add_list_parsers(subparsers)

        # Create commands
        self._add_create_parsers(subparsers)

        # Generate commands
        self._add_generate_parsers(subparsers)

        # Export commands
        self._add_export_parsers(subparsers)

        # Utility commands
        self._add_utility_parsers(subparsers)

        return parser

    def _add_import_parsers(self, subparsers):
        """Add import-related subparsers"""
        # Import ICPs
        icp_parser = subparsers.add_parser('import-icp', help='Import ICP profiles from YAML')
        icp_parser.add_argument('yaml_file', help='YAML file containing ICP definitions')
        icp_parser.add_argument('--auto-templates', action='store_true',
                               help='Automatically create default templates for imported ICPs')

        # Import prospects
        prospect_parser = subparsers.add_parser('import-prospects', help='Import prospects from CSV')
        prospect_parser.add_argument('csv_file', help='CSV file containing prospect data')
        prospect_parser.add_argument('--match-icps', action='store_true',
                                    help='Automatically match prospects to ICPs')

    def _add_list_parsers(self, subparsers):
        """Add list-related subparsers"""
        # List ICPs
        subparsers.add_parser('list-icps', help='List all ICP profiles')

        # List prospects
        prospect_list_parser = subparsers.add_parser('list-prospects', help='List prospects')
        prospect_list_parser.add_argument('--icp', help='Filter by ICP ID')
        prospect_list_parser.add_argument('--limit', type=int, help='Limit number of results')
        prospect_list_parser.add_argument('--has-email', action='store_true',
                                         help='Only show prospects with email addresses')

        # List templates
        template_list_parser = subparsers.add_parser('list-templates', help='List copy templates')
        template_list_parser.add_argument('--icp', help='Filter by ICP ID')

        # List campaigns
        campaign_list_parser = subparsers.add_parser('list-campaigns', help='List outreach campaigns')
        campaign_list_parser.add_argument('--status', help='Filter by campaign status')

    def _add_create_parsers(self, subparsers):
        """Add create-related subparsers"""
        # Create template
        template_parser = subparsers.add_parser('create-template', help='Create copy template')
        template_parser.add_argument('icp_id', help='ICP ID for the template')
        template_parser.add_argument('name', help='Template name')
        template_parser.add_argument('--type', default='email',
                                    choices=['email', 'linkedin', 'twitter'],
                                    help='Template type')

        # Create campaign
        campaign_parser = subparsers.add_parser('create-campaign', help='Create outreach campaign')
        campaign_parser.add_argument('name', help='Campaign name')
        campaign_parser.add_argument('icp_id', help='ICP ID for the campaign')
        campaign_parser.add_argument('template_id', help='Template ID to use')

    def _add_generate_parsers(self, subparsers):
        """Add generate-related subparsers"""
        # Generate copy
        copy_parser = subparsers.add_parser('generate-copy', help='Generate personalized copy')
        copy_parser.add_argument('campaign_id', help='Campaign ID to generate copy for')
        copy_parser.add_argument('--preview', action='store_true',
                                help='Preview generated copy without saving')

    def _add_export_parsers(self, subparsers):
        """Add export-related subparsers"""
        # Export campaign
        export_parser = subparsers.add_parser('export-campaign', help='Export campaign data')
        export_parser.add_argument('campaign_id', help='Campaign ID to export')
        export_parser.add_argument('output_file', help='Output CSV file path')

        # Export prospects
        export_prospects_parser = subparsers.add_parser('export-prospects', help='Export prospects data')
        export_prospects_parser.add_argument('output_file', help='Output CSV file path')
        export_prospects_parser.add_argument('--icp', help='Filter by ICP ID')

    def _add_utility_parsers(self, subparsers):
        """Add utility subparsers"""
        # Match prospects
        subparsers.add_parser('match-prospects', help='Match prospects to ICP profiles')

        # Stats
        subparsers.add_parser('stats', help='Show Copy Factory statistics')

        # Validate
        subparsers.add_parser('validate', help='Validate Copy Factory setup')

        # Preview template
        preview_parser = subparsers.add_parser('preview-template', help='Preview copy template')
        preview_parser.add_argument('template_id', help='Template ID to preview')

    # Command implementations
    def cmd_import_icp(self, args):
        """Import ICP profiles"""
        imported = self.factory.import_icp_from_yaml(args.yaml_file)
        print(f"✅ Imported {imported} ICP profiles")

        if args.auto_templates:
            icps = self.factory.storage.list_icps()
            templates_created = 0
            for icp in icps:
                try:
                    self.factory.create_icp_template(icp, "email")
                    templates_created += 1
                except Exception as e:
                    print(f"⚠️  Failed to create template for {icp.name}: {e}")

            print(f"✅ Created {templates_created} default templates")

    def cmd_import_prospects(self, args):
        """Import prospects"""
        imported = self.factory.import_prospects_from_csv(args.csv_file)
        print(f"✅ Imported {imported} prospects")

        if args.match_icps:
            matches = self.factory.match_prospects_to_icps()
            print(f"✅ Matched {len(matches)} prospects to ICPs")

    def cmd_list_icps(self, args):
        """List ICP profiles"""
        icps = self.factory.storage.list_icps()
        if not icps:
            print("No ICP profiles found")
            return

        print(f"\n📊 ICP Profiles ({len(icps)})")
        print("-" * 80)
        for icp in icps:
            print(f"ID: {icp.id}")
            print(f"Name: {icp.name}")
            print(f"Description: {icp.description or 'N/A'}")
            print(f"Triggers: {len(icp.triggers)}")
            print(f"GitHub Queries: {len(icp.github_queries)}")
            print("-" * 80)

    def cmd_list_prospects(self, args):
        """List prospects"""
        prospects = self.factory.storage.list_prospects(
            limit=args.limit,
            icp_filter=args.icp
        )

        if args.has_email:
            prospects = [p for p in prospects if p.has_email()]

        if not prospects:
            print("No prospects found")
            return

        print(f"\n👥 Prospects ({len(prospects)})")
        print("-" * 100)
        for prospect in prospects[:args.limit or 50]:  # Limit display
            email_status = "✅" if prospect.has_email() else "❌"
            print(f"{email_status} {prospect.login} | {prospect.name or 'N/A'} | {prospect.company or 'N/A'} | {prospect.get_best_email() or 'N/A'}")
        print("-" * 100)

    def cmd_list_templates(self, args):
        """List templates"""
        templates = self.factory.storage.list_templates(icp_id=args.icp)
        if not templates:
            print("No templates found")
            return

        print(f"\n📝 Copy Templates ({len(templates)})")
        print("-" * 80)
        for template in templates:
            print(f"ID: {template.id}")
            print(f"Name: {template.name}")
            print(f"Type: {template.template_type}")
            print(f"ICP: {template.icp_id}")
            print("-" * 80)

    def cmd_list_campaigns(self, args):
        """List campaigns"""
        campaigns = self.factory.storage.list_campaigns(status_filter=args.status)
        if not campaigns:
            print("No campaigns found")
            return

        print(f"\n🎯 Campaigns ({len(campaigns)})")
        print("-" * 80)
        for campaign in campaigns:
            print(f"ID: {campaign.id}")
            print(f"Name: {campaign.name}")
            print(f"ICP: {campaign.icp_id}")
            print(f"Template: {campaign.template_id}")
            print(f"Status: {campaign.status}")
            print(f"Prospects: {len(campaign.prospect_ids)}")
            print("-" * 80)

    def cmd_create_template(self, args):
        """Create copy template"""
        icp = self.factory.storage.get_icp(args.icp_id)
        if not icp:
            print(f"❌ ICP {args.icp_id} not found")
            return

        template = self.factory.create_icp_template(icp, args.type)
        print(f"✅ Created template: {template.name}")
        print(f"   ID: {template.id}")
        print(f"   Type: {template.template_type}")

    def cmd_create_campaign(self, args):
        """Create campaign"""
        # Verify ICP exists
        icp = self.factory.storage.get_icp(args.icp_id)
        if not icp:
            print(f"❌ ICP {args.icp_id} not found")
            return

        # Verify template exists
        template = self.factory.storage.get_template(args.template_id)
        if not template:
            print(f"❌ Template {args.template_id} not found")
            return

        campaign = self.factory.create_campaign(args.name, args.icp_id, args.template_id)
        print(f"✅ Created campaign: {campaign.name}")
        print(f"   ID: {campaign.id}")
        print(f"   Prospects: {len(campaign.prospect_ids)}")

    def cmd_generate_copy(self, args):
        """Generate copy"""
        try:
            copy_data = self.factory.generate_campaign_copy(args.campaign_id)

            if args.preview:
                print(f"\n📋 Preview - Generated copy for {len(copy_data)} prospects")
                for i, copy in enumerate(copy_data[:3]):  # Show first 3
                    print(f"\n--- Prospect {i+1} ---")
                    if copy.get('subject'):
                        print(f"Subject: {copy['subject']}")
                    print(f"Body: {copy['body'][:200]}...")
            else:
                print(f"✅ Generated copy for {len(copy_data)} prospects")

        except ValueError as e:
            print(f"❌ {e}")

    def cmd_export_campaign(self, args):
        """Export campaign"""
        try:
            exported = self.factory.export_campaign_data(args.campaign_id, args.output_file)
            print(f"✅ Exported {exported} copy items to {args.output_file}")
        except ValueError as e:
            print(f"❌ {e}")

    def cmd_export_prospects(self, args):
        """Export prospects"""
        exported = self.factory.storage.export_prospects_to_csv(args.output_file, args.icp)
        print(f"✅ Exported {exported} prospects to {args.output_file}")

    def cmd_match_prospects(self, args):
        """Match prospects to ICPs"""
        matches = self.factory.match_prospects_to_icps()
        print(f"✅ Matched {len(matches)} prospects to ICPs")

    def cmd_stats(self, args):
        """Show statistics"""
        stats = self.factory.get_icp_stats()

        print("\n📊 Copy Factory Statistics")
        print("=" * 40)
        print(f"Total ICPs: {stats['total_icps']}")
        print(f"Total Prospects: {stats['total_prospects']}")
        print(f"Prospects with Emails: {stats['prospects_with_emails']}")

        print(f"\n📈 ICP Breakdown:")
        for icp_id, data in stats['icp_breakdown'].items():
            print(f"  {data['name']}: {data['prospects_count']} prospects")

    def cmd_validate(self, args):
        """Validate setup"""
        validation = self.factory.validate_setup()

        if validation['valid']:
            print("✅ Copy Factory setup is valid!")
        else:
            print("⚠️  Setup issues found:")
            for issue in validation['issues']:
                print(f"  - {issue}")

        print("\n📊 Current Stats:")
        for key, value in validation['stats'].items():
            print(f"  {key}: {value}")

    def cmd_preview_template(self, args):
        """Preview template"""
        template = self.factory.storage.get_template(args.template_id)
        if not template:
            print(f"❌ Template {args.template_id} not found")
            return

        preview = self.factory.generator.preview_template(template)
        print(f"\n📋 Template Preview: {template.name}")
        print("=" * 50)
        if preview.get('subject'):
            print(f"Subject: {preview['subject']}")
        print(f"\nBody:\n{preview['body']}")


def main():
    """Main entry point"""
    cli = CopyFactoryCLI()
    cli.run()


if __name__ == '__main__':
    main()
