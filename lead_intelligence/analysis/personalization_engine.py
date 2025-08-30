#!/usr/bin/env python3
"""
Personalization Engine
Generates personalized outreach content based on lead intelligence and cohort analysis
"""

import re
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RepoBrief:
    """Structured repository brief for personalization"""
    email: str
    first_name: str
    repo: str
    one_line_context: str
    personalization_snippet: str
    subject_options: List[str]
    body_short: str
    risk_flags: List[str]
    cohort: Dict[str, str]


@dataclass
class InstantlyRow:
    """Instantly-compatible CSV row"""
    email: str
    first_name: str
    repo: str
    language: str
    personalization_snippet: str
    subject: str
    body: str
    unsub: str


class PersonalizationEngine:
    """Generates personalized outreach content based on lead intelligence"""

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load personalization templates by language and cohort"""
        return {
            'python_pytest': {
                'subjects': [
                    'tiny PR to keep {{repo}} green',
                    'auto-fix failing pytest in {{repo}}',
                    'less CI yak-shaving for {{repo}}'
                ],
                'body_template': 'Built a small GitHub App that wakes only when CI fails on a PR, proposes a minimal patch, and opens a PR. Happy to try on {{repo}}—close it if not helpful.',
                'context_patterns': [
                    'Active pytest project with {{open_prs}} open PRs',
                    'Python project with intermittent CI flakes',
                    '{{stars}} stars, active development'
                ]
            },
            'javascript_jest': {
                'subjects': [
                    'keeps {{repo}} green without big diffs',
                    'minimal PR when {{repo}} CI fails',
                    'auto-fix failing jest tests'
                ],
                'body_template': 'Tiny PRs when CI fails—no sweeping rewrites or config churn. Worth a 3-min test branch on {{repo}}?',
                'context_patterns': [
                    'Active JavaScript project with {{open_prs}} open PRs',
                    'JS/TS project with CI reliability issues',
                    '{{stars}} stars, modern JavaScript stack'
                ]
            },
            'go': {
                'subjects': [
                    '1 small PR when go test fails',
                    'auto-fix failing go tests in {{repo}}',
                    'keeps {{repo}} CI green'
                ],
                'body_template': 'Catches failing tests in CI, proposes a minimal fix, opens a PR. Happy to try on {{repo}}—close if noisy.',
                'context_patterns': [
                    'Go project with {{open_prs}} open PRs',
                    'Golang project with test reliability issues',
                    '{{stars}} stars, Go ecosystem'
                ]
            },
            'rust': {
                'subjects': [
                    'less CI yak-shaving for {{repo}}',
                    'auto-fix failing cargo tests',
                    'minimal diffs when {{repo}} CI fails'
                ],
                'body_template': 'Minimal diffs when checks fail, with a short explainer in the PR. One test PR on {{repo}}?',
                'context_patterns': [
                    'Rust project with {{open_prs}} open PRs',
                    'Cargo-based project with CI challenges',
                    '{{stars}} stars, Rust ecosystem'
                ]
            },
            'default': {
                'subjects': [
                    'auto-fix failing tests in {{repo}}',
                    'keeps {{repo}} CI green',
                    'minimal PR for test reliability'
                ],
                'body_template': 'Built a GitHub App that proposes minimal patches when CI fails. Worth trying on {{repo}}?',
                'context_patterns': [
                    'Active project with {{open_prs}} open PRs',
                    'Project with CI reliability challenges',
                    '{{stars}} stars, active development'
                ]
            }
        }

    def generate_repo_brief(self, lead: Dict[str, Any], enrichment: Dict[str, Any],
                          cohort: Dict[str, str]) -> RepoBrief:
        """Generate personalized repo brief"""
        # Extract key information
        email = lead.get('email', '')
        first_name = self._extract_first_name(lead.get('maintainer_name', ''))
        repo = lead.get('repo', '')

        # Generate one-line context
        context = self._generate_context(lead, enrichment, cohort)

        # Generate personalization snippet
        snippet = self._generate_personalization_snippet(lead, enrichment)

        # Get subject options based on cohort
        subject_options = self._get_subject_options(cohort)

        # Generate body
        body = self._get_body_template(cohort, repo)

        # Determine risk flags
        risk_flags = self._assess_risk_flags(lead, enrichment)

        return RepoBrief(
            email=email,
            first_name=first_name,
            repo=repo,
            one_line_context=context,
            personalization_snippet=snippet,
            subject_options=subject_options,
            body_short=body,
            risk_flags=risk_flags,
            cohort=cohort
        )

    def generate_instantly_row(self, brief: RepoBrief) -> InstantlyRow:
        """Convert repo brief to Instantly-compatible CSV row"""
        # Select best subject
        subject = self._select_best_subject(brief.subject_options, brief.cohort)

        return InstantlyRow(
            email=brief.email,
            first_name=brief.first_name,
            repo=brief.repo,
            language=brief.cohort.get('lang', 'unknown'),
            personalization_snippet=brief.personalization_snippet,
            subject=subject,
            body=brief.body_short,
            unsub='{{unsubscribe}}'
        )

    def _extract_first_name(self, maintainer_name: str) -> str:
        """Extract first name from maintainer name"""
        if not maintainer_name:
            return ''

        # Split by common separators
        name_parts = re.split(r'[_\-\s]+', maintainer_name.strip())

        # Return first part, capitalized
        if name_parts:
            first_name = name_parts[0].strip()
            # Handle common variations
            if first_name.lower() in ['the', 'a', 'an', 'dr', 'mr', 'mrs', 'ms']:
                return name_parts[1] if len(name_parts) > 1 else first_name
            return first_name.capitalize()

        return ''

    def _generate_context(self, lead: Dict[str, Any], enrichment: Dict[str, Any],
                        cohort: Dict[str, str]) -> str:
        """Generate one-line context about the repository"""
        language = cohort.get('lang', 'unknown')
        stars = lead.get('stars', 0) or enrichment.get('stars', 0)
        open_prs = enrichment.get('prs', {}).get('open', 0)

        template_key = f"{language.lower()}_{enrichment.get('tests', {}).get('framework', '')}"
        if template_key not in self.templates:
            template_key = 'default'

        patterns = self.templates[template_key]['context_patterns']
        context = patterns[0]  # Use first pattern

        # Fill in template variables
        context = context.replace('{{open_prs}}', str(open_prs))
        context = context.replace('{{stars}}', str(stars))

        return context

    def _generate_personalization_snippet(self, lead: Dict[str, Any],
                                       enrichment: Dict[str, Any]) -> str:
        """Generate personalized snippet based on repo signals"""
        snippets = []

        # CI failure signals
        ci_data = enrichment.get('ci', {})
        if ci_data.get('fail_rate_30d', 0) > 0.2:
            if ci_data.get('flake_hints'):
                snippets.append('noticed Windows-only flakes in CI')
            else:
                snippets.append('noticed CI reliability issues')

        # Test framework signals
        test_data = enrichment.get('tests', {})
        if test_data.get('framework'):
            framework = test_data['framework']
            snippets.append(f'noticed {framework} test failures')

        # Activity signals
        activity = enrichment.get('activity', {})
        if activity.get('commits_30d', 0) > 20:
            snippets.append('noticed high development velocity')

        # Default fallback
        if not snippets:
            snippets.append('noticed CI/test automation opportunities')

        snippet = snippets[0]
        repo = lead.get('repo', '').split('/')[-1]  # Get repo name only
        snippet += f' for {repo}'

        return snippet

    def _get_subject_options(self, cohort: Dict[str, str]) -> List[str]:
        """Get subject options based on cohort"""
        language = cohort.get('lang', 'unknown').lower()
        framework = 'pytest'  # Default assumption, could be enhanced

        template_key = f"{language}_{framework}"
        if template_key not in self.templates:
            template_key = 'default'

        subjects = self.templates[template_key]['subjects'][:]

        # Fill in repo name
        repo_name = cohort.get('repo', '').split('/')[-1]
        subjects = [s.replace('{{repo}}', repo_name) for s in subjects]

        return subjects

    def _get_body_template(self, cohort: Dict[str, str], repo: str) -> str:
        """Get body template based on cohort"""
        language = cohort.get('lang', 'unknown').lower()
        framework = 'pytest'  # Default assumption

        template_key = f"{language}_{framework}"
        if template_key not in self.templates:
            template_key = 'default'

        body = self.templates[template_key]['body_template']
        repo_name = repo.split('/')[-1]
        body = body.replace('{{repo}}', repo_name)

        return body

    def _assess_risk_flags(self, lead: Dict[str, Any], enrichment: Dict[str, Any]) -> List[str]:
        """Assess content risk flags"""
        flags = ['ok_to_send']  # Default assumption

        # Check for potentially sensitive content
        email = lead.get('email', '').lower()

        # Role-based emails
        if any(role in email for role in ['admin@', 'info@', 'noreply@', 'support@']):
            flags.append('role_email_caution')

        # Public email domains
        domain = email.split('@')[1] if '@' in email else ''
        if domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
            flags.append('public_domain')

        return flags

    def _select_best_subject(self, subject_options: List[str], cohort: Dict[str, str]) -> str:
        """Select the best subject based on cohort characteristics"""
        if not subject_options:
            return 'auto-fix failing tests'

        # Stars bucket influences tone
        stars_bucket = cohort.get('stars_bucket', '1k-5k')
        if stars_bucket in ['>20k', '5k-20k']:
            # More conservative tone for popular repos
            return subject_options[0]  # Usually the most conservative
        else:
            # More direct tone for smaller repos
            return subject_options[1] if len(subject_options) > 1 else subject_options[0]

    def deliverability_check(self, brief: RepoBrief) -> Dict[str, Any]:
        """Perform deliverability check on generated content"""
        result = {
            'risk': 'low',
            'issues': [],
            'recommendations': []
        }

        body = brief.body_short
        subject = brief.subject_options[0] if brief.subject_options else ''

        # Length checks
        if len(body) > 80:
            result['issues'].append('body_too_long')
            result['recommendations'].append('Shorten body to under 80 words')

        if len(subject) > 45:
            result['issues'].append('subject_too_long')
            result['recommendations'].append('Shorten subject to under 45 characters')

        # Spam trigger checks
        spam_triggers = ['free', 'guarantee', 'urgent', 'act now', 'limited time']
        body_lower = body.lower()
        if any(trigger in body_lower for trigger in spam_triggers):
            result['issues'].append('spam_triggers')
            result['recommendations'].append('Remove potential spam trigger words')

        # Link checks
        link_count = body.count('http') + body.count('{{')
        if link_count > 1:
            result['issues'].append('multiple_links')
            result['recommendations'].append('Limit to one link placeholder')

        # Risk assessment
        if result['issues']:
            result['risk'] = 'medium' if len(result['issues']) == 1 else 'high'

        return result
