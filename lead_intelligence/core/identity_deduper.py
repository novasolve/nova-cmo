#!/usr/bin/env python3
"""
Identity Deduplication
Merges duplicate prospects across repositories and keeps best contact information
"""

import hashlib
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from .timezone_utils import parse_utc_datetime


@dataclass
class MergedProspect:
    """Represents a merged prospect with best contact information"""
    canonical_login: str
    all_logins: Set[str]
    best_prospect: Dict[str, Any]
    all_repos: Set[str]
    contact_methods: Dict[str, Any] = field(default_factory=dict)
    merged_fields: Dict[str, Any] = field(default_factory=dict)
    merge_count: int = 1
    last_updated: str = ""

    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()


class IdentityDeduper:
    """Deduplicates prospects based on identity keys"""

    def __init__(self):
        self.merged_prospects: Dict[str, MergedProspect] = {}
        self.identity_map: Dict[str, str] = {}  # identity_key -> canonical_login

    def deduplicate_prospects(self, prospects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate a list of prospects and return merged versions"""

        # Group prospects by identity keys
        identity_groups = self._group_by_identity(prospects)

        # Merge each group
        merged_list = []
        for canonical_key, group_prospects in identity_groups.items():
            merged_prospect = self._merge_prospect_group(group_prospects)
            merged_list.append(merged_prospect.best_prospect)

            # Store in merged prospects for future reference
            self.merged_prospects[canonical_key] = merged_prospect

        return merged_list

    def _group_by_identity(self, prospects: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group prospects by identity keys"""
        groups = defaultdict(list)

        for prospect in prospects:
            # Primary identity key: GitHub login
            login = prospect.get('login', '')
            if login:
                canonical_key = f"github:{login.lower()}"
                groups[canonical_key].append(prospect)
                continue

            # Fallback: email-based grouping
            email = prospect.get('email_profile') or prospect.get('email_public_commit')
            if email and '@' in email:
                domain = email.split('@')[1].lower()
                # Only group by email if it's a corporate domain
                if not self._is_public_email_domain(domain):
                    email_key = f"email:{email.lower()}"
                    groups[email_key].append(prospect)
                    continue

            # Last resort: name + company
            name = prospect.get('name', '').strip().lower()
            company = prospect.get('company', '').strip().lower()
            if name and company:
                name_key = f"name:{name}_{company}"
                groups[name_key].append(prospect)
            elif name:
                name_key = f"name:{name}"
                groups[name_key].append(prospect)
            else:
                # No identity key found, keep as separate
                import uuid
                unique_key = f"unknown:{str(uuid.uuid4())[:8]}"
                groups[unique_key].append(prospect)

        return groups

    def _merge_prospect_group(self, prospects: List[Dict[str, Any]]) -> MergedProspect:
        """Merge a group of prospects into one with best information"""

        if not prospects:
            raise ValueError("Cannot merge empty prospect group")

        if len(prospects) == 1:
            prospect = prospects[0]
            login = prospect.get('login', 'unknown')
            return MergedProspect(
                canonical_login=login,
                all_logins={login},
                best_prospect=prospect,
                all_repos={prospect.get('repo_full_name', '')},
                merge_count=1
            )

        # Find the "best" prospect as the base
        best_prospect = self._select_best_prospect(prospects)

        # Merge information from all prospects
        merged_data = self._merge_prospect_data(prospects, best_prospect)

        # Collect all logins and repos
        all_logins = set()
        all_repos = set()

        for prospect in prospects:
            login = prospect.get('login', '')
            if login:
                all_logins.add(login)

            repo = prospect.get('repo_full_name', '')
            if repo:
                all_repos.add(repo)

        canonical_login = best_prospect.get('login', 'unknown')

        return MergedProspect(
            canonical_login=canonical_login,
            all_logins=all_logins,
            best_prospect=merged_data,
            all_repos=all_repos,
            merge_count=len(prospects)
        )

    def _select_best_prospect(self, prospects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the best prospect from a group to use as the base"""

        if len(prospects) == 1:
            return prospects[0]

        # Scoring criteria for selecting best prospect
        scored_prospects = []

        for prospect in prospects:
            score = 0

            # Prefer prospects with maintainer status
            if prospect.get('is_maintainer'):
                score += 50
            if prospect.get('is_codeowner'):
                score += 30
            if prospect.get('is_org_member'):
                score += 20

            # Prefer prospects with better contactability
            contact_score = prospect.get('contactability_score', 0)
            score += contact_score

            # Prefer prospects with higher tier
            tier = prospect.get('prospect_tier', 'C')
            tier_scores = {'A': 20, 'B': 10, 'C': 5, 'REJECT': 0}
            score += tier_scores.get(tier, 0)

            # Prefer prospects with more recent activity
            if prospect.get('signal_at'):
                try:
                    signal_date = parse_utc_datetime(prospect['signal_at'])
                    days_since = (datetime.now() - signal_date).days
                    recency_score = max(0, 30 - days_since)  # Max 30 points for very recent
                    score += recency_score
                except:
                    pass

            scored_prospects.append((score, prospect))

        # Return the highest scoring prospect
        scored_prospects.sort(key=lambda x: x[0], reverse=True)
        return scored_prospects[0][1]

    def _merge_prospect_data(self, prospects: List[Dict[str, Any]], base_prospect: Dict[str, Any]]) -> Dict[str, Any]:
        """Merge data from multiple prospects, keeping the best information"""

        merged = base_prospect.copy()
        merged_fields = {}

        # Collect all unique repositories
        all_repos = set()
        for prospect in prospects:
            repo = prospect.get('repo_full_name', '')
            if repo:
                all_repos.add(repo)

        if len(all_repos) > 1:
            merged['all_repo_full_names'] = list(all_repos)
            merged_fields['repositories'] = f"Merged from {len(all_repos)} repos: {', '.join(sorted(all_repos))}"

        # Merge contact information - keep the best available
        best_email_profile = self._select_best_email([p.get('email_profile') for p in prospects if p.get('email_profile')])
        best_email_commit = self._select_best_email([p.get('email_public_commit') for p in prospects if p.get('email_public_commit')])

        if best_email_profile and best_email_profile != merged.get('email_profile'):
            merged['email_profile'] = best_email_profile
            merged_fields['email_profile'] = "Merged from multiple sources"

        if best_email_commit and best_email_commit != merged.get('email_public_commit'):
            merged['email_public_commit'] = best_email_commit
            merged_fields['email_public_commit'] = "Merged from multiple sources"

        # Merge LinkedIn information
        linkedin_urls = [p.get('linkedin_username') for p in prospects if p.get('linkedin_username')]
        if linkedin_urls:
            # Take the first non-empty LinkedIn URL
            for url in linkedin_urls:
                if url and url.strip():
                    if url != merged.get('linkedin_username'):
                        merged['linkedin_username'] = url
                        merged_fields['linkedin_username'] = "Merged from multiple sources"
                    break

        # Merge bio information - keep the longest/most complete
        bios = [p.get('bio', '') for p in prospects if p.get('bio')]
        if bios:
            best_bio = max(bios, key=len)
            if best_bio != merged.get('bio'):
                merged['bio'] = best_bio
                merged_fields['bio'] = "Selected longest bio"

        # Update contactability score based on merged data
        if merged_fields:
            # Recalculate contactability if we merged contact info
            merged['contactability_score'] = self._recalculate_contactability(merged)

        # Add merge metadata
        merged['merge_metadata'] = {
            'merged_from_count': len(prospects),
            'merged_fields': merged_fields,
            'merge_timestamp': datetime.now().isoformat()
        }

        return merged

    def _select_best_email(self, emails: List[str]) -> Optional[str]:
        """Select the best email from a list"""
        if not emails:
            return None

        # Remove duplicates and empty strings
        unique_emails = list(set(email.strip() for email in emails if email and email.strip()))

        if not unique_emails:
            return None

        if len(unique_emails) == 1:
            return unique_emails[0]

        # Prefer corporate emails over personal
        corporate_emails = []
        personal_emails = []

        for email in unique_emails:
            if '@' in email:
                domain = email.split('@')[1].lower()
                if self._is_public_email_domain(domain):
                    personal_emails.append(email)
                else:
                    corporate_emails.append(email)

        # Return corporate email if available, otherwise personal
        if corporate_emails:
            return corporate_emails[0]  # Could implement more sophisticated selection
        elif personal_emails:
            return personal_emails[0]

        return unique_emails[0]

    def _recalculate_contactability(self, prospect: Dict[str, Any]) -> int:
        """Recalculate contactability score after merging"""
        score = 0

        # Email availability
        if prospect.get('email_profile') or prospect.get('email_public_commit'):
            score += 30
            if prospect.get('email_profile'):  # Profile email preferred
                score += 10

        # LinkedIn availability
        if prospect.get('linkedin_username'):
            score += 30

        # Corporate domain detection
        email = prospect.get('email_profile') or prospect.get('email_public_commit')
        if email and '@' in email:
            domain = email.split('@')[1].lower()
            if not self._is_public_email_domain(domain):
                score += 20

        # Professional indicators
        if prospect.get('company'):
            score += 5
        if prospect.get('blog'):
            score += 5

        return min(100, score)

    def _is_public_email_domain(self, domain: str) -> bool:
        """Check if domain is a public email provider"""
        public_domains = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
            'proton.me', 'protonmail.com', 'icloud.com', 'me.com', 'mac.com'
        }
        return domain.lower() in public_domains

    def get_merge_stats(self) -> Dict[str, Any]:
        """Get statistics about merged prospects"""
        total_merged = len(self.merged_prospects)
        total_duplicates = sum(mp.merge_count for mp in self.merged_prospects.values())
        total_unique = sum(1 for mp in self.merged_prospects.values() if mp.merge_count == 1)

        merge_counts = defaultdict(int)
        for mp in self.merged_prospects.values():
            merge_counts[mp.merge_count] += 1

        return {
            'total_prospects_processed': total_duplicates,
            'unique_prospects_after_merge': len(self.merged_prospects),
            'total_merged_groups': total_merged - total_unique,
            'merge_distribution': dict(merge_counts),
            'deduplication_ratio': total_duplicates / len(self.merged_prospects) if self.merged_prospects else 1.0
        }
