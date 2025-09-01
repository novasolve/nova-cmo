#!/usr/bin/env python3
"""
Job Metadata Tracker
Tracks processing runs with metadata, statistics, and reproducible parameters
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from .timezone_utils import utc_now, to_utc_iso8601


@dataclass
class JobStats:
    """Statistics for a processing job"""
    total_repos_processed: int = 0
    raw_prospects_found: int = 0
    prospects_after_dedupe: int = 0
    contactable_prospects: int = 0
    prospects_by_tier: Dict[str, int] = None
    maintainer_prospects: int = 0
    org_member_prospects: int = 0
    processing_time_seconds: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.prospects_by_tier is None:
            self.prospects_by_tier = {'A': 0, 'B': 0, 'C': 0, 'REJECT': 0}
        if self.errors is None:
            self.errors = []


@dataclass
class JobMetadata:
    """Complete metadata for a processing job"""
    job_id: str
    started_at: str
    query_hash: str
    config_hash: str
    ended_at: Optional[str] = None
    icp_config_hash: Optional[str] = None
    github_token_hash: str = ""
    window_days: int = 30
    max_repos: int = 40
    max_leads: int = 200
    concurrency_enabled: bool = False
    workers_used: int = 1
    search_query: str = ""
    exclude_filters: List[str] = None
    stats: JobStats = None
    output_files: Dict[str, str] = None
    success: bool = False

    def __post_init__(self):
        if self.exclude_filters is None:
            self.exclude_filters = []
        if self.stats is None:
            self.stats = JobStats()
        if self.output_files is None:
            self.output_files = {}


class JobTracker:
    """Tracks processing jobs and manages metadata"""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.jobs_dir = self.base_dir / "jobs"
        self.jobs_dir.mkdir(exist_ok=True)
        self.current_job: Optional[JobMetadata] = None

    def start_job(
        self,
        search_query: str,
        config: Dict[str, Any],
        icp_config: Optional[Dict[str, Any]] = None,
        github_token: str = ""
    ) -> JobMetadata:
        """Start a new processing job"""

        # Generate hashes for reproducibility
        query_hash = hashlib.md5(search_query.encode()).hexdigest()[:12]

        # Convert config to serializable format to avoid type comparison issues
        try:
            config_str = json.dumps(config, default=str)
            config_hash = hashlib.md5(config_str.encode()).hexdigest()[:12]
        except (TypeError, ValueError):
            # Fallback: convert to string representation
            config_str = str(sorted(config.items())) if hasattr(config, 'items') else str(config)
            config_hash = hashlib.md5(config_str.encode()).hexdigest()[:12]

        icp_hash = None
        if icp_config:
            try:
                icp_str = json.dumps(icp_config, default=str)
                icp_hash = hashlib.md5(icp_str.encode()).hexdigest()[:12]
            except (TypeError, ValueError):
                # Fallback: convert to string representation
                icp_str = str(sorted(icp_config.items())) if hasattr(icp_config, 'items') else str(icp_config)
                icp_hash = hashlib.md5(icp_str.encode()).hexdigest()[:12]

        # Generate job ID
        timestamp = utc_now().strftime('%Y%m%d_%H%M%S')
        job_id = f"job_{timestamp}_{query_hash}"

        # Create job metadata
        job = JobMetadata(
            job_id=job_id,
            started_at=to_utc_iso8601(utc_now()),
            query_hash=query_hash,
            config_hash=config_hash,
            icp_config_hash=icp_hash,
            github_token_hash=hashlib.md5(github_token.encode()).hexdigest()[:8] if github_token else "",
            window_days=config.get('filters', {}).get('activity_days', 30),
            max_repos=config.get('limits', {}).get('max_repos', 40),
            max_leads=config.get('limits', {}).get('max_people', 200),
            concurrency_enabled=config.get('concurrency', {}).get('enabled', False),
            workers_used=config.get('concurrency', {}).get('max_workers', 1),
            search_query=search_query
        )

        self.current_job = job
        return job

    def end_job(self, success: bool = True) -> JobMetadata:
        """End the current job"""
        if not self.current_job:
            raise ValueError("No active job to end")

        self.current_job.ended_at = to_utc_iso8601(utc_now())
        self.current_job.success = success

        if self.current_job.stats:
            self.current_job.stats.processing_time_seconds = (
                datetime.fromisoformat(self.current_job.ended_at) -
                datetime.fromisoformat(self.current_job.started_at)
            ).total_seconds()

        # Save job metadata
        self._save_job_metadata(self.current_job)

        return self.current_job

    def update_stats(self, stats: JobStats):
        """Update job statistics"""
        if self.current_job:
            self.current_job.stats = stats

    def add_output_file(self, file_type: str, file_path: str):
        """Add an output file to the job metadata"""
        if self.current_job:
            self.current_job.output_files[file_type] = file_path

    def add_error(self, error: str):
        """Add an error to the job"""
        if self.current_job and self.current_job.stats:
            self.current_job.stats.errors.append(error)

    def get_job_summary(self) -> str:
        """Get a formatted summary of the current job"""
        if not self.current_job:
            return "No active job"

        job = self.current_job
        stats = job.stats

        # Calculate percentages safely to avoid division by zero
        contactable_pct = f"{(stats.contactable_prospects / stats.prospects_after_dedupe * 100):.1f}%" if stats.prospects_after_dedupe > 0 else "N/A"
        maintainer_pct = f"{(stats.maintainer_prospects / stats.prospects_after_dedupe * 100):.1f}%" if stats.prospects_after_dedupe > 0 else "N/A"

        summary = f"""
📊 Phase 1: Data Collection
Job ID: {job.job_id}
QueryHash: {job.query_hash}
Window: {job.window_days}d | Max Repos: {job.max_repos} | Max Leads: {job.max_leads}
Started: {job.started_at}

📦 Processing Results:
Fetched: {stats.total_repos_processed} repos | Raw prospects: {stats.raw_prospects_found}
Deduped: {stats.prospects_after_dedupe} | Contactable: {stats.contactable_prospects} ({contactable_pct})
Maintainers: {stats.maintainer_prospects} ({maintainer_pct}) | Org Members: {stats.org_member_prospects}

🏆 Tier Distribution:
A: {stats.prospects_by_tier.get('A', 0)} | B: {stats.prospects_by_tier.get('B', 0)} | C: {stats.prospects_by_tier.get('C', 0)} | Rejected: {stats.prospects_by_tier.get('REJECT', 0)}

⚡ Performance:
Processing time: {stats.processing_time_seconds:.1f}s | Cache hits: {stats.cache_hits} | Cache misses: {stats.cache_misses}
Concurrency: {'Enabled' if job.concurrency_enabled else 'Disabled'} ({job.workers_used} workers)

📁 Output Files:
"""

        for file_type, file_path in job.output_files.items():
            summary += f"  - {file_type}: {file_path}\n"

        if stats.errors:
            summary += f"\n❌ Errors ({len(stats.errors)}):\n"
            for error in stats.errors[:5]:  # Show first 5 errors
                summary += f"  - {error}\n"
            if len(stats.errors) > 5:
                summary += f"  ... and {len(stats.errors) - 5} more\n"

        return summary.strip()

    def _save_job_metadata(self, job: JobMetadata):
        """Save job metadata to file"""
        job_file = self.jobs_dir / f"{job.job_id}_metadata.json"

        with open(job_file, 'w') as f:
            # Convert dataclasses to dicts for JSON serialization
            job_dict = asdict(job)
            json.dump(job_dict, f, indent=2, default=str)

    def load_job(self, job_id: str) -> Optional[JobMetadata]:
        """Load job metadata from file"""
        job_file = self.jobs_dir / f"{job_id}_metadata.json"

        if not job_file.exists():
            return None

        try:
            with open(job_file, 'r') as f:
                job_dict = json.load(f)

            # Reconstruct JobMetadata object
            stats_dict = job_dict.pop('stats', {})
            stats = JobStats(**stats_dict)
            job = JobMetadata(**job_dict)
            job.stats = stats

            return job
        except Exception:
            return None

    def list_recent_jobs(self, limit: int = 10) -> List[JobMetadata]:
        """List recent jobs"""
        job_files = sorted(
            self.jobs_dir.glob("*_metadata.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        jobs = []
        for job_file in job_files[:limit]:
            job_id = job_file.stem.replace('_metadata', '')
            job = self.load_job(job_id)
            if job:
                jobs.append(job)

        return jobs

    def get_job_history_stats(self) -> Dict[str, Any]:
        """Get statistics across all jobs"""
        jobs = self.list_recent_jobs(100)  # Last 100 jobs

        if not jobs:
            return {}

        total_jobs = len(jobs)
        successful_jobs = len([j for j in jobs if j.success])
        total_prospects = sum(j.stats.prospects_after_dedupe for j in jobs)
        total_contactable = sum(j.stats.contactable_prospects for j in jobs)

        return {
            'total_jobs': total_jobs,
            'success_rate': successful_jobs / total_jobs if total_jobs > 0 else 0,
            'avg_prospects_per_job': total_prospects / total_jobs if total_jobs > 0 else 0,
            'avg_contactable_rate': total_contactable / total_prospects if total_prospects > 0 else 0,
            'most_recent_job': jobs[0] if jobs else None
        }
