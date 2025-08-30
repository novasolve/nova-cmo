#!/usr/bin/env python3
"""
Concurrent Processor
Handles parallel processing of repositories with rate limiting and caching
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path


@dataclass
class ProcessingResult:
    """Result of processing a single repository"""
    repo_full_name: str
    success: bool
    prospects: List[Dict[str, Any]]
    error: Optional[str] = None
    processing_time: float = 0.0


class ConcurrentProcessor:
    """Processes repositories concurrently with rate limiting and caching"""

    def __init__(self, max_workers: int = 4, requests_per_hour: int = 2000, cache_dir: str = ".cache"):
        self.max_workers = max_workers
        self.requests_per_hour = requests_per_hour
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Rate limiting
        self.request_times: List[float] = []
        self.min_request_interval = 3600 / requests_per_hour  # seconds between requests

        # GitHub rate limit tracking
        self.github_rate_limit_remaining = 5000
        self.github_rate_limit_reset = None

        # Cache settings
        self.cache_ttl_hours = 24  # Cache results for 24 hours to reduce API calls

    def _get_cache_key(self, repo_full_name: str, params: Dict[str, Any]) -> str:
        """Generate cache key for repository processing"""
        key_data = {
            'repo': repo_full_name,
            'params': params
        }
        key_str = json.dumps(key_data, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path"""
        return self.cache_dir / f"{cache_key}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is still valid"""
        if not cache_path.exists():
            return False

        cache_age = time.time() - cache_path.stat().st_mtime
        return cache_age < (self.cache_ttl_hours * 3600)

    def _load_cache(self, cache_path: Path) -> Optional[Dict[str, Any]]:
        """Load cached result"""
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    def _save_cache(self, cache_path: Path, result: Dict[str, Any]):
        """Save result to cache"""
        try:
            with open(cache_path, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass  # Silently fail if caching fails

    def _enforce_rate_limit(self):
        """Enforce rate limiting by waiting if necessary"""
        current_time = time.time()

        # Check GitHub rate limit first (if available)
        if self.github_rate_limit_reset and self.github_rate_limit_remaining <= 50:
            reset_time = self.github_rate_limit_reset
            wait_time = reset_time - current_time
            if wait_time > 0:
                print(f"🛑 GitHub rate limit low ({self.github_rate_limit_remaining} remaining). Waiting {wait_time:.0f} seconds...")
                time.sleep(wait_time)
                # Reset after waiting
                self.github_rate_limit_remaining = 5000
                self.github_rate_limit_reset = None

        # Remove old request times
        cutoff_time = current_time - 3600  # Last hour
        self.request_times = [t for t in self.request_times if t > cutoff_time]

        # Check if we need to wait based on our own rate limiting
        if len(self.request_times) >= self.requests_per_hour:
            # Wait until we can make another request
            oldest_request = min(self.request_times)
            wait_time = 3600 - (current_time - oldest_request)
            if wait_time > 0:
                print(f"⏱️  Local rate limit reached. Waiting {wait_time:.0f} seconds...")
                time.sleep(wait_time)

        # Also enforce minimum interval between requests
        if len(self.request_times) > 1:
            time_since_last = current_time - self.request_times[-2]
            if time_since_last < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last
                time.sleep(sleep_time)

        # Record this request
        self.request_times.append(current_time)

    def update_github_rate_limit(self, response):
        """Update GitHub rate limit information from response headers"""
        if hasattr(response, 'headers'):
            if 'X-RateLimit-Remaining' in response.headers:
                try:
                    self.github_rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
                except ValueError:
                    pass

            if 'X-RateLimit-Reset' in response.headers:
                try:
                    self.github_rate_limit_reset = int(response.headers['X-RateLimit-Reset'])
                except ValueError:
                    pass

    def process_repositories_concurrent(
        self,
        repositories: List[Dict[str, Any]],
        processing_func: Callable[[Dict[str, Any]], ProcessingResult],
        params: Optional[Dict[str, Any]] = None
    ) -> List[ProcessingResult]:
        """Process repositories concurrently with caching and rate limiting"""

        if params is None:
            params = {}

        results = []
        cache_hits = 0
        cache_misses = 0

        # Check cache first
        cached_results = []
        to_process = []

        for repo in repositories:
            repo_full_name = repo.get('full_name') or 'unknown/unknown'
            cache_key = self._get_cache_key(repo_full_name, params)
            cache_path = self._get_cache_path(cache_key)

            if self._is_cache_valid(cache_path):
                cached_data = self._load_cache(cache_path)
                if cached_data:
                    cached_result = ProcessingResult(
                        repo_full_name=repo_full_name,
                        success=cached_data['success'],
                        prospects=cached_data['prospects'],
                        error=cached_data.get('error'),
                        processing_time=cached_data.get('processing_time', 0.0)
                    )
                    cached_results.append(cached_result)
                    cache_hits += 1
                    continue

            to_process.append(repo)

        # Process remaining repositories concurrently
        if to_process:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_repo = {}

                for repo in to_process:
                    # Enforce rate limiting before submitting
                    self._enforce_rate_limit()

                    future = executor.submit(self._process_single_repo, repo, processing_func, params)
                    future_to_repo[future] = repo

                try:
                    for future in as_completed(future_to_repo):
                        repo = future_to_repo[future]
                        try:
                            result = future.result()
                            results.append(result)
                            cache_misses += 1

                            # Cache successful results
                            if result.success:
                                cache_key = self._get_cache_key(result.repo_full_name, params)
                                cache_path = self._get_cache_path(cache_key)
                                cache_data = {
                                    'success': result.success,
                                    'prospects': result.prospects,
                                    'error': result.error,
                                    'processing_time': result.processing_time,
                                    'cached_at': time.time()
                                }
                                self._save_cache(cache_path, cache_data)

                        except Exception as e:
                            error_result = ProcessingResult(
                                repo_full_name=repo.get('full_name') or 'unknown/unknown',
                                success=False,
                                prospects=[],
                                error=str(e),
                                processing_time=0.0
                            )
                            results.append(error_result)
                except KeyboardInterrupt:
                    print("\n⚠️  Keyboard interrupt detected. Cancelling pending tasks...")
                    # Cancel all pending futures
                    for future in future_to_repo:
                        future.cancel()
                    executor.shutdown(wait=False)
                    raise

        # Combine cached and fresh results
        all_results = cached_results + results

        print(f"📊 Processing complete: {cache_hits} cached, {cache_misses} fresh, {len(all_results)} total")

        return all_results

    def _process_single_repo(
        self,
        repo: Dict[str, Any],
        processing_func: Callable[[Dict[str, Any]], ProcessingResult],
        params: Dict[str, Any]
    ) -> ProcessingResult:
        """Process a single repository"""
        start_time = time.time()

        try:
            result = processing_func(repo)
            result.processing_time = time.time() - start_time
            return result
        except Exception as e:
            return ProcessingResult(
                repo_full_name=repo.get('full_name') or 'unknown/unknown',
                success=False,
                prospects=[],
                error=str(e),
                processing_time=time.time() - start_time
            )

    def clear_cache(self, older_than_hours: Optional[int] = None):
        """Clear cache files"""
        if older_than_hours is None:
            # Clear all cache
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
        else:
            # Clear old cache files
            cutoff_time = time.time() - (older_than_hours * 3600)
            for cache_file in self.cache_dir.glob("*.json"):
                if cache_file.stat().st_mtime < cutoff_time:
                    cache_file.unlink()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            'cache_files': len(cache_files),
            'total_size_mb': total_size / (1024 * 1024),
            'cache_dir': str(self.cache_dir)
        }

