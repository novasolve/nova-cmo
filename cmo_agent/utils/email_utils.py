"""
Email utility functions for consistent filtering and validation.
"""

import re
from typing import List, Union


# Unified noreply patterns - comprehensive coverage
NOREPLY_PATTERNS = [
    # GitHub noreply addresses
    r'noreply@github\.com',
    r'users\.noreply\.github\.com',
    # Generic noreply patterns
    r'noreply',
    r'no-reply',
    # Common role-based emails that shouldn't be contacted
    r'admin@',
    r'info@',
    r'support@',
    r'hello@',
    r'contact@',
    r'team@',
    r'security@',
    r'legal@',
    r'compliance@',
    r'marketing@',
    r'sales@',
    # Corporate team emails (like torax-team@google.com)
    r'-team@',
    r'\.team@',
    # Bot/automation emails
    r'bot@',
    r'automation@',
    r'ci@',
    r'build@',
    # Generic corporate domains that are typically not personal
    r'@google\.com$',
    r'@microsoft\.com$',
    r'@amazon\.com$',
    r'@meta\.com$',
    r'@facebook\.com$',
    r'@apple\.com$',
]

NOREPLY_REGEX = re.compile('|'.join(NOREPLY_PATTERNS), re.IGNORECASE)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_noreply_email(email: str) -> bool:
    """
    Check if an email address is a noreply or role-based address that shouldn't be contacted.

    Args:
        email: Email address to check

    Returns:
        True if email should be filtered out, False otherwise
    """
    if not email or not isinstance(email, str):
        return True

    email_lower = email.lower().strip()

    # Must contain @ to be a valid email
    if '@' not in email_lower:
        return True

    # Check against all noreply patterns
    return bool(NOREPLY_REGEX.search(email_lower))


def filter_contactable_emails(emails: Union[List[str], str]) -> List[str]:
    """
    Filter a list of emails to return only contactable addresses.

    Args:
        emails: Single email string or list of email strings

    Returns:
        List of contactable email addresses
    """
    if isinstance(emails, str):
        emails = [emails]

    contactable = []
    for email in emails:
        if email and isinstance(email, str) and not is_noreply_email(email):
            contactable.append(normalize_email(email))

    return list(set(contactable))  # Remove duplicates


# Centralized dedup + contactable extractor for consistency across exporter/summary

def dedup_contactable(emails: Union[List[str], str]) -> List[str]:
    if isinstance(emails, str):
        emails = [emails]
    seen: set[str] = set()
    out: List[str] = []
    for e in emails:
        ne = normalize_email(e)
        if ne and ("@" in ne) and (not is_noreply_email(ne)) and ne not in seen:
            seen.add(ne)
            out.append(ne)
    return out


def keep_email(email: str) -> bool:
    """
    Minimal hygiene check for whether an email should be kept for outreach.

    Returns True for valid, contactable emails; False for noreply/role or invalid.
    """
    if not email or not isinstance(email, str):
        return False
    email_lower = email.strip().lower()
    if "@" not in email_lower:
        return False
    return not is_noreply_email(email_lower)

def count_noreply_emails(emails: Union[List[str], str]) -> int:
    """
    Count how many emails in a list are noreply addresses.

    Args:
        emails: Single email string or list of email strings

    Returns:
        Number of noreply emails found
    """
    if isinstance(emails, str):
        emails = [emails]

    return sum(1 for email in emails if is_noreply_email(email))
