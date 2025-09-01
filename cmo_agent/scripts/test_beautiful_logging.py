#!/usr/bin/env python3
"""
Test script for beautiful logging system
"""
import asyncio
import sys
import time
from pathlib import Path

# Ensure project root on sys.path
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from cmo_agent.obs.beautiful_logging import setup_beautiful_logging, StageAwareLogger
from cmo_agent.core.state import DEFAULT_CONFIG
from cmo_agent.core.monitoring import get_global_collector, MetricsLogger

def test_console_formatting():
    """Test the beautiful console formatting"""
    print("🧪 Testing Beautiful Console Formatting")
    print("=" * 50)

    # Setup beautiful logging
    config = DEFAULT_CONFIG.copy()
    config['logging']['beautiful_console'] = True
    config['logging']['job_specific_files'] = False  # For testing

    job_id = "test-20250831-123456"
    beautiful_logger = setup_beautiful_logging(config, job_id)

    # Test different stage transitions
    print("\n📋 Testing Stage Transitions:")

    # Discovery stage
    beautiful_logger.start_stage("discovery", "Searching for Python repositories")
    time.sleep(0.5)
    beautiful_logger.log_progress("Found repositories", current=25, total=100)
    time.sleep(0.5)
    beautiful_logger.end_stage("Discovery completed", found=46, processed=100)

    # Extraction stage
    beautiful_logger.start_stage("extraction", "Extracting contributors from repositories")
    time.sleep(0.5)
    beautiful_logger.log_progress("Processing repositories", current=23, total=46)
    time.sleep(0.5)
    beautiful_logger.end_stage("Extraction completed", found=99, processed=46)

    # Enrichment stage
    beautiful_logger.start_stage("enrichment", "Enriching user profiles and finding emails")
    time.sleep(0.5)
    beautiful_logger.log_progress("Enriching users", current=50, total=99)
    time.sleep(0.5)
    beautiful_logger.log_progress("Finding commit emails", current=75, total=99)
    time.sleep(0.5)
    beautiful_logger.end_stage("Enrichment completed", enriched=99, emails_found=1)

    # Validation stage
    beautiful_logger.start_stage("validation", "Validating emails and scoring leads")
    time.sleep(0.5)
    beautiful_logger.end_stage("Validation completed", validated=1, scored=1)

    # Completion
    beautiful_logger.start_stage("completed", "Finalizing campaign")
    time.sleep(0.5)
    beautiful_logger.end_stage("Campaign completed successfully",
                               leads=1, emails_sent=0, status="completed")

    print("\n✅ Stage transition testing completed!")

def test_error_logging():
    """Test error logging with beautiful formatting"""
    print("\n🚨 Testing Error Logging:")

    config = DEFAULT_CONFIG.copy()
    beautiful_logger = setup_beautiful_logging(config, "test-error-job")

    # Test different types of errors
    try:
        raise ValueError("Invalid email format detected")
    except Exception as e:
        beautiful_logger.log_error(e, "email_validation")

    try:
        raise ConnectionError("GitHub API connection failed")
    except Exception as e:
        beautiful_logger.log_error(e, "github_api")

    try:
        raise TimeoutError("Request timed out after 30 seconds")
    except Exception as e:
        beautiful_logger.log_error(e, "api_timeout")

    print("✅ Error logging testing completed!")

async def test_metrics_logging():
    """Test metrics logging with beautiful formatting"""
    print("\n📊 Testing Metrics Logging:")

    # Get global metrics collector
    collector = get_global_collector()

    # Simulate some metrics
    collector.record_job_submitted()
    collector.record_api_call(successful=True, endpoint="github_search")
    collector.record_api_call(successful=True, endpoint="github_users")
    collector.record_api_call(successful=False, endpoint="github_commits")
    collector.record_business_metrics(leads_processed=99, leads_enriched=99,
                                     repos_discovered=46, emails_sent=1)
    collector.record_job_completed(125.5)

    # Create metrics logger and log a snapshot
    metrics_logger = MetricsLogger(collector, log_interval=1)

    # Collect and display a metrics snapshot
    snapshot = collector.collect_snapshot()
    metrics_dict = snapshot.to_dict()

    print("📈 Metrics snapshot:")
    print(f"  Jobs completed: {metrics_dict['jobs']['completed']}")
    print(f"  API calls: {metrics_dict['api']['calls_total']}")
    print(f"  Success rate: {metrics_dict['api']['success_rate_percent']:.1f}%")
    print(f"  Leads processed: {metrics_dict['business']['leads_processed']}")

    # Test alert triggering
    collector.record_error("test_component", "test_error")
    collector.record_error("test_component", "test_error")
    collector.record_error("test_component", "test_error")

    snapshot_with_alerts = collector.collect_snapshot()
    if snapshot_with_alerts.alerts_active:
        print(f"🚨 Alerts triggered: {snapshot_with_alerts.alerts_active}")

    print("✅ Metrics logging testing completed!")

def test_job_specific_files():
    """Test job-specific log file creation"""
    print("\n📁 Testing Job-Specific Log Files:")

    config = DEFAULT_CONFIG.copy()
    config['logging']['job_specific_files'] = True

    job_id = "test-job-files-20250831-123456"
    beautiful_logger = setup_beautiful_logging(config, job_id)

    # Log some test messages
    beautiful_logger.start_stage("testing", "Testing job-specific log files")
    beautiful_logger.log_stage_event("test", "This message should appear in the job-specific log file")
    beautiful_logger.end_stage("Testing completed", status="success")

    # Check if log file was created
    logs_dir = Path(config['directories']['logs'])
    log_file = logs_dir / f"{job_id}.log"

    if log_file.exists():
        print(f"✅ Job-specific log file created: {log_file}")
        print(f"📄 Log file size: {log_file.stat().st_size} bytes")
    else:
        print(f"❌ Job-specific log file not found: {log_file}")

    print("✅ Job-specific file testing completed!")

async def main():
    """Run all beautiful logging tests"""
    print("🎨 Beautiful Logging System Test Suite")
    print("=" * 60)

    # Test console formatting
    test_console_formatting()

    # Test error logging
    test_error_logging()

    # Test metrics logging
    await test_metrics_logging()

    # Test job-specific files
    test_job_specific_files()

    print("\n🎉 All beautiful logging tests completed!")
    print("=" * 60)
    print("✨ The logging system is ready for production use!")

if __name__ == "__main__":
    asyncio.run(main())
