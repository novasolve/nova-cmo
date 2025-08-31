"""
Export and finalization tools
"""
import csv
import json
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, List

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

    async def execute(self, rows: List[Dict[str, Any]], path: str, **kwargs) -> ToolResult:
        """Export data to CSV"""
        try:
            if not rows:
                return ToolResult(success=False, error="No data to export")

            # Ensure export directory exists
            full_path = Path(path)
            if not full_path.is_absolute():
                full_path = self.export_dir / full_path

            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Get all unique keys for CSV headers
            headers = set()
            for row in rows:
                headers.update(row.keys())
            headers = sorted(list(headers))

            # Write CSV file
            with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)

            # Get file stats
            file_stats = full_path.stat()

            result_data = {
                "path": str(full_path),
                "count": len(rows),
                "headers": headers,
                "file_size_bytes": file_stats.st_size,
                "file_size_mb": round(file_stats.st_size / (1024 * 1024), 2),
            }

            return ToolResult(success=True, data=result_data)

        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return ToolResult(success=False, error=str(e))


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
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
