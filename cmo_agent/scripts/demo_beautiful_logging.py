#!/usr/bin/env python3
"""
Demo script showing beautiful logging in action
Run this to see the enhanced logging system working!
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

from cmo_agent.obs.beautiful_logging import setup_beautiful_logging
from cmo_agent.core.state import DEFAULT_CONFIG

async def simulate_campaign():
    """Simulate a CMO Agent campaign with beautiful logging"""

    # Setup beautiful logging
    config = DEFAULT_CONFIG.copy()
    config['logging']['beautiful_console'] = True
    config['logging']['job_specific_files'] = True

    job_id = f"demo-{int(time.time())}"
    beautiful_logger = setup_beautiful_logging(config, job_id)

    print("🚀 CMO Agent Campaign Demo")
    print("=" * 50)
    print(f"Job ID: {job_id}")
    print("Watch the beautiful logging in action!\n")

    # Stage 1: Discovery
    beautiful_logger.start_stage("discovery", "Searching for OSS Python repositories")
    await asyncio.sleep(1)

    for i in range(1, 4):
        repos_found = i * 15
        beautiful_logger.log_progress(f"Scanning repository page {i}",
                                     current=repos_found, total=46)
        await asyncio.sleep(0.8)

    beautiful_logger.end_stage("Repository discovery completed", found=46, scanned=150)
    await asyncio.sleep(0.5)

    # Stage 2: Extraction
    beautiful_logger.start_stage("extraction", "Extracting contributors from repositories")
    await asyncio.sleep(1)

    for i in range(1, 5):
        contributors = i * 25
        beautiful_logger.log_progress(f"Processing repository batch {i}",
                                     current=contributors, total=99)
        await asyncio.sleep(0.7)

    beautiful_logger.end_stage("Contributor extraction completed", extracted=99, repos=46)
    await asyncio.sleep(0.5)

    # Stage 3: Enrichment
    beautiful_logger.start_stage("enrichment", "Enriching user profiles and finding emails")
    await asyncio.sleep(1)

    # Simulate user enrichment
    for i in range(1, 4):
        users = i * 33
        beautiful_logger.log_progress(f"Enriching user profiles",
                                     current=min(users, 99), total=99)
        await asyncio.sleep(0.6)

    await asyncio.sleep(0.5)

    # Simulate email discovery
    beautiful_logger.log_stage_event("processing", "Scanning commit history for email addresses")
    await asyncio.sleep(1.5)

    # Simulate finding very few emails (like the real scenario)
    beautiful_logger.log_stage_event("warning", "Most users have no recent commit activity")
    await asyncio.sleep(0.5)

    beautiful_logger.end_stage("Profile enrichment completed",
                              enriched=99, emails_found=1, noreply_filtered=45)
    await asyncio.sleep(0.5)

    # Stage 4: Validation
    beautiful_logger.start_stage("validation", "Validating emails and scoring leads")
    await asyncio.sleep(1)

    beautiful_logger.log_progress("Validating email addresses", current=1, total=1)
    await asyncio.sleep(0.8)

    beautiful_logger.log_progress("Calculating ICP scores", current=1, total=1)
    await asyncio.sleep(0.8)

    beautiful_logger.end_stage("Lead validation completed", validated=1, qualified=1)
    await asyncio.sleep(0.5)

    # Stage 5: Personalization
    beautiful_logger.start_stage("personalization", "Creating personalized email content")
    await asyncio.sleep(1)

    beautiful_logger.log_stage_event("processing", "Analyzing contributor profiles for personalization")
    await asyncio.sleep(1.2)

    beautiful_logger.log_stage_event("processing", "Generating personalized email templates")
    await asyncio.sleep(1.0)

    beautiful_logger.end_stage("Email personalization completed", personalized=1)
    await asyncio.sleep(0.5)

    # Stage 6: Sending (Dry Run)
    beautiful_logger.start_stage("sending", "Preparing emails for delivery (DRY RUN)")
    await asyncio.sleep(1)

    beautiful_logger.log_stage_event("dry_run", "DRY RUN mode: No emails will actually be sent")
    await asyncio.sleep(0.8)

    beautiful_logger.log_stage_event("processing", "Validating email templates and recipients")
    await asyncio.sleep(1.0)

    beautiful_logger.end_stage("Email preparation completed", prepared=1, dry_run=True)
    await asyncio.sleep(0.5)

    # Stage 7: Export
    beautiful_logger.start_stage("export", "Exporting campaign results")
    await asyncio.sleep(1)

    beautiful_logger.log_stage_event("processing", f"Exporting leads to CSV: {job_id}_leads.csv")
    await asyncio.sleep(1.2)

    beautiful_logger.end_stage("Results exported successfully", exported=1, format="CSV")
    await asyncio.sleep(0.5)

    # Final completion
    beautiful_logger.start_stage("completed", "Campaign finalization")
    await asyncio.sleep(0.8)

    beautiful_logger.end_stage("Campaign completed successfully! 🎉",
                              status="completed",
                              total_leads=1,
                              repos_discovered=46,
                              contributors_found=99,
                              emails_discovered=1,
                              duration_minutes=15)

    print("\n" + "=" * 50)
    print("✨ Demo completed!")
    print(f"📁 Check the log file: ./logs/{job_id}.log")
    print("🎨 This is what your campaigns will look like with beautiful logging!")

def simulate_error_scenario():
    """Show how errors look in beautiful logging"""
    print("\n🚨 Error Scenario Demo")
    print("=" * 30)

    config = DEFAULT_CONFIG.copy()
    beautiful_logger = setup_beautiful_logging(config, "error-demo")

    beautiful_logger.start_stage("enrichment", "Attempting to enrich user profiles")

    # Simulate various errors
    try:
        raise ConnectionError("GitHub API rate limit exceeded")
    except Exception as e:
        beautiful_logger.log_error(e, "github_api")

    try:
        raise ValueError("Invalid email format: not-an-email")
    except Exception as e:
        beautiful_logger.log_error(e, "email_validation")

    try:
        raise TimeoutError("Request timed out after 30 seconds")
    except Exception as e:
        beautiful_logger.log_error(e, "api_request")

    beautiful_logger.end_stage("Enrichment failed due to errors", status="failed")

    print("✅ Error demo completed - see how clear error reporting is!")

async def main():
    """Run the beautiful logging demo"""
    print("🎨 Beautiful Logging Demo for CMO Agent")
    print("🌟 Experience the enhanced observability system!")
    print("\n" + "=" * 60 + "\n")

    # Main campaign simulation
    await simulate_campaign()

    # Error scenario
    simulate_error_scenario()

    print("\n" + "=" * 60)
    print("🎉 Beautiful Logging Demo Complete!")
    print("📚 Key Features Demonstrated:")
    print("  ✅ Stage-aware logging with emojis and colors")
    print("  ✅ Progress tracking within stages")
    print("  ✅ Job-specific log files")
    print("  ✅ Structured error reporting")
    print("  ✅ Correlation IDs for tracing")
    print("  ✅ Beautiful console output")
    print("  ✅ JSON file logging for machine parsing")
    print("\n🚀 Ready to enhance your CMO Agent campaigns!")

if __name__ == "__main__":
    asyncio.run(main())
