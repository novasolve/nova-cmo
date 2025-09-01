#!/usr/bin/env python3
"""
Timezone Utilities
Ensures all datetime operations use timezone-aware UTC to prevent Phase 2 crashes
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Union
import dateutil.parser


def utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)"""
    return datetime.now(timezone.utc)


def to_utc_iso8601(dt: Optional[Union[datetime, str]]) -> str:
    """Convert datetime to UTC ISO-8601 string format

    Args:
        dt: Datetime object or ISO string

    Returns:
        ISO-8601 formatted string with timezone info
    """
    if dt is None:
        return utc_now().isoformat()

    if isinstance(dt, str):
        # Parse string to datetime
        try:
            dt = dateutil.parser.isoparse(dt)
        except Exception:
            # Fallback to current time if parsing fails
            return utc_now().isoformat()

    # Ensure timezone awareness
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt.isoformat()


def parse_utc_datetime(dt_str: str) -> datetime:
    """Parse datetime string to timezone-aware UTC datetime"""
    if not dt_str:
        return utc_now()

    try:
        dt = dateutil.parser.isoparse(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return utc_now()


def days_ago(days: int) -> str:
    """Get ISO string for N days ago"""
    past_date = utc_now() - timedelta(days=days)
    return past_date.isoformat()


def is_recent(dt_str: str, days: int = 30) -> bool:
    """Check if datetime string is within last N days"""
    if not dt_str:
        return False

    try:
        dt = parse_utc_datetime(dt_str)
        cutoff = utc_now() - timedelta(days=days)
        return dt >= cutoff
    except Exception:
        return False


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string"""
    if seconds < 60:
        return ".1f"
    elif seconds < 3600:
        return ".1f"
    elif seconds < 86400:
        return ".1f"
    else:
        return ".1f"


def safe_datetime_compare(dt1_str: str, dt2_str: str) -> int:
    """Safely compare two datetime strings

    Returns:
        -1 if dt1 < dt2
         0 if dt1 == dt2
         1 if dt1 > dt2
    """
    try:
        dt1 = parse_utc_datetime(dt1_str)
        dt2 = parse_utc_datetime(dt2_str)
        return (dt1 > dt2) - (dt1 < dt2)
    except Exception:
        return 0  # Consider equal if parsing fails
