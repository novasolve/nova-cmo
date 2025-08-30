#!/usr/bin/env python3
"""
Compliance Checker
Handles regulatory compliance, sanctions screening, and geo-based filtering
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
import re
import os


@dataclass
class ComplianceResult:
    """Result of compliance check"""
    compliant: bool
    risk_level: str  # 'low', 'medium', 'high', 'block'
    risk_factors: List[str]
    blocked_reason: Optional[str] = None
    geo_location: Optional[str] = None
    sanctions_flags: List[str] = None

    def __post_init__(self):
        if self.sanctions_flags is None:
            self.sanctions_flags = []


class ComplianceChecker:
    """Checks prospects for regulatory compliance and risk factors"""

    def __init__(self, icp_config: Optional[Dict[str, Any]] = None):
        self.icp_config = icp_config or {}
        self.sanctions_lists = self._load_sanctions_lists()
        self.geo_restrictions = self._load_geo_restrictions()

    def check_compliance(self, prospect: Dict[str, Any]) -> ComplianceResult:
        """Check a prospect for compliance issues"""

        risk_factors = []
        sanctions_flags = []
        blocked_reason = None

        # 1. Geo-based compliance check
        geo_result = self._check_geo_compliance(prospect)
        if geo_result.get('blocked'):
            return ComplianceResult(
                compliant=False,
                risk_level='block',
                risk_factors=['geo_restricted'],
                blocked_reason=geo_result['reason'],
                geo_location=geo_result.get('location')
            )

        # 2. Sanctions screening
        sanctions_result = self._check_sanctions(prospect)
        if sanctions_result['flagged']:
            sanctions_flags.extend(sanctions_result['flags'])
            risk_factors.append('sanctions_match')

        # 3. Email domain compliance
        email_result = self._check_email_compliance(prospect)
        if not email_result['compliant']:
            risk_factors.extend(email_result['issues'])

        # 4. Company/domain compliance
        company_result = self._check_company_compliance(prospect)
        if not company_result['compliant']:
            risk_factors.extend(company_result['issues'])

        # 5. Content compliance (bio, repo names, etc.)
        content_result = self._check_content_compliance(prospect)
        if not content_result['compliant']:
            risk_factors.extend(content_result['issues'])

        # Determine overall risk level
        risk_level = self._calculate_risk_level(risk_factors, sanctions_flags)

        return ComplianceResult(
            compliant=len(risk_factors) == 0,
            risk_level=risk_level,
            risk_factors=risk_factors,
            sanctions_flags=sanctions_flags,
            geo_location=geo_result.get('location')
        )

    def _check_geo_compliance(self, prospect: Dict[str, Any]) -> Dict[str, Any]:
        """Check geographic compliance"""
        result = {
            'blocked': False,
            'reason': None,
            'location': None
        }

        # Extract location from prospect data
        location = prospect.get('location', '').strip()
        if not location:
            return result

        result['location'] = location

        # Check against blocked geo list
        blocked_geos = self.icp_config.get('geo_block', [])
        if not blocked_geos:
            return result

        location_lower = location.lower()

        # Check for blocked countries/regions
        for blocked_geo in blocked_geos:
            blocked_lower = blocked_geo.lower()

            # Direct country name match
            if blocked_lower in location_lower:
                result['blocked'] = True
                result['reason'] = f"Location contains blocked geo: {blocked_geo}"
                return result

            # Check for common geo indicators
            if blocked_geo == 'CN' and any(term in location_lower for term in ['china', 'chinese', 'beijing', 'shanghai']):
                result['blocked'] = True
                result['reason'] = "China-based location blocked"
                return result

            if blocked_geo == 'RU' and any(term in location_lower for term in ['russia', 'russian', 'moscow', 'saint petersburg']):
                result['blocked'] = True
                result['reason'] = "Russia-based location blocked"
                return result

        return result

    def _check_sanctions(self, prospect: Dict[str, Any]) -> Dict[str, Any]:
        """Screen against sanctions lists"""
        result = {
            'flagged': False,
            'flags': []
        }

        # Check name
        name = prospect.get('name', '').strip()
        if name:
            name_flags = self._screen_name_against_sanctions(name)
            if name_flags:
                result['flagged'] = True
                result['flags'].extend([f"name:{flag}" for flag in name_flags])

        # Check company
        company = prospect.get('company', '').strip()
        if company:
            company_flags = self._screen_name_against_sanctions(company)
            if company_flags:
                result['flagged'] = True
                result['flags'].extend([f"company:{flag}" for flag in company_flags])

        # Check email domain
        email = prospect.get('email_profile') or prospect.get('email_public_commit')
        if email and '@' in email:
            domain = email.split('@')[1].lower()
            domain_flags = self._screen_domain_against_sanctions(domain)
            if domain_flags:
                result['flagged'] = True
                result['flags'].extend([f"domain:{flag}" for flag in domain_flags])

        return result

    def _screen_name_against_sanctions(self, name: str) -> List[str]:
        """Screen a name against sanctions lists"""
        if not name or not self.sanctions_lists:
            return []

        name_lower = name.lower().strip()
        flags = []

        # Simple name matching (in production, use more sophisticated fuzzy matching)
        for sanctions_list in self.sanctions_lists.values():
            for entry in sanctions_list:
                entry_lower = entry.lower()
                if entry_lower in name_lower or name_lower in entry_lower:
                    flags.append(entry)
                    break

        return flags

    def _screen_domain_against_sanctions(self, domain: str) -> List[str]:
        """Screen a domain against sanctions lists"""
        if not domain or not self.sanctions_lists:
            return []

        domain_lower = domain.lower()
        flags = []

        # Check domain against sanctioned domains
        sanctioned_domains = self.sanctions_lists.get('domains', [])
        for sanctioned_domain in sanctioned_domains:
            if sanctioned_domain.lower() in domain_lower:
                flags.append(sanctioned_domain)
                break

        return flags

    def _check_email_compliance(self, prospect: Dict[str, Any]) -> Dict[str, Any]:
        """Check email for compliance issues"""
        result = {
            'compliant': True,
            'issues': []
        }

        email = prospect.get('email_profile') or prospect.get('email_public_commit')
        if not email:
            return result

        domain = email.split('@')[1].lower() if '@' in email else ''

        # Check disposable email
        if prospect.get('is_disposable_email'):
            result['compliant'] = False
            result['issues'].append('disposable_email')

        # Check blocked domains
        blocked_domains = self.icp_config.get('blocked_email_domains', [])
        if domain in [d.lower() for d in blocked_domains]:
            result['compliant'] = False
            result['issues'].append('blocked_email_domain')

        return result

    def _check_company_compliance(self, prospect: Dict[str, Any]) -> Dict[str, Any]:
        """Check company for compliance issues"""
        result = {
            'compliant': True,
            'issues': []
        }

        company = prospect.get('company', '').strip()
        if not company:
            return result

        company_lower = company.lower()

        # Check against blocked companies
        blocked_companies = self.icp_config.get('blocked_companies', [])
        for blocked in blocked_companies:
            if blocked.lower() in company_lower:
                result['compliant'] = False
                result['issues'].append('blocked_company')
                break

        return result

    def _check_content_compliance(self, prospect: Dict[str, Any]) -> Dict[str, Any]:
        """Check content for compliance issues"""
        result = {
            'compliant': True,
            'issues': []
        }

        # Check bio for prohibited content
        bio = prospect.get('bio', '').lower()
        if bio:
            prohibited_terms = self.icp_config.get('prohibited_bio_terms', [])
            for term in prohibited_terms:
                if term.lower() in bio:
                    result['compliant'] = False
                    result['issues'].append('prohibited_bio_content')
                    break

        # Check repository name
        repo_name = prospect.get('repo_full_name', '').lower()
        if repo_name:
            prohibited_repo_terms = self.icp_config.get('prohibited_repo_terms', [])
            for term in prohibited_repo_terms:
                if term.lower() in repo_name:
                    result['compliant'] = False
                    result['issues'].append('prohibited_repo_name')
                    break

        return result

    def _calculate_risk_level(self, risk_factors: List[str], sanctions_flags: List[str]) -> str:
        """Calculate overall risk level"""
        if not risk_factors and not sanctions_flags:
            return 'low'

        # Sanctions hits are always high/block risk
        if sanctions_flags:
            if len(sanctions_flags) > 1:
                return 'block'
            else:
                return 'high'

        # Count risk factors
        risk_count = len(risk_factors)

        if risk_count >= 3:
            return 'high'
        elif risk_count >= 2:
            return 'medium'
        else:
            return 'low'

    def _load_sanctions_lists(self) -> Dict[str, List[str]]:
        """Load sanctions lists (simplified version)"""
        # In production, this would load from actual sanctions databases
        # For now, using simplified example lists
        return {
            'names': [
                'Example Sanctioned Entity',
                # Add real sanctions list entries here
            ],
            'domains': [
                'example-sanctioned-domain.com',
                # Add sanctioned domains here
            ],
            'countries': [
                'North Korea',
                'Iran',
                # Add sanctioned countries here
            ]
        }

    def _load_geo_restrictions(self) -> Dict[str, Any]:
        """Load geo restrictions from ICP config"""
        return {
            'blocked_countries': self.icp_config.get('geo_block', []),
            'allowed_countries': self.icp_config.get('geo_allow', [])
        }

    def should_block_prospect(self, compliance_result: ComplianceResult) -> bool:
        """Determine if prospect should be blocked based on compliance result"""
        return compliance_result.risk_level == 'block' or not compliance_result.compliant

    def get_compliance_summary(self, prospects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get compliance summary for a batch of prospects"""
        results = []
        blocked_count = 0
        risk_counts = {'low': 0, 'medium': 0, 'high': 0, 'block': 0}

        for prospect in prospects:
            compliance_result = self.check_compliance(prospect)
            results.append(compliance_result)

            risk_counts[compliance_result.risk_level] += 1
            if self.should_block_prospect(compliance_result):
                blocked_count += 1

        return {
            'total_prospects': len(prospects),
            'blocked_count': blocked_count,
            'compliance_rate': (len(prospects) - blocked_count) / len(prospects) if prospects else 0,
            'risk_distribution': risk_counts,
            'results': results
        }
