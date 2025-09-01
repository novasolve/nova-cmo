from __future__ import annotations

from typing import Dict, Any, List, Tuple

from .schemas import JobConfig


def build_plan(cfg: JobConfig) -> List[Tuple[str, Dict[str, Any]]]:
    steps: List[Tuple[str, Dict[str, Any]]] = []
    topics = cfg.params.topics
    query: Dict[str, Any] = {
        "language": cfg.params.language,
        "stars_range": cfg.params.stars_range,
        "pushed_since": cfg.pushed_since,
        "topics": topics,
        "per_page": 100,
    }
    steps.append(("search_github_repos", query))
    return steps


def heal_and_retry(query: Dict[str, Any], attempt: int) -> Dict[str, Any]:
    # attempt = 1..N
    q = dict(query)
    if attempt == 1:
        q["topics"] = None
    elif attempt == 2:
        q["stars_range"] = "100..2000"
    elif attempt == 3:
        # Older window (double activity days)
        q["pushed_since"] = None  # let server compute broader
    return q


