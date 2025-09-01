from __future__ import annotations

import json
from typing import Optional, Dict, Any

import yaml
from pydantic import ValidationError

from .schemas import JobConfig, Params, compute_pushed_since, normalize_stars_range

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
except Exception:  # Optional dependency not always available
    ChatPromptTemplate = None
    ChatOpenAI = None


YAMLIZER_PROMPT = None
if ChatPromptTemplate is not None:
    YAMLIZER_PROMPT = ChatPromptTemplate.from_messages([
        ("system", "You output ONLY JSON that matches the provided schema. No prose."),
        ("user", """Turn this request into a JobConfig JSON.\nRequest:\n{request}\nConstraints:\n- version=1\n- params.language ∈ {\"Python\",\"Go\",\"JavaScript\",\"TypeScript\",\"Rust\",\"Java\"}\n- stars_range = \"min..max\" (both ints)\n- activity_days ∈ [7, 365]\n- topics is optional list of short slugs (e.g., [\"ai\",\"ml\",\"pytest\"])\n- goal_template optional\nOutput: valid JSON only."""),
    ])


def make_yaml_config(user_request: str, user_overrides: Optional[Dict[str, Any]] = None) -> JobConfig:
    """Return a validated JobConfig built by LLM (if available) or defaults."""
    cfg: Optional[JobConfig] = None

    # Try LLM structured output if available
    if ChatOpenAI and YAMLIZER_PROMPT:
        try:
            model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            # Use model.with_structured_output to force schema
            chain = YAMLIZER_PROMPT | model.with_structured_output(JobConfig)
            cfg = chain.invoke({"request": user_request})
        except Exception:
            cfg = None

    # Fallback: minimal default config
    if cfg is None:
        cfg = JobConfig(params=Params())

    # Merge overrides (user wins)
    if user_overrides:
        merged = {**cfg.params.model_dump(), **user_overrides}
        cfg.params = Params(**merged)

    # Autofill pushed_since
    if not cfg.pushed_since:
        cfg.pushed_since = compute_pushed_since(cfg)

    # Normalize stars range
    cfg.params.stars_range = normalize_stars_range(cfg.params.stars_range)

    return cfg


def to_yaml(cfg: JobConfig) -> str:
    # Convert via JSON to keep ordering and types stable
    return yaml.safe_dump(json.loads(cfg.model_dump_json()), sort_keys=False)


