#!/usr/bin/env python3
"""
Copy generation engine for personalized outreach
"""

import re
from typing import Dict, List, Optional, Any
from string import Template
import logging

from .models import ICPProfile, ProspectData, CopyTemplate

logger = logging.getLogger(__name__)


class CopyGenerator:
    """Engine for generating personalized outreach copy"""

    def __init__(self):
        self.variable_patterns = {
            'first_name': self._extract_first_name,
            'last_name': self._extract_last_name,
            'company': self._extract_company,
            'repo_name': self._extract_repo_name,
            'repo_description': self._extract_repo_description,
            'language': self._extract_language,
            'icp_name': self._extract_icp_name,
            'location': self._extract_location,
            'bio': self._extract_bio,
            'signal': self._extract_signal
        }

    def generate_copy(self, template: CopyTemplate, prospect: ProspectData,
                     icp: ICPProfile) -> Dict[str, str]:
        """Generate personalized copy from template"""
        try:
            # Extract variables
            variables = self._extract_variables(prospect, icp)

            # Generate subject if template has one
            subject = None
            if template.subject_template:
                subject = self._render_template(template.subject_template, variables)

            # Generate body
            body = self._render_template(template.body_template, variables)

            return {
                'subject': subject,
                'body': body,
                'variables_used': variables,
                'template_id': template.id,
                'prospect_id': prospect.lead_id,
                'icp_id': icp.id
            }

        except Exception as e:
            logger.error(f"Error generating copy for prospect {prospect.login}: {e}")
            return {
                'subject': None,
                'body': f"Error generating copy: {str(e)}",
                'variables_used': {},
                'template_id': template.id,
                'prospect_id': prospect.lead_id,
                'icp_id': icp.id
            }

    def _extract_variables(self, prospect: ProspectData, icp: ICPProfile) -> Dict[str, str]:
        """Extract all available variables from prospect and ICP data"""
        variables = {}

        for var_name, extractor_func in self.variable_patterns.items():
            try:
                value = extractor_func(prospect, icp)
                if value:
                    variables[var_name] = value
            except Exception as e:
                logger.warning(f"Error extracting variable {var_name}: {e}")
                variables[var_name] = ""

        # Add custom ICP-specific variables
        variables.update(self._extract_icp_variables(icp))

        return variables

    def _render_template(self, template_text: str, variables: Dict[str, str]) -> str:
        """Render template with variables"""
        try:
            # Use string.Template for safe substitution
            template = Template(template_text)

            # Replace variables with fallback to empty string
            safe_vars = {k: v or "" for k, v in variables.items()}

            return template.safe_substitute(safe_vars)

        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            return template_text

    # Variable extraction functions
    def _extract_first_name(self, prospect: ProspectData, icp: ICPProfile) -> Optional[str]:
        """Extract first name from prospect name"""
        if not prospect.name:
            return None

        # Split on common separators
        name_parts = re.split(r'[,\s]+', prospect.name.strip())
        if name_parts:
            first_name = name_parts[0]
            # Capitalize properly
            return first_name.capitalize()
        return None

    def _extract_last_name(self, prospect: ProspectData, icp: ICPProfile) -> Optional[str]:
        """Extract last name from prospect name"""
        if not prospect.name:
            return None

        name_parts = re.split(r'[,\s]+', prospect.name.strip())
        if len(name_parts) > 1:
            last_name = name_parts[-1]
            return last_name.capitalize()
        return None

    def _extract_company(self, prospect: ProspectData, icp: ICPProfile) -> Optional[str]:
        """Extract company name"""
        if prospect.company:
            # Clean up company name
            company = prospect.company.strip()
            # Remove common prefixes
            company = re.sub(r'^@', '', company)
            return company
        return None

    def _extract_repo_name(self, prospect: ProspectData, icp: ICPProfile) -> Optional[str]:
        """Extract repository name"""
        if prospect.repo_full_name:
            # Extract repo name from full name (owner/repo)
            parts = prospect.repo_full_name.split('/')
            if len(parts) == 2:
                return parts[1]
        return None

    def _extract_repo_description(self, prospect: ProspectData, icp: ICPProfile) -> Optional[str]:
        """Extract repository description"""
        return prospect.repo_description

    def _extract_language(self, prospect: ProspectData, icp: ICPProfile) -> Optional[str]:
        """Extract programming language"""
        return prospect.language

    def _extract_icp_name(self, prospect: ProspectData, icp: ICPProfile) -> str:
        """Extract ICP name"""
        return icp.name

    def _extract_location(self, prospect: ProspectData, icp: ICPProfile) -> Optional[str]:
        """Extract location"""
        return prospect.location

    def _extract_bio(self, prospect: ProspectData, icp: ICPProfile) -> Optional[str]:
        """Extract bio"""
        return prospect.bio

    def _extract_signal(self, prospect: ProspectData, icp: ICPProfile) -> Optional[str]:
        """Extract signal/trigger"""
        return prospect.signal

    def _extract_icp_variables(self, icp: ICPProfile) -> Dict[str, str]:
        """Extract ICP-specific variables"""
        variables = {}

        # Add ICP metadata
        variables['icp_description'] = icp.description or ""

        # Add technographics
        if icp.technographics.get('language'):
            variables['primary_language'] = ', '.join(icp.technographics['language'])

        if icp.technographics.get('frameworks'):
            variables['frameworks'] = ', '.join(icp.technographics['frameworks'])

        # Add firmographics
        if icp.firmographics.get('size'):
            variables['company_size'] = icp.firmographics['size']

        if icp.firmographics.get('geo'):
            variables['target_geo'] = ', '.join(icp.firmographics['geo'])

        return variables

    def validate_template(self, template: CopyTemplate) -> List[str]:
        """Validate template for required variables and syntax"""
        errors = []

        # Check for unmatched variables in subject
        if template.subject_template:
            subject_vars = self._extract_template_variables(template.subject_template)
            for var in subject_vars:
                if var not in self.variable_patterns and not var.startswith('icp_'):
                    errors.append(f"Unknown variable '{var}' in subject template")

        # Check for unmatched variables in body
        body_vars = self._extract_template_variables(template.body_template)
        for var in body_vars:
            if var not in self.variable_patterns and not var.startswith('icp_'):
                errors.append(f"Unknown variable '{var}' in body template")

        return errors

    def _extract_template_variables(self, template_text: str) -> List[str]:
        """Extract variable names from template text"""
        # Find all ${variable} patterns
        pattern = r'\$\{([^}]+)\}'
        matches = re.findall(pattern, template_text)
        return matches

    def get_available_variables(self) -> Dict[str, str]:
        """Get list of all available variables with descriptions"""
        return {
            'first_name': 'Prospect\'s first name',
            'last_name': 'Prospect\'s last name',
            'company': 'Prospect\'s company name',
            'repo_name': 'Repository name (without owner)',
            'repo_description': 'Repository description',
            'language': 'Primary programming language',
            'icp_name': 'ICP profile name',
            'location': 'Prospect\'s location',
            'bio': 'Prospect\'s bio/description',
            'signal': 'Signal/trigger that identified this prospect',
            'icp_description': 'ICP profile description',
            'primary_language': 'Primary language from ICP technographics',
            'frameworks': 'Frameworks from ICP technographics',
            'company_size': 'Company size from ICP firmographics',
            'target_geo': 'Target geography from ICP firmographics'
        }

    def preview_template(self, template: CopyTemplate, sample_prospect: ProspectData = None,
                        sample_icp: ICPProfile = None) -> Dict[str, str]:
        """Preview template with sample data"""
        if not sample_prospect:
            sample_prospect = ProspectData(
                lead_id="preview_123",
                login="johndoe",
                name="John Doe",
                company="Acme Corp",
                repo_full_name="johndoe/myproject",
                repo_description="A sample Python project",
                language="Python",
                location="San Francisco, CA",
                bio="Software engineer passionate about open source",
                signal="Recent commit activity"
            )

        if not sample_icp:
            sample_icp = ICPProfile(
                id="sample_icp",
                name="Python Developers",
                description="Developers working with Python",
                technographics={"language": ["Python"], "frameworks": ["Django", "Flask"]},
                firmographics={"size": "50-200 employees", "geo": ["US", "EU"]}
            )

        return self.generate_copy(template, sample_prospect, sample_icp)

