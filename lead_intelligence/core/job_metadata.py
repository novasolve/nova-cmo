#!/usr/bin/env python3
"""
Job Metadata
Tracks processing runs with reproducible hashes and structured output
"""

import hashlib
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

from .timezone_utils import utc_now, to_utc_iso8601


@dataclass
class JobStats:
    """Statistics for a processing job"""
    total_repos_processed: int = 0
    total_prospects_found: int = 0
    prospects_with_email: int = 0
    prospects_with_linkedin: int = 0
    prospects_maintainers: int = 0
    prospects_org_members: int = 0
    prospects_contactable: int = 0
    tier_a_count: int = 0
    tier_b_count: int = 0
    tier_c_count: int = 0
    rejected_count: int = 0
    processing_time_seconds: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0


@dataclass
class JobMetadata:
    """Complete metadata for a processing job"""
    job_id: str
    started_at: str
    config_hash: str
    icp_hash: str
    query_hash: str
    stats: JobStats
    parameters: Dict[str, Any]
    output_files: Dict[str, str]
    errors: List[str]
    warnings: List[str]
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert JobStats to dict
        data['stats'] = asdict(self.stats)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobMetadata':
        """Create from dictionary"""
        # Convert stats back to JobStats
        stats_data = data.pop('stats', {})
        stats = JobStats(**stats_data)
        return cls(stats=stats, **data)


class JobTracker:
    """Tracks processing jobs and manages metadata"""

    def __init__(self, output_dir: str = "lead_intelligence/data"):
        self.output_dir = Path(output_dir)
        self.jobs_dir = self.output_dir / "jobs"
        self.jobs_dir.mkdir(exist_ok=True)

    def create_job(self, config: Dict[str, Any], icp_config: Optional[Dict[str, Any]] = None) -> JobMetadata:
        """Create a new job with metadata"""
        job_id = self._generate_job_id()
        started_at = to_utc_iso8601(utc_now())

        # Generate hashes for reproducibility
        config_hash = self._hash_dict(config)
        icp_hash = self._hash_dict(icp_config) if icp_config else ""
        query_hash = self._generate_query_hash(config, icp_config)

        # Extract parameters for logging
        parameters = self._extract_parameters(config, icp_config)

        job = JobMetadata(
            job_id=job_id,
            started_at=started_at,
            config_hash=config_hash,
            icp_hash=icp_hash,
            query_hash=query_hash,
            stats=JobStats(),
            parameters=parameters,
            output_files={},
            errors=[],
            warnings=[]
        )

        return job

    def complete_job(self, job: JobMetadata, stats: JobStats) -> JobMetadata:
        """Mark job as completed and save metadata"""
        job.completed_at = to_utc_iso8601(utc_now())
        job.stats = stats

        # Save metadata
        self._save_job_metadata(job)

        return job

    def save_output_file(self, job: JobMetadata, file_type: str, file_path: str) -> None:
        """Record an output file for the job"""
        job.output_files[file_type] = file_path
        self._save_job_metadata(job)

    def add_error(self, job: JobMetadata, error: str) -> None:
        """Add an error to the job"""
        job.errors.append(error)
        self._save_job_metadata(job)

    def add_warning(self, job: JobMetadata, warning: str) -> None:
        """Add a warning to the job"""
        job.warnings.append(warning)
        self._save_job_metadata(job)

    def _generate_job_id(self) -> str:
        """Generate a unique job ID"""
        timestamp = utc_now().strftime('%Y%m%d_%H%M%S')
        random_suffix = hashlib.md5(str(utc_now()).encode()).hexdigest()[:6]
        return f"{timestamp}_{random_suffix}"

    def _hash_dict(self, data: Optional[Dict[str, Any]]) -> str:
        """Generate hash for a dictionary"""
        if not data:
            return ""

        # Sort keys for consistent hashing
        sorted_data = json.dumps(data, sort_keys=True)
        return hashlib.md5(sorted_data.encode()).hexdigest()[:12]

    def _generate_query_hash(self, config: Dict[str, Any], icp_config: Optional[Dict[str, Any]]) -> str:
        """Generate a hash representing the search query"""
        query_components = []

        # Add search query
        if 'search' in config and 'query' in config['search']:
            query_components.append(config['search']['query'])

        # Add ICP components
        if icp_config:
            if 'include_topics' in icp_config:
                query_components.extend(icp_config['include_topics'])
            if 'exclude_topics' in icp_config:
                query_components.extend([f"-{topic}" for topic in icp_config['exclude_topics']])
            if 'languages' in icp_config:
                query_components.extend(icp_config['languages'])
            if 'min_stars' in icp_config:
                query_components.append(f"stars:{icp_config['min_stars']}")

        # Generate hash
        query_str = '|'.join(sorted(query_components))
        return hashlib.md5(query_str.encode()).hexdigest()[:12]

    def _extract_parameters(self, config: Dict[str, Any], icp_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract key parameters for logging"""
        params = {}

        # Extract from main config
        if 'limits' in config:
            params.update({
                'max_repos': config['limits'].get('max_repos'),
                'max_people': config['limits'].get('max_people'),
                'per_repo_prs': config['limits'].get('per_repo_prs'),
                'per_repo_commits': config['limits'].get('per_repo_commits')
            })

        if 'search' in config:
            params.update({
                'search_query': config['search'].get('query'),
                'sort': config['search'].get('sort'),
                'order': config['search'].get('order')
            })

        # Extract from ICP config
        if icp_config:
            params.update({
                'icp_languages': icp_config.get('languages', []),
                'icp_include_topics': icp_config.get('include_topics', []),
                'icp_exclude_topics': icp_config.get('exclude_topics', []),
                'icp_min_stars': icp_config.get('min_stars'),
                'icp_window_days': icp_config.get('window_days'),
                'icp_company_whitelist': icp_config.get('company_whitelist', [])
            })

        return params

    def _save_job_metadata(self, job: JobMetadata) -> None:
        """Save job metadata to file"""
        metadata_file = self.jobs_dir / f"{job.job_id}_metadata.json"

        with open(metadata_file, 'w') as f:
            json.dump(job.to_dict(), f, indent=2)

    def load_job(self, job_id: str) -> Optional[JobMetadata]:
        """Load job metadata from file"""
        metadata_file = self.jobs_dir / f"{job_id}_metadata.json"

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, 'r') as f:
                data = json.load(f)
            return JobMetadata.from_dict(data)
        except Exception:
            return None

    def list_jobs(self, limit: int = 10) -> List[JobMetadata]:
        """List recent jobs"""
        job_files = sorted(self.jobs_dir.glob("*_metadata.json"),
                          key=lambda x: x.stat().st_mtime, reverse=True)

        jobs = []
        for job_file in job_files[:limit]:
            try:
                with open(job_file, 'r') as f:
                    data = json.load(f)
                jobs.append(JobMetadata.from_dict(data))
            except Exception:
                continue

        return jobs

    def print_job_summary(self, job: JobMetadata) -> None:
        """Print a formatted summary of the job"""
        print(f"\n📊 Job Summary: {job.job_id}")
        print(f"Started: {job.started_at}")
        if job.completed_at:
            print(f"Completed: {job.completed_at}")
        print(f"Query Hash: {job.query_hash}")
        print(f"Config Hash: {job.config_hash}")
        if job.icp_hash:
            print(f"ICP Hash: {job.icp_hash}")

        stats = job.stats
        print(f"\n📈 Statistics:")
        print(f"  • Repos processed: {stats.total_repos_processed}")
        print(f"  • Prospects found: {stats.total_prospects_found}")
        print(f"  • With email: {stats.prospects_with_email}")
        print(f"  • With LinkedIn: {stats.prospects_with_linkedin}")
        print(f"  • Maintainers: {stats.prospects_maintainers}")
        print(f"  • Org members: {stats.prospects_org_members}")
        print(f"  • Contactable: {stats.prospects_contactable}")
        print(f"  • Tier A: {stats.tier_a_count} | B: {stats.tier_b_count} | C: {stats.tier_c_count} | Rejected: {stats.rejected_count}")
        print(f"  • Processing time: {stats.processing_time_seconds:.1f}s")
        if stats.cache_hits + stats.cache_misses > 0:
            cache_rate = stats.cache_hits / (stats.cache_hits + stats.cache_misses) * 100
            print(f"  • Cache: {stats.cache_hits} hits, {cache_rate:.1f}% hit rate")

        if job.output_files:
            print(f"\n💾 Output Files:")
            for file_type, file_path in job.output_files.items():
                print(f"  • {file_type}: {file_path}")

        if job.errors:
            print(f"\n❌ Errors ({len(job.errors)}):")
            for error in job.errors[:5]:  # Show first 5
                print(f"  • {error}")
            if len(job.errors) > 5:
                print(f"  • ... and {len(job.errors) - 5} more")

        if job.warnings:
            print(f"\n⚠️  Warnings ({len(job.warnings)}):")
            for warning in job.warnings[:3]:  # Show first 3
                print(f"  • {warning}")
            if len(job.warnings) > 3:
                print(f"  • ... and {len(job.warnings) - 3} more")
