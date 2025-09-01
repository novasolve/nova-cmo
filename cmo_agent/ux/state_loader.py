"""
State loader utilities for reading CMO Agent RunState checkpoints.

This module provides helpers to locate and parse the latest checkpoint
JSON file from one or more directories. It is intentionally light-weight
and has no runtime dependencies outside the standard library.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_CHECKPOINT_DIRS: Tuple[Path, ...] = (
    Path("./checkpoints"),
    Path("./cmo_agent/checkpoints"),
)


@dataclass
class LoadedState:
    path: Path
    state: Dict[str, Any]


def _iter_checkpoint_files(dirs: Iterable[Path]) -> List[Path]:
    files: List[Path] = []
    for d in dirs:
        try:
            if d.exists() and d.is_dir():
                for p in d.glob("*.json"):
                    # Only include files that look like our periodic/state dumps
                    files.append(p)
        except Exception:
            # Skip unreadable directories
            continue
    return files


def find_latest_checkpoint(
    search_dirs: Optional[Iterable[str | os.PathLike]] = None,
) -> Optional[Path]:
    dirs: Tuple[Path, ...]
    if search_dirs is None:
        dirs = DEFAULT_CHECKPOINT_DIRS
    else:
        dirs = tuple(Path(p) for p in search_dirs)

    files = _iter_checkpoint_files(dirs)
    if not files:
        return None

    # Newest by modified time
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def load_state_from_file(path: str | os.PathLike) -> LoadedState:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return LoadedState(path=p, state=data)


def load_latest_state(
    search_dirs: Optional[Iterable[str | os.PathLike]] = None,
) -> Optional[LoadedState]:
    latest = find_latest_checkpoint(search_dirs)
    if latest is None:
        return None
    return load_state_from_file(latest)
