"""
Enhanced Artifacts Management System
"""
import json
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import gzip
import shutil

logger = logging.getLogger(__name__)


@dataclass
class ArtifactMetadata:
    """Metadata for an artifact"""
    artifact_id: str
    job_id: str
    filename: str
    path: str
    artifact_type: str
    size_bytes: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    checksum: Optional[str] = None
    compressed: bool = False
    storage_backend: str = "filesystem"
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    retention_policy: str = "default"


class ArtifactManager:
    """Enhanced artifact management with lifecycle, cleanup, and multiple backends"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.artifacts_dir = Path(config.get("directories", {}).get("artifacts", "./data/artifacts"))
        self.exports_dir = Path(config.get("directories", {}).get("exports", "./exports"))

        # Create directories
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

        # Artifact registry
        self._artifact_registry: Dict[str, ArtifactMetadata] = {}
        self._registry_file = self.artifacts_dir / "artifact_registry.json"

        # Load existing registry
        self._load_registry()

        # Start cleanup task
        self.cleanup_task = None
        self.cleanup_interval = config.get("artifacts", {}).get("cleanup_interval_seconds", 3600)  # 1 hour

        # Retention policies
        self.retention_policies = {
            "temporary": timedelta(hours=24),
            "short": timedelta(days=7),
            "default": timedelta(days=30),
            "long": timedelta(days=90),
            "permanent": None
        }

    async def start_cleanup_task(self):
        """Start the periodic cleanup task"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logger.info("Artifact cleanup task started")

    async def stop_cleanup_task(self):
        """Stop the periodic cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Artifact cleanup task stopped")

    async def store_artifact(self, job_id: str, filename: str, data: Any,
                           artifact_type: str, retention_policy: str = "default",
                           compress: bool = False, tags: List[str] = None) -> str:
        """Store an artifact with metadata tracking"""
        try:
            # Generate artifact ID
            artifact_id = f"{job_id}_{int(datetime.now().timestamp())}_{filename}"

            # Determine file path
            if artifact_type in ["repositories", "leads", "candidates", "personalization", "reports"]:
                base_dir = self.exports_dir
            else:
                base_dir = self.artifacts_dir

            filepath = base_dir / f"{artifact_id}"

            # Serialize data if needed
            if isinstance(data, (dict, list)):
                content = json.dumps(data, indent=2, default=str)
            else:
                content = str(data)

            # Compress if requested
            if compress:
                filepath = filepath.with_suffix('.json.gz')
                with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                    f.write(content)
            else:
                filepath = filepath.with_suffix('.json')
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)

            # Calculate file size
            file_size = filepath.stat().st_size

            # Create metadata
            metadata = ArtifactMetadata(
                artifact_id=artifact_id,
                job_id=job_id,
                filename=filename,
                path=str(filepath),
                artifact_type=artifact_type,
                size_bytes=file_size,
                created_at=datetime.now(),
                tags=tags or [],
                compressed=compress,
                retention_policy=retention_policy
            )

            # Set expiration based on retention policy
            if retention_policy in self.retention_policies:
                retention_period = self.retention_policies[retention_policy]
                if retention_period:
                    metadata.expires_at = datetime.now() + retention_period

            # Store in registry
            self._artifact_registry[artifact_id] = metadata
            await self._save_registry()

            logger.info(f"Stored artifact {artifact_id} ({file_size} bytes) for job {job_id}")
            return artifact_id

        except Exception as e:
            logger.error(f"Failed to store artifact for job {job_id}: {e}")
            raise

    async def get_artifact(self, artifact_id: str) -> Optional[bytes]:
        """Retrieve an artifact by ID"""
        try:
            metadata = self._artifact_registry.get(artifact_id)
            if not metadata:
                return None

            filepath = Path(metadata.path)
            if not filepath.exists():
                logger.warning(f"Artifact file not found: {filepath}")
                return None

            # Update access statistics
            metadata.access_count += 1
            metadata.last_accessed = datetime.now()
            await self._save_registry()

            # Read file
            if metadata.compressed:
                with gzip.open(filepath, 'rb') as f:
                    return f.read()
            else:
                with open(filepath, 'rb') as f:
                    return f.read()

        except Exception as e:
            logger.error(f"Failed to retrieve artifact {artifact_id}: {e}")
            return None

    async def get_artifact_metadata(self, artifact_id: str) -> Optional[ArtifactMetadata]:
        """Get artifact metadata"""
        return self._artifact_registry.get(artifact_id)

    async def list_job_artifacts(self, job_id: str) -> List[ArtifactMetadata]:
        """List all artifacts for a job"""
        return [meta for meta in self._artifact_registry.values() if meta.job_id == job_id]

    async def delete_artifact(self, artifact_id: str) -> bool:
        """Delete an artifact"""
        try:
            metadata = self._artifact_registry.get(artifact_id)
            if not metadata:
                return False

            # Delete file
            filepath = Path(metadata.path)
            if filepath.exists():
                filepath.unlink()

            # Remove from registry
            del self._artifact_registry[artifact_id]
            await self._save_registry()

            logger.info(f"Deleted artifact {artifact_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete artifact {artifact_id}: {e}")
            return False

    async def cleanup_expired_artifacts(self) -> int:
        """Clean up expired artifacts based on retention policies"""
        try:
            now = datetime.now()
            expired_artifacts = []

            for artifact_id, metadata in self._artifact_registry.items():
                if metadata.expires_at and metadata.expires_at < now:
                    expired_artifacts.append(artifact_id)

            # Delete expired artifacts
            deleted_count = 0
            for artifact_id in expired_artifacts:
                if await self.delete_artifact(artifact_id):
                    deleted_count += 1

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired artifacts")

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired artifacts: {e}")
            return 0

    async def optimize_storage(self) -> Dict[str, int]:
        """Optimize storage by compressing old artifacts and removing duplicates"""
        try:
            stats = {"compressed": 0, "duplicates_removed": 0, "space_saved": 0}

            # Compress old artifacts that aren't already compressed
            cutoff_date = datetime.now() - timedelta(days=7)  # Compress artifacts older than 7 days

            for metadata in self._artifact_registry.values():
                if (not metadata.compressed and
                    metadata.created_at < cutoff_date and
                    metadata.artifact_type in ["logs", "metrics", "debug"]):

                    try:
                        await self._compress_artifact(metadata)
                        stats["compressed"] += 1
                    except Exception as e:
                        logger.warning(f"Failed to compress artifact {metadata.artifact_id}: {e}")

            # Remove duplicate artifacts (same job, same type, keep newest)
            job_artifacts = {}
            for metadata in self._artifact_registry.values():
                key = f"{metadata.job_id}_{metadata.artifact_type}"
                if key not in job_artifacts:
                    job_artifacts[key] = []
                job_artifacts[key].append(metadata)

            for artifact_list in job_artifacts.values():
                if len(artifact_list) > 3:  # Keep max 3 artifacts per type per job
                    # Sort by creation time, keep newest
                    artifact_list.sort(key=lambda x: x.created_at, reverse=True)
                    to_remove = artifact_list[3:]

                    for metadata in to_remove:
                        if await self.delete_artifact(metadata.artifact_id):
                            stats["duplicates_removed"] += 1
                            stats["space_saved"] += metadata.size_bytes

            logger.info(f"Storage optimization completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to optimize storage: {e}")
            return {"compressed": 0, "duplicates_removed": 0, "space_saved": 0}

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            total_artifacts = len(self._artifact_registry)
            total_size = sum(meta.size_bytes for meta in self._artifact_registry.values())

            # Count by type
            type_counts = {}
            for meta in self._artifact_registry.values():
                type_counts[meta.artifact_type] = type_counts.get(meta.artifact_type, 0) + 1

            # Count by retention policy
            policy_counts = {}
            for meta in self._artifact_registry.values():
                policy_counts[meta.retention_policy] = policy_counts.get(meta.retention_policy, 0) + 1

            # Count expired artifacts
            now = datetime.now()
            expired_count = sum(1 for meta in self._artifact_registry.values()
                              if meta.expires_at and meta.expires_at < now)

            return {
                "total_artifacts": total_artifacts,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "artifacts_by_type": type_counts,
                "artifacts_by_policy": policy_counts,
                "expired_artifacts": expired_count,
                "compression_ratio": 0.0,  # TODO: Calculate actual compression ratio
            }

        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}

    async def _compress_artifact(self, metadata: ArtifactMetadata):
        """Compress an artifact"""
        try:
            filepath = Path(metadata.path)

            # Skip if already compressed
            if metadata.compressed:
                return

            # Read original content
            with open(filepath, 'rb') as f:
                content = f.read()

            # Create compressed version
            compressed_path = filepath.with_suffix('.json.gz')
            with gzip.open(compressed_path, 'wb') as f:
                f.write(content)

            # Replace original with compressed
            compressed_size = compressed_path.stat().st_size
            os.replace(compressed_path, filepath)

            # Update metadata
            metadata.compressed = True
            metadata.size_bytes = compressed_size
            await self._save_registry()

            logger.debug(f"Compressed artifact {metadata.artifact_id}: {len(content)} -> {compressed_size} bytes")

        except Exception as e:
            logger.error(f"Failed to compress artifact {metadata.artifact_id}: {e}")
            raise

    async def _periodic_cleanup(self):
        """Periodic cleanup task"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)

                # Cleanup expired artifacts
                expired_count = await self.cleanup_expired_artifacts()

                # Optimize storage
                if expired_count > 0:  # Only optimize if we cleaned up something
                    await self.optimize_storage()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")

    def _load_registry(self):
        """Load artifact registry from disk"""
        try:
            if self._registry_file.exists():
                with open(self._registry_file, 'r') as f:
                    data = json.load(f)

                # Reconstruct metadata objects
                for artifact_id, meta_dict in data.items():
                    meta_dict["created_at"] = datetime.fromisoformat(meta_dict["created_at"])
                    if meta_dict.get("expires_at"):
                        meta_dict["expires_at"] = datetime.fromisoformat(meta_dict["expires_at"])
                    if meta_dict.get("last_accessed"):
                        meta_dict["last_accessed"] = datetime.fromisoformat(meta_dict["last_accessed"])

                    self._artifact_registry[artifact_id] = ArtifactMetadata(**meta_dict)

                logger.info(f"Loaded {len(self._artifact_registry)} artifacts from registry")

        except Exception as e:
            logger.error(f"Failed to load artifact registry: {e}")
            self._artifact_registry = {}

    async def _save_registry(self):
        """Save artifact registry to disk"""
        try:
            # Convert metadata to dict
            registry_data = {}
            for artifact_id, metadata in self._artifact_registry.items():
                meta_dict = {
                    "artifact_id": metadata.artifact_id,
                    "job_id": metadata.job_id,
                    "filename": metadata.filename,
                    "path": metadata.path,
                    "artifact_type": metadata.artifact_type,
                    "size_bytes": metadata.size_bytes,
                    "created_at": metadata.created_at.isoformat(),
                    "tags": metadata.tags,
                    "checksum": metadata.checksum,
                    "compressed": metadata.compressed,
                    "storage_backend": metadata.storage_backend,
                    "access_count": metadata.access_count,
                    "retention_policy": metadata.retention_policy,
                }

                if metadata.expires_at:
                    meta_dict["expires_at"] = metadata.expires_at.isoformat()
                if metadata.last_accessed:
                    meta_dict["last_accessed"] = metadata.last_accessed.isoformat()

                registry_data[artifact_id] = meta_dict

            # Save to file
            with open(self._registry_file, 'w') as f:
                json.dump(registry_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save artifact registry: {e}")


# Global artifact manager instance
_artifact_manager = None

def get_artifact_manager(config: Dict[str, Any] = None) -> ArtifactManager:
    """Get the global artifact manager instance"""
    global _artifact_manager
    if _artifact_manager is None:
        from ..core.state import DEFAULT_CONFIG
        config = config or DEFAULT_CONFIG
        _artifact_manager = ArtifactManager(config)
    return _artifact_manager
