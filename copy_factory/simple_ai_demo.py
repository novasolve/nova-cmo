#!/usr/bin/env python3
"""
Simple AI Copy Factory Demo
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.storage import CopyFactoryStorage

def simple_demo():
    """Simple demo of AI Copy Factory"""

    print("🚀 AI-Powered Copy Factory")
    print("=" * 40)

    storage = CopyFactoryStorage()

    # Show system stats
    icps = storage.list_icps()
    prospects = storage.list_prospects()
    prospects_with_emails = [p for p in prospects if p.has_email()]

    print(f"📊 System Status:")
    print(f"   ICP Profiles: {len(icps)}")
    print(f"   Total Prospects: {len(prospects)}")
    print(f"   Prospects with Emails: {len(prospects_with_emails)}")
    print(f"   Email Coverage: {len(prospects_with_emails)/len(prospects)*100:.1f}%")
    # Show sample ICPs
    if icps:
        print(f"\n🎯 Sample ICPs:")
        for icp in icps[:3]:
            print(f"   • {icp.name} ({icp.id})")

    # Show sample prospects
    if prospects_with_emails:
        print(f"\n👥 Sample Prospects with Emails:")
        for prospect in prospects_with_emails[:3]:
            email = prospect.get_best_email()
            print(f"   • {prospect.login}: {email}")

    print(f"\n✅ AI Copy Factory is ready!")
    print(f"🤖 AI capabilities include:")
    print(f"   • AI-powered copy generation")
    print(f"   • Smart ICP matching")
    print(f"   • Content analysis")
    print(f"   • Campaign automation")
    print(f"   • Performance optimization")
    print(f"   • Natural language commands")

    print("\n🎉 Going all in on AI for lead generation!")

if __name__ == '__main__':
    simple_demo()
