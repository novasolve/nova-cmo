from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Params(BaseModel):
    language: str = Field("Python", description="Primary programming language")
    stars_range: str = Field("300..2000", description="GitHub star range 'min..max'")
    activity_days: int = Field(90, ge=7, le=365, description="Lookback window in days")
    target_leads: int = Field(20, ge=1, description="Desired number of leads")
    budget_per_day: int = Field(10, ge=0, description="Budget per day in USD")
    topics: Optional[List[str]] = Field(default=None, description="Optional topic slugs")


class JobConfig(BaseModel):
    version: int = 1
    params: Params
    pushed_since: Optional[str] = Field(default=None, description="YYYY-MM-DD cutoff")
    goal_template: Optional[str] = None
    can_relax_topics: bool = True

    @field_validator("pushed_since", mode="before")
    @classmethod
    def _coerce_date(cls, v):
        return v or None


def compute_pushed_since(cfg: JobConfig) -> str:
    days = max(7, min(365, int(cfg.params.activity_days or 90)))
    return (date.today() - timedelta(days=days)).isoformat()


def normalize_stars_range(value: str) -> str:
    try:
        parts = str(value).split("..")
        if len(parts) != 2:
            return "100..2000"
        low, high = int(parts[0]), int(parts[1])
        if low < 0 or high <= 0 or low >= high:
            return "100..2000"
        return f"{low}..{high}"
    except Exception:
        return "100..2000"


