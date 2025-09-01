"""
Export and finalization tools
"""
import csv
import json
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Iterable, Sequence, Optional
import asyncio
from tempfile import NamedTemporaryFile

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from .base import BaseTool, ToolResult
except ImportError:
    try:
        from base import BaseTool, ToolResult
    except ImportError:
        # Create minimal fallback classes
        class ToolResult:
            def __init__(self, success: bool, data: Any = None, error: str = None, metadata: Dict = None):
                self.success = success
                self.data = data or {}
                self.error = error
                self.metadata = metadata or {}

            def to_dict(self) -> Dict[str, Any]:
                return {
                    "success": self.success,
                    "data": self.data,
                    "error": self.error,
                    "metadata": self.metadata,
                }

        class BaseTool:
            def __init__(self, name: str, description: str, rate_limit: float = 1000):
                self.name = name
                self.description = description
                self.rate_limit = rate_limit

logger = logging.getLogger(__name__)


class ExportCSV(BaseTool):
    """CSV export tool"""

    def __init__(self, export_dir: str = "./exports"):
        super().__init__(
            name="export_csv",
            description="Export data to CSV format with proper formatting",
            rate_limit=100  # File I/O bound
        )
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(exist_ok=True)

    async def execute(
        self,
        rows: List[Dict[str, Any]],
        path: str,
        **kwargs,
    ) -> ToolResult:
        """Export data to CSV with safe paths and atomic write.

        kwargs supports optional keys:
        - field_order: Sequence[str]
        - include_bom: bool
        - allow_overwrite: bool
        - newline: str
        - quoting: int
        - dialect: Optional[str]
        - extrasaction: str
        """
        try:
            dry_run: bool = bool(kwargs.get("dry_run", False))
            if not rows:
                return ToolResult(success=False, error="No data to export")

            # Resolve destination within export root and guard traversal
            dest = Path(path)
            if not dest.is_absolute():
                dest = self.export_dir / dest
            base = dest.parent.expanduser().resolve()
            base.mkdir(parents=True, exist_ok=True)
            dest = (base / dest.name).resolve()
            try:
                dest.relative_to(base)
            except ValueError:
                return ToolResult(success=False, error=f"Illegal export path outside base dir: {dest}")

            # Compute headers deterministically, honoring optional field_order
            headers = self._compute_headers(rows, kwargs.get("field_order"))

            if dry_run:
                # Simulate export in dry-run
                result_data = {
                    "path": str(dest),
                    "count": len(rows),
                    "headers": headers,
                    "file_size_bytes": 0,
                    "file_size_mb": 0.0,
                    "status": "dry_run",
                }
                return ToolResult(success=True, data=result_data)
            else:
                # Atomic write via temp file then replace
                include_bom = bool(kwargs.get("include_bom", False))
                encoding = "utf-8-sig" if include_bom else "utf-8"
                newline = kwargs.get("newline", "")
                quoting = int(kwargs.get("quoting", csv.QUOTE_MINIMAL))
                dialect = kwargs.get("dialect")
                extrasaction = kwargs.get("extrasaction", "ignore")
                allow_overwrite = bool(kwargs.get("allow_overwrite", True))

                if dest.exists() and not allow_overwrite:
                    return ToolResult(success=False, error=f"File already exists: {dest}")

                async def _write_file():
                    from contextlib import suppress
                    mode_kwargs = dict(newline=newline, encoding=encoding)
                    with NamedTemporaryFile("w", delete=False, dir=base, suffix=".tmp") as tf:
                        tmp_path = Path(tf.name)
                    try:
                        with tmp_path.open("w", **mode_kwargs) as f:
                            if dialect:
                                writer = csv.DictWriter(f, fieldnames=headers, dialect=dialect, extrasaction=extrasaction)
                            else:
                                writer = csv.DictWriter(f, fieldnames=headers, quoting=quoting, extrasaction=extrasaction)
                            writer.writeheader()
                            for r in rows:
                                writer.writerow(self._coerce_row(r, headers))
                        os.replace(tmp_path, dest)
                    except Exception:
                        with suppress(FileNotFoundError):
                            try:
                                tmp_path.unlink(missing_ok=True)
                            except TypeError:
                                # py<3.8 compatibility
                                if tmp_path.exists():
                                    tmp_path.unlink()
                        raise

                await asyncio.to_thread(lambda: asyncio.run(_write_file()))

            # Get file stats
            file_stats = dest.stat()

            result_data = {
                "path": str(dest),
                "count": len(rows),
                "headers": headers,
                "file_size_bytes": file_stats.st_size,
                "file_size_mb": round(file_stats.st_size / (1024 * 1024), 2),
            }

            return ToolResult(success=True, data=result_data)

        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return ToolResult(success=False, error=str(e))

    @staticmethod
    def _compute_headers(rows: Iterable[Dict[str, Any]], field_order: Optional[Sequence[str]]) -> List[str]:
        if not rows:
            return []
        all_keys = set()
        for r in rows:
            if isinstance(r, dict):
                all_keys.update(r.keys())
        if field_order:
            ordered = [k for k in field_order if k in all_keys]
            tail = sorted(all_keys - set(ordered))
            return ordered + tail
        return sorted(all_keys)

    @staticmethod
    def _coerce_row(r: Dict[str, Any], headers: Sequence[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for h in headers:
            v = r.get(h)
            if v is None:
                out[h] = ""
            elif isinstance(v, (str, int, float, bool)):
                out[h] = v
            else:
                out[h] = str(v)
        return out


class Done(BaseTool):
    """Finalization tool - signals completion of the job"""

    def __init__(self):
        super().__init__(
            name="done",
            description="Signal job completion with summary",
            rate_limit=1000  # Pure operation
        )

    async def execute(self, summary: str, **kwargs) -> ToolResult:
        """Mark job as complete"""
        try:
            result_data = {
                "summary": summary,
                "completed_at": self._get_timestamp(),
                "status": "completed",
            }

            logger.info(f"Job completed: {summary}")
            return ToolResult(success=True, data=result_data)

        except Exception as e:
            logger.error(f"Done signal failed: {e}")
            return ToolResult(success=False, error=str(e))

    def _get_timestamp(self) -> str:
        """UTC ISO-8601 with trailing 'Z'"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
