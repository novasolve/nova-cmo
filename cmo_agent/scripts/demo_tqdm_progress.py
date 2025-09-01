#!/usr/bin/env python3
"""
Demo script showing tqdm-style progress bars with live email counting
"""
import asyncio
import sys
import time
import random
from pathlib import Path

# Ensure project root on sys.path
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from cmo_agent.obs.beautiful_logging import LiveProgressTracker, setup_beautiful_logging
from cmo_agent.core.state import DEFAULT_CONFIG

async def simulate_user_enrichment():
    """Simulate enriching user profiles with progress tracking"""
    print("👤 User Profile Enrichment Demo")
    print("=" * 40)

    users = ["alice", "bob", "charlie", "david", "eve", "frank", "grace", "henry", "iris", "jack"]

    # Start progress tracker
    progress = LiveProgressTracker(
        description="👤 Enriching user profiles",
        total=len(users),
        show_emails=False
    )

    for i, user in enumerate(users):
        # Simulate API call delay
        await asyncio.sleep(random.uniform(0.2, 0.8))

        # Update progress
        progress.update(1)

        # Occasionally update description
        if i == 3:
            progress.set_description("👤 Enriching profiles (getting detailed info)")
        elif i == 7:
            progress.set_description("👤 Enriching profiles (finalizing)")

    progress.close()
    print("✅ User enrichment completed!\n")

async def simulate_email_discovery():
    """Simulate email discovery with live email counting"""
    print("📧 Email Discovery Demo (The Main Event!)")
    print("=" * 50)

    users = [
        "maintainer1", "contributor2", "developer3", "coder4", "pythonista5",
        "hacker6", "engineer7", "architect8", "devops9", "analyst10",
        "researcher11", "scientist12", "student13", "freelancer14", "consultant15",
        "startup16", "enterprise17", "opensource18", "github19", "gitlab20"
    ]

    # Start progress tracker with email counting
    progress = LiveProgressTracker(
        description="🔍 Scanning commit history for emails",
        total=len(users),
        show_emails=True
    )

    total_emails_found = 0

    for i, user in enumerate(users):
        # Simulate commit scanning delay
        await asyncio.sleep(random.uniform(0.3, 1.2))

        # Simulate finding emails (most users won't have any, just like real scenario)
        emails_found = 0
        if random.random() < 0.15:  # 15% chance of finding emails (realistic!)
            emails_found = random.randint(1, 3)
            total_emails_found += emails_found

        # Update progress with email count
        progress.update(1, emails_found)

        # Update description based on progress
        if i == 5:
            progress.set_description("🔍 Scanning commits (checking author emails)")
        elif i == 10:
            progress.set_description("🔍 Scanning commits (checking committer emails)")
        elif i == 15:
            progress.set_description("🔍 Scanning commits (final repositories)")

    progress.close()
    print(f"✅ Email discovery completed! Found {total_emails_found} emails total\n")
    return total_emails_found

async def simulate_email_validation():
    """Simulate email validation with progress tracking"""
    print("✉️  Email Validation Demo")
    print("=" * 30)

    # Simulate having found a few emails
    emails = ["dev@example.com", "maintainer@project.org", "contributor@opensource.dev"]

    progress = LiveProgressTracker(
        description="✉️  Validating email addresses",
        total=len(emails),
        show_emails=False
    )

    for email in emails:
        # Simulate MX record check delay
        await asyncio.sleep(random.uniform(0.5, 1.0))
        progress.update(1)

    progress.close()
    print("✅ Email validation completed!\n")

async def simulate_full_campaign():
    """Simulate a full campaign with multiple progress stages"""
    print("🚀 Full Campaign Simulation with Live Progress")
    print("=" * 60)

    # Stage 1: Repository Discovery
    print("📁 Stage 1: Repository Discovery")
    repos_progress = LiveProgressTracker("🔍 Searching repositories", total=50, show_emails=False)
    for i in range(50):
        await asyncio.sleep(0.05)  # Fast simulation
        repos_progress.update(1)
    repos_progress.close()
    print("✅ Found 50 repositories\n")

    # Stage 2: Contributor Extraction
    print("⚡ Stage 2: Contributor Extraction")
    contributors_progress = LiveProgressTracker("⚡ Extracting contributors", total=50, show_emails=False)
    for i in range(50):
        await asyncio.sleep(0.08)
        contributors_progress.update(1)
    contributors_progress.close()
    print("✅ Extracted 99 contributors\n")

    # Stage 3: Profile Enrichment
    print("👤 Stage 3: Profile Enrichment")
    await simulate_user_enrichment()

    # Stage 4: Email Discovery (The main event!)
    print("🔍 Stage 4: Email Discovery")
    emails_found = await simulate_email_discovery()

    # Stage 5: Email Validation
    if emails_found > 0:
        print("✉️  Stage 5: Email Validation")
        await simulate_email_validation()

    print("🎉 Campaign completed successfully!")
    print(f"📊 Final Results: {emails_found} leads with valid email addresses")

async def demonstrate_tqdm_features():
    """Demonstrate various tqdm features"""
    print("\n🎨 Advanced Progress Bar Features")
    print("=" * 40)

    # Test different progress bar styles
    print("📈 Processing with rate display:")
    progress1 = LiveProgressTracker("📈 Processing items", total=20, show_emails=False)
    for i in range(20):
        await asyncio.sleep(0.1)
        progress1.update(1)
    progress1.close()

    print("\n📧 Email discovery with live count:")
    progress2 = LiveProgressTracker("📧 Finding emails", total=15, show_emails=True)
    emails = 0
    for i in range(15):
        await asyncio.sleep(0.15)
        # Simulate occasional email discovery
        found = 1 if random.random() < 0.2 else 0
        emails += found
        progress2.update(1, found)
    progress2.close()

    print("\n🔄 Dynamic description updates:")
    progress3 = LiveProgressTracker("🔄 Processing", total=10, show_emails=False)
    for i in range(10):
        if i == 3:
            progress3.set_description("🔄 Processing (phase 2)")
        elif i == 7:
            progress3.set_description("🔄 Processing (finalizing)")

        await asyncio.sleep(0.2)
        progress3.update(1)
    progress3.close()

async def main():
    """Run all progress tracking demos"""
    print("📊 CMO Agent Progress Tracking Demo")
    print("🎯 Featuring: tqdm-style bars + live email counting!")
    print("=" * 70)

    # Check if tqdm is available
    try:
        import tqdm
        print("✅ tqdm is available - you'll see beautiful progress bars!")
    except ImportError:
        print("⚠️  tqdm not available - using fallback progress display")

    print("\n" + "=" * 70)

    # Demo individual components
    await simulate_user_enrichment()
    emails_found = await simulate_email_discovery()

    if emails_found > 0:
        await simulate_email_validation()

    # Demo advanced features
    await demonstrate_tqdm_features()

    print("\n" + "=" * 70)

    # Full campaign simulation
    await simulate_full_campaign()

    print("\n" + "=" * 70)
    print("🎉 Demo Complete!")
    print("💡 Key Features Demonstrated:")
    print("  ✅ tqdm-style progress bars")
    print("  ✅ Live email counting during discovery")
    print("  ✅ Real-time rate display")
    print("  ✅ Dynamic description updates")
    print("  ✅ Multi-stage campaign tracking")
    print("  ✅ Fallback for terminals without tqdm")
    print("\n🚀 Your CMO Agent campaigns will now show live progress!")
    print("📧 Watch email counts update in real-time as discovery happens!")

if __name__ == "__main__":
    asyncio.run(main())
