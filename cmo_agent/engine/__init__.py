"""
Minimal engine package to support unified_cli imports.
"""

from .types import JobSpec, RunSummary
from .events import CLIRenderer, SummaryCollector

# Lazily provide create_unified_engine so API mode can run without core.py
try:
    from .core import create_unified_engine  # type: ignore
except Exception:
    def create_unified_engine():  # type: ignore
        raise NotImplementedError(
            "create_unified_engine is not implemented yet. Use --mode api for now."
        )

__all__ = [
    "JobSpec",
    "RunSummary",
    "CLIRenderer",
    "SummaryCollector",
    "create_unified_engine",
]

# Unified execution engine module
