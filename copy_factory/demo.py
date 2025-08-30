#!/usr/bin/env python3
"""
Copy Factory Demo Script
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.factory import CopyFactory


def demo_copy_factory():
    """Demonstrate Copy Factory functionality"""

    print("🚀 Copy Factory Demo")
    print("=" * 50)

    # Initialize factory
    factory = CopyFactory()

    # Show ICPs
    print("\n📊 Available ICP Profiles:")
    icps = factory.storage.list_icps()
    for icp in icps[:5]:  # Show first 5
        print(f"  • {icp.name} ({icp.id})")

    # Show prospects with emails
    print(f"\n👥 Prospects with Emails:")
    all_prospects = factory.storage.list_prospects(limit=20)
    prospects_with_emails = [p for p in all_prospects if p.has_email()][:10]

    for prospect in prospects_with_emails:
        email = prospect.get_best_email()
        print(f"  • {prospect.login}: {email}")

    # Show templates
    print(f"\n📝 Available Templates:")
    templates = factory.storage.list_templates()
    for template in templates[:5]:  # Show first 5
        print(f"  • {template.name} ({template.template_type})")

    # Get stats
    print(f"\n📈 Statistics:")
    stats = factory.get_icp_stats()
    print(f"  • Total ICPs: {stats['total_icps']}")
    print(f"  • Total Prospects: {stats['total_prospects']}")
    print(f"  • Prospects with Emails: {stats['prospects_with_emails']}")
    print(f"  • Email Coverage: {stats['prospects_with_emails']/stats['total_prospects']*100:.1f}%")

    # Demonstrate copy generation
    if prospects_with_emails and templates:
        print(f"\n📧 Copy Generation Demo:")
        prospect = prospects_with_emails[0]
        template = templates[0]

        # Find the ICP for this template
        icp = factory.storage.get_icp(template.icp_id)

        if icp:
            copy_result = factory.generator.generate_copy(template, prospect, icp)
            print(f"  Subject: {copy_result.get('subject', 'N/A')}")
            print(f"  Body Preview: {copy_result['body'][:150]}...")
            print(f"  Variables Used: {len(copy_result.get('variables_used', {}))}")

    # Create a sample campaign
    print(f"\n🎯 Campaign Creation Demo:")
    if icps and templates:
        icp = icps[0]
        template = templates[0]

        campaign = factory.create_campaign(
            f"Demo Campaign - {icp.name}",
            icp.id,
            template.id
        )

        print(f"  Created campaign: {campaign.name}")
        print(f"  Prospects in campaign: {len(campaign.prospect_ids)}")
        print(f"  Campaign ID: {campaign.id}")

    print(f"\n✅ Copy Factory Demo Complete!")


if __name__ == '__main__':
    demo_copy_factory()
