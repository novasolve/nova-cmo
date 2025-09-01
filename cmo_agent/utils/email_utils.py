"""
Email utility functions for consistent filtering and validation.
"""

import re
from typing import List, Union


# Unified noreply patterns - comprehensive coverage
NOREPLY_PATTERNS = [
    # GitHub noreply addresses
    r'@users\.noreply\.github\.com$',
    r'@noreply\.github\.com$',
    # Generic noreply patterns
    r'@.*noreply.*\.',
    r'@.*no-reply.*\.',
    # Common role-based emails that shouldn't be contacted
    r'@.*admin@.*\.',
    r'@.*info@.*\.',
    r'@.*support@.*\.',
    r'@.*hello@.*\.',
    r'@.*contact@.*\.',
]

NOREPLY_REGEX = re.compile('|'.join(NOREPLY_PATTERNS), re.IGNORECASE)


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
            contactable.append(email.strip())

    return list(set(contactable))  # Remove duplicates


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
