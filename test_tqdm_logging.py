#!/usr/bin/env python3
"""
Test script to verify tqdm progress bars are working in logging
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from cmo_agent.obs.beautiful_logging import setup_beautiful_logging
from cmo_agent.core.state import DEFAULT_CONFIG

async def test_tqdm_logging():
    """Test tqdm progress bars in logging context"""
    print("🧪 Testing tqdm Progress Bars in CMO Agent Logging")
    print("=" * 60)

    # Setup beautiful logging
    config = DEFAULT_CONFIG.copy()
    job_id = "test-tqdm-20250831-123456"

    beautiful_logger = setup_beautiful_logging(config, job_id)

    # Test 1: User Enrichment with Progress
    print("\n👤 Test 1: User Enrichment Progress")
    beautiful_logger.start_stage("enrichment", "Testing user profile enrichment")

    progress = beautiful_logger.start_progress("👤 Enriching user profiles", total=25, show_emails=False)
    for i in range(25):
        await asyncio.sleep(0.1)
        progress.update(1)
    progress.close()

    beautiful_logger.end_stage("User enrichment completed", enriched=25)

    # Test 2: Email Discovery with Live Email Counting
    print("\n📧 Test 2: Email Discovery with Live Email Counting")
    beautiful_logger.start_stage("email_discovery", "Testing email discovery with live counting")

    progress = beautiful_logger.start_progress("🔍 Finding commit emails", total=50, show_emails=True)
    emails_found = 0
    for i in range(50):
        await asyncio.sleep(0.08)
        # Simulate finding emails occasionally
        if i % 7 == 0:  # Find email every 7th user
            emails_found += 1
            progress.update(1, 1)  # +1 user, +1 email
        else:
            progress.update(1, 0)  # +1 user, +0 emails
    progress.close()

    beautiful_logger.end_stage("Email discovery completed", processed=50, emails_found=emails_found)

    # Test 3: Batch Processing
    print("\n⚡ Test 3: Batch Processing")
    beautiful_logger.start_stage("processing", "Testing batch processing")

    progress = beautiful_logger.start_progress("⚡ Processing batches", total=100, show_emails=False)
    for i in range(100):
        await asyncio.sleep(0.02)
        progress.update(1)

        # Update description at milestones
        if i == 25:
            progress.set_description("⚡ Processing batches (quarter done)")
        elif i == 50:
            progress.set_description("⚡ Processing batches (halfway)")
        elif i == 75:
            progress.set_description("⚡ Processing batches (almost done)")
    progress.close()

    beautiful_logger.end_stage("Batch processing completed", batches=100)

    print("\n✅ All tqdm progress bar tests completed!")
    print(f"📁 Check the log file: ./logs/{job_id}.log")

if __name__ == "__main__":
    asyncio.run(test_tqdm_logging())
