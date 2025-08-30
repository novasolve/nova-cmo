#!/usr/bin/env python3
"""
Data Normalizer
Standardizes all prospect fields to consistent formats and values
"""

import re
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from dataclasses import dataclass
from urllib.parse import urlparse, urljoin
import logging

logger = logging.getLogger(__name__)


@dataclass
class NormalizationResult:
    """Result of data normalization"""
    normalized_prospect: Dict[str, Any]
    changes_made: Dict[str, Any]
    normalization_warnings: List[str]


class DataNormalizer:
    """Normalizes prospect data to consistent formats and standards"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.version = "1.0.0"

        # Common name prefixes/titles to remove
        self.name_prefixes = {
            'mr.', 'mrs.', 'ms.', 'miss', 'dr.', 'prof.', 'professor',
            'sir', 'madam', 'mx.', 'rev.', 'fr.', 'sr.', 'jr.', 'sr',
            'ii', 'iii', 'iv', 'v', 'phd', 'ph.d.'
        }

        # Common company suffixes to standardize
        self.company_suffixes = {
            'inc': 'Inc',
            'ltd': 'Ltd',
            'llc': 'LLC',
            'corp': 'Corp',
            'corporation': 'Corporation',
            'co': 'Co',
            'company': 'Company',
            'gmbh': 'GmbH',
            'ag': 'AG',
            'ltd.': 'Ltd',
            'inc.': 'Inc',
            'llc.': 'LLC',
            'corp.': 'Corp',
            'co.': 'Co'
        }

        # Country name mappings for consistency
        self.country_mappings = {
            'usa': 'United States',
            'us': 'United States',
            'uk': 'United Kingdom',
            'united kingdom of great britain and northern ireland': 'United Kingdom',
            'deutschland': 'Germany',
            'de': 'Germany',
            'france': 'France',
            'fr': 'France',
            'italia': 'Italy',
            'it': 'Italy',
            'españa': 'Spain',
            'es': 'Spain',
            'canada': 'Canada',
            'ca': 'Canada',
            'australia': 'Australia',
            'au': 'Australia',
            'nederland': 'Netherlands',
            'nl': 'Netherlands'
        }

    def _default_config(self) -> Dict[str, Any]:
        """Default normalization configuration"""
        return {
            'normalize_names': True,
            'normalize_companies': True,
            'normalize_locations': True,
            'normalize_emails': True,
            'normalize_urls': True,
            'normalize_bio': True,
            'standardize_languages': True,
            'max_bio_length': 500,
            'max_name_length': 100,
            'max_company_length': 100,
            'lowercase_emails': True,
            'standardize_protocols': True
        }

    def normalize_prospect(self, prospect: Dict[str, Any]) -> NormalizationResult:
        """
        Normalize all fields in a prospect record
        Returns NormalizationResult with changes tracking
        """
        normalized = prospect.copy()
        changes_made = {}
        warnings = []

        # Normalize core fields
        if self.config.get('normalize_names', True):
            original_name = prospect.get('name')
            normalized_name = self._normalize_name(original_name)
            if normalized_name != original_name:
                normalized['name'] = normalized_name
                changes_made['name'] = {'from': original_name, 'to': normalized_name}

        if self.config.get('normalize_companies', True):
            original_company = prospect.get('company')
            normalized_company = self._normalize_company(original_company)
            if normalized_company != original_company:
                normalized['company'] = normalized_company
                changes_made['company'] = {'from': original_company, 'to': normalized_company}

        if self.config.get('normalize_locations', True):
            original_location = prospect.get('location')
            normalized_location = self._normalize_location(original_location)
            if normalized_location != original_location:
                normalized['location'] = normalized_location
                changes_made['location'] = {'from': original_location, 'to': normalized_location}

        # Normalize contact fields
        if self.config.get('normalize_emails', True):
            for email_field in ['email_profile', 'email_public_commit']:
                original_email = prospect.get(email_field)
                if original_email:
                    normalized_email = self._normalize_email(original_email)
                    if normalized_email != original_email:
                        normalized[email_field] = normalized_email
                        changes_made[email_field] = {'from': original_email, 'to': normalized_email}

        if self.config.get('normalize_urls', True):
            for url_field in ['github_user_url', 'github_repo_url', 'html_url', 'api_url', 'avatar_url']:
                original_url = prospect.get(url_field)
                if original_url:
                    normalized_url = self._normalize_url(original_url)
                    if normalized_url != original_url:
                        normalized[url_field] = normalized_url
                        changes_made[url_field] = {'from': original_url, 'to': normalized_url}

        # Normalize LinkedIn URL
        original_linkedin = prospect.get('linkedin_username')
        if original_linkedin:
            normalized_linkedin = self._normalize_linkedin_url(original_linkedin)
            if normalized_linkedin != original_linkedin:
                normalized['linkedin_username'] = normalized_linkedin
                changes_made['linkedin_username'] = {'from': original_linkedin, 'to': normalized_linkedin}

        # Normalize bio
        if self.config.get('normalize_bio', True):
            original_bio = prospect.get('bio')
            normalized_bio = self._normalize_bio(original_bio)
            if normalized_bio != original_bio:
                normalized['bio'] = normalized_bio
                changes_made['bio'] = {'from': original_bio, 'to': normalized_bio}

        # Normalize programming languages
        if self.config.get('standardize_languages', True):
            original_language = prospect.get('language')
            normalized_language = self._normalize_language(original_language)
            if normalized_language != original_language:
                normalized['language'] = normalized_language
                changes_made['language'] = {'from': original_language, 'to': normalized_language}

        # Normalize topics
        original_topics = prospect.get('topics', [])
        normalized_topics = self._normalize_topics(original_topics)
        if normalized_topics != original_topics:
            normalized['topics'] = normalized_topics
            changes_made['topics'] = {'from': original_topics, 'to': normalized_topics}

        # Add normalization metadata
        normalized['normalized_at'] = datetime.now().isoformat()
        normalized['normalization_version'] = self.version
        normalized['normalization_warnings'] = warnings

        return NormalizationResult(
            normalized_prospect=normalized,
            changes_made=changes_made,
            normalization_warnings=warnings
        )

    def _normalize_name(self, name: str) -> str:
        """Normalize person names to Title Case format"""
        if not name or not isinstance(name, str):
            return name or ""

        # Limit length
        if len(name) > self.config.get('max_name_length', 100):
            name = name[:self.config.get('max_name_length', 100)].strip()

        # Clean up the name
        name = name.strip()

        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name)

        # Handle names with parentheses, quotes, etc.
        name = re.sub(r'[()\[\]{}"\'*]', '', name)

        # Convert to title case but handle special cases
        words = name.split()
        normalized_words = []

        for i, word in enumerate(words):
            word_lower = word.lower()

            # Skip name prefixes/titles unless they're the first word
            if i > 0 and word_lower in self.name_prefixes:
                continue

            # Handle hyphenated names
            if '-' in word:
                parts = word.split('-')
                normalized_parts = []
                for part in parts:
                    # Don't capitalize very short parts (like "de", "van", "von")
                    if len(part) <= 2:
                        normalized_parts.append(part.lower())
                    else:
                        normalized_parts.append(part.capitalize())
                normalized_words.append('-'.join(normalized_parts))
            else:
                # Don't capitalize very short words (like "de", "van", "von")
                if len(word) <= 2 and i > 0:
                    normalized_words.append(word.lower())
                else:
                    normalized_words.append(word.capitalize())

        return ' '.join(normalized_words)

    def _normalize_company(self, company: str) -> str:
        """Normalize company names"""
        if not company or not isinstance(company, str):
            return company or ""

        # Limit length
        if len(company) > self.config.get('max_company_length', 100):
            company = company[:self.config.get('max_company_length', 100)].strip()

        # Clean up the company name
        company = company.strip()

        # Remove extra whitespace
        company = re.sub(r'\s+', ' ', company)

        # Handle common abbreviations and suffixes
        words = company.split()
        normalized_words = []

        for word in words:
            word_lower = word.lower().rstrip('.,')

            # Standardize company suffixes
            if word_lower in self.company_suffixes:
                normalized_words.append(self.company_suffixes[word_lower])
            else:
                # Title case for other words
                normalized_words.append(word.capitalize())

        result = ' '.join(normalized_words)

        # Handle special cases
        result = re.sub(r'\bAnd\b', 'and', result)  # "and" should be lowercase
        result = re.sub(r'\bOf\b', 'of', result)    # "of" should be lowercase
        result = re.sub(r'\bThe\b', 'the', result)  # "the" should be lowercase

        return result

    def _normalize_location(self, location: str) -> str:
        """Normalize location information"""
        if not location or not isinstance(location, str):
            return location or ""

        location = location.strip()

        # Remove extra whitespace
        location = re.sub(r'\s+', ' ', location)

        # Handle country names
        location_lower = location.lower()

        # Check for country mappings
        for short, full in self.country_mappings.items():
            if location_lower == short or location_lower == full.lower():
                return full

        # Title case for location names
        words = location.split()
        normalized_words = []

        for word in words:
            # Don't capitalize small words like "de", "du", etc.
            if len(word) <= 3 and word.lower() in ['de', 'du', 'la', 'le', 'von', 'van', 'der', 'den']:
                normalized_words.append(word.lower())
            else:
                normalized_words.append(word.capitalize())

        return ', '.join(normalized_words)

    def _normalize_email(self, email: str) -> str:
        """Normalize email addresses"""
        if not email or not isinstance(email, str):
            return email or ""

        email = email.strip()

        # Convert to lowercase if configured
        if self.config.get('lowercase_emails', True):
            email = email.lower()

        # Basic email validation (don't change invalid emails)
        if '@' not in email:
            return email

        local, domain = email.split('@', 1)

        # Remove common email prefixes/suffixes that cause bounces
        local = re.sub(r'^[^a-zA-Z0-9]+', '', local)  # Remove leading non-alphanumeric
        local = re.sub(r'[^a-zA-Z0-9._-]*$', '', local)  # Remove trailing non-alphanumeric

        # Reconstruct email
        normalized = f"{local}@{domain}"

        return normalized

    def _normalize_url(self, url: str) -> str:
        """Normalize URLs to consistent format"""
        if not url or not isinstance(url, str):
            return url or ""

        url = url.strip()

        # Ensure protocol
        if self.config.get('standardize_protocols', True):
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

        # Remove trailing slashes except for root
        if url.endswith('/') and url.count('/') > 2:
            url = url.rstrip('/')

        # Basic URL validation
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return url  # Return as-is if parsing fails
        except:
            return url  # Return as-is if parsing fails

        return url

    def _normalize_linkedin_url(self, linkedin: str) -> str:
        """Normalize LinkedIn URLs to consistent format"""
        if not linkedin or not isinstance(linkedin, str):
            return linkedin or ""

        linkedin = linkedin.strip()

        # Handle different LinkedIn URL formats
        linkedin_lower = linkedin.lower()

        # If it's just a username, convert to full URL
        if not linkedin.startswith('http') and '/' not in linkedin:
            return f"https://linkedin.com/in/{linkedin}"

        # If it's a full URL, standardize it
        if 'linkedin.com' in linkedin_lower:
            # Extract username from various LinkedIn URL formats
            if '/in/' in linkedin:
                username = linkedin.split('/in/')[1].split('/')[0].split('?')[0]
                return f"https://linkedin.com/in/{username}"
            elif '/company/' in linkedin:
                company = linkedin.split('/company/')[1].split('/')[0].split('?')[0]
                return f"https://linkedin.com/company/{company}"

        return linkedin

    def _normalize_bio(self, bio: str) -> str:
        """Normalize bio/description text"""
        if not bio or not isinstance(bio, str):
            return bio or ""

        bio = bio.strip()

        # Limit length
        max_length = self.config.get('max_bio_length', 500)
        if len(bio) > max_length:
            bio = bio[:max_length].strip()
            # Try to cut at word boundary
            if len(bio) > max_length * 0.8:
                bio = bio.rsplit(' ', 1)[0]

        # Normalize whitespace
        bio = re.sub(r'\s+', ' ', bio)

        # Remove excessive punctuation
        bio = re.sub(r'!{2,}', '!', bio)
        bio = re.sub(r'\?{2,}', '?', bio)
        bio = re.sub(r'\.{2,}', '.', bio)

        # Capitalize first letter
        if bio:
            bio = bio[0].upper() + bio[1:]

        return bio

    def _normalize_language(self, language: str) -> str:
        """Normalize programming language names"""
        if not language or not isinstance(language, str):
            return language or ""

        language = language.strip()

        # Common language name mappings
        language_mappings = {
            'py': 'Python',
            'python': 'Python',
            'js': 'JavaScript',
            'javascript': 'JavaScript',
            'ts': 'TypeScript',
            'typescript': 'TypeScript',
            'rb': 'Ruby',
            'ruby': 'Ruby',
            'java': 'Java',
            'cpp': 'C++',
            'c++': 'C++',
            'c#': 'C#',
            'csharp': 'C#',
            'php': 'PHP',
            'go': 'Go',
            'golang': 'Go',
            'rs': 'Rust',
            'rust': 'Rust',
            'swift': 'Swift',
            'kotlin': 'Kotlin',
            'scala': 'Scala',
            'r': 'R',
            'matlab': 'MATLAB',
            'shell': 'Shell',
            'bash': 'Shell',
            'powershell': 'PowerShell',
            'html': 'HTML',
            'css': 'CSS',
            'vue': 'Vue',
            'react': 'JavaScript'  # React is a framework, not language
        }

        language_lower = language.lower()
        return language_mappings.get(language_lower, language)

    def _normalize_topics(self, topics: List[str]) -> List[str]:
        """Normalize repository topics"""
        if not topics:
            return []

        normalized_topics = []

        for topic in topics:
            if not isinstance(topic, str):
                continue

            topic = topic.strip().lower()

            # Skip empty topics
            if not topic:
                continue

            # Skip very short topics (likely typos)
            if len(topic) < 3:
                continue

            # Normalize topic format (replace underscores and hyphens with spaces for consistency)
            topic = re.sub(r'[_-]', ' ', topic)

            # Capitalize words
            words = topic.split()
            normalized_topic = ' '.join(word.capitalize() for word in words)

            normalized_topics.append(normalized_topic)

        # Remove duplicates while preserving order
        seen = set()
        unique_topics = []
        for topic in normalized_topics:
            if topic not in seen:
                seen.add(topic)
                unique_topics.append(topic)

        return unique_topics

    def normalize_batch(self, prospects: List[Dict[str, Any]]) -> List[NormalizationResult]:
        """
        Normalize a batch of prospects
        Returns list of NormalizationResult objects
        """
        results = []

        for prospect in prospects:
            try:
                result = self.normalize_prospect(prospect)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to normalize prospect {prospect.get('login', 'unknown')}: {e}")
                # Return original prospect with error noted
                error_result = NormalizationResult(
                    normalized_prospect=prospect,
                    changes_made={},
                    normalization_warnings=[f"Normalization failed: {str(e)}"]
                )
                results.append(error_result)

        return results

    def get_normalization_stats(self, results: List[NormalizationResult]) -> Dict[str, Any]:
        """Get statistics about normalization operations"""
        total_prospects = len(results)
        if total_prospects == 0:
            return {'total_prospects': 0}

        total_changes = sum(len(result.changes_made) for result in results)
        total_warnings = sum(len(result.normalization_warnings) for result in results)

        # Count changes by field
        field_changes = {}
        for result in results:
            for field in result.changes_made.keys():
                field_changes[field] = field_changes.get(field, 0) + 1

        return {
            'total_prospects': total_prospects,
            'total_changes': total_changes,
            'total_warnings': total_warnings,
            'avg_changes_per_prospect': total_changes / total_prospects,
            'avg_warnings_per_prospect': total_warnings / total_prospects,
            'field_change_distribution': field_changes
        }
