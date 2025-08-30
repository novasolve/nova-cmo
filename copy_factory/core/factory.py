#!/usr/bin/env python3
"""
Main Copy Factory engine
"""

import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from .models import ICPProfile, ProspectData, CopyTemplate, OutreachCampaign
from .storage import CopyFactoryStorage
from .copy_generator import CopyGenerator

logger = logging.getLogger(__name__)


class CopyFactory:
    """Main Copy Factory engine"""

    def __init__(self, data_dir: str = "copy_factory/data"):
        self.storage = CopyFactoryStorage(data_dir)
        self.generator = CopyGenerator()
        self.logger = logger

    # ICP Management
    def import_icp_from_yaml(self, yaml_file: str) -> int:
        """Import ICP profiles from YAML configuration file"""
        imported_count = 0

        try:
            with open(yaml_file, 'r') as f:
                config = yaml.safe_load(f)

            if 'icp_options' in config:
                for icp_data in config['icp_options']:
                    try:
                        icp = self._yaml_to_icp(icp_data)
                        self.storage.save_icp(icp)
                        imported_count += 1
                        self.logger.info(f"Imported ICP: {icp.name}")
                    except Exception as e:
                        self.logger.error(f"Error importing ICP {icp_data.get('id', 'unknown')}: {e}")

        except Exception as e:
            self.logger.error(f"Error reading YAML file {yaml_file}: {e}")

        self.logger.info(f"Imported {imported_count} ICP profiles from {yaml_file}")
        return imported_count

    def _yaml_to_icp(self, icp_data: Dict[str, Any]) -> ICPProfile:
        """Convert YAML ICP data to ICPProfile object"""
        return ICPProfile(
            id=icp_data['id'],
            name=icp_data['name'],
            description=icp_data.get('description'),
            personas=icp_data.get('personas', []),
            firmographics=icp_data.get('firmographics', {}),
            technographics=icp_data.get('technographics', {}),
            triggers=icp_data.get('triggers', []),
            disqualifiers=icp_data.get('disqualifiers', []),
            github_queries=icp_data.get('github', {}).get('repo_queries', []),
            outreach_sequence_tag=icp_data.get('outreach', {}).get('sequence_tag')
        )

    def create_icp_template(self, icp: ICPProfile, template_type: str = "email") -> CopyTemplate:
        """Create a default copy template for an ICP"""
        template_id = f"{icp.id}_{template_type}_template"

        # Generate default subject and body based on ICP
        subject_template = self._generate_default_subject(icp, template_type)
        body_template = self._generate_default_body(icp, template_type)

        template = CopyTemplate(
            id=template_id,
            name=f"{icp.name} - {template_type.title()} Template",
            icp_id=icp.id,
            template_type=template_type,
            subject_template=subject_template,
            body_template=body_template,
            variables=self.generator.get_available_variables().keys(),
            tags=[icp.id, template_type, "auto_generated"]
        )

        self.storage.save_template(template)
        return template

    def _generate_default_subject(self, icp: ICPProfile, template_type: str) -> str:
        """Generate default subject line for ICP"""
        if template_type == "email":
            return "Question about your work with ${language} - ${icp_name}"
        elif template_type == "linkedin":
            return "Following your ${language} work - ${icp_name}"
        else:
            return "Hello from ${icp_name}"

    def _generate_default_body(self, icp: ICPProfile, template_type: str) -> str:
        """Generate default body template for ICP"""
        base_template = """Hi ${first_name},

I came across your work on ${repo_name} and was impressed by your expertise in ${language}.

As someone working with ${icp_name} at ${company_size} companies, I help teams like yours optimize their development workflows.

I'd love to hear about your experience with ${frameworks} and see if there are any challenges you're facing that we could help with.

Best regards,
[Your Name]
"""

        if template_type == "linkedin":
            return "Hi ${first_name},\n\n" + base_template.split('\n', 1)[1]
        elif template_type == "twitter":
            return "Hey ${first_name}! Saw your ${language} work on ${repo_name}. Would love to connect! #${language}"

        return base_template

    # Prospect Management
    def import_prospects_from_csv(self, csv_file: str) -> int:
        """Import prospects from CSV file"""
        return self.storage.import_prospects_from_csv(csv_file)

    def match_prospects_to_icps(self) -> Dict[str, int]:
        """Match prospects to ICP profiles based on criteria"""
        prospects = self.storage.list_prospects()
        icps = self.storage.list_icps()
        matches = {}

        for prospect in prospects:
            matched_icps = []

            for icp in icps:
                if self._prospect_matches_icp(prospect, icp):
                    matched_icps.append(icp.id)

            if matched_icps:
                prospect.icp_matches = matched_icps
                prospect.updated_at = datetime.now()
                self.storage.save_prospect(prospect)
                matches[prospect.lead_id] = len(matched_icps)

        self.logger.info(f"Matched {len(matches)} prospects to ICPs")
        return matches

    def _prospect_matches_icp(self, prospect: ProspectData, icp: ICPProfile) -> bool:
        """Check if prospect matches ICP criteria"""
        # Language match
        if icp.technographics.get('language') and prospect.language:
            if prospect.language.lower() not in [lang.lower() for lang in icp.technographics['language']]:
                return False

        # Framework match (check repo topics/description)
        if icp.technographics.get('frameworks'):
            frameworks = [fw.lower() for fw in icp.technographics['frameworks']]
            content = f"{prospect.repo_description or ''} {prospect.bio or ''}".lower()
            if not any(fw in content for fw in frameworks):
                return False

        # Company size inference (rough heuristic)
        if icp.firmographics.get('size') and prospect.followers:
            # This is a simplified heuristic - in practice you'd want more sophisticated matching
            if 'startup' in icp.firmographics['size'].lower() and prospect.followers > 100:
                return False
            if 'enterprise' in icp.firmographics['size'].lower() and prospect.followers < 10:
                return False

        return True

    # Campaign Management
    def create_campaign(self, name: str, icp_id: str, template_id: str) -> OutreachCampaign:
        """Create a new outreach campaign"""
        campaign_id = f"campaign_{icp_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Get prospects matching the ICP
        prospects = self.storage.list_prospects(icp_filter=icp_id)
        prospect_ids = [p.lead_id for p in prospects]

        campaign = OutreachCampaign(
            id=campaign_id,
            name=name,
            icp_id=icp_id,
            template_id=template_id,
            prospect_ids=prospect_ids
        )

        self.storage.save_campaign(campaign)
        self.logger.info(f"Created campaign {campaign_id} with {len(prospect_ids)} prospects")
        return campaign

    def generate_campaign_copy(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Generate personalized copy for all prospects in a campaign"""
        campaign = self.storage.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        template = self.storage.get_template(campaign.template_id)
        if not template:
            raise ValueError(f"Template {campaign.template_id} not found")

        icp = self.storage.get_icp(campaign.icp_id)
        if not icp:
            raise ValueError(f"ICP {campaign.icp_id} not found")

        generated_copy = []

        for prospect_id in campaign.prospect_ids:
            prospect = self.storage.get_prospect(prospect_id)
            if prospect:
                copy = self.generator.generate_copy(template, prospect, icp)
                generated_copy.append(copy)

        self.logger.info(f"Generated copy for {len(generated_copy)} prospects in campaign {campaign_id}")
        return generated_copy

    # Analytics and Reporting
    def get_icp_stats(self) -> Dict[str, Any]:
        """Get ICP statistics"""
        icps = self.storage.list_icps()
        prospects = self.storage.list_prospects()

        stats = {
            'total_icps': len(icps),
            'total_prospects': len(prospects),
            'icp_breakdown': {},
            'prospects_with_emails': len([p for p in prospects if p.has_email()]),
            'prospects_by_icp': {}
        }

        # ICP breakdown
        for icp in icps:
            stats['icp_breakdown'][icp.id] = {
                'name': icp.name,
                'prospects_count': len([p for p in prospects if icp.id in p.icp_matches])
            }

        return stats

    def export_campaign_data(self, campaign_id: str, output_file: str) -> int:
        """Export campaign data with generated copy"""
        copy_data = self.generate_campaign_copy(campaign_id)

        # Convert to exportable format
        export_data = []
        for copy in copy_data:
            prospect = self.storage.get_prospect(copy['prospect_id'])
            if prospect:
                export_row = {
                    'prospect_id': copy['prospect_id'],
                    'login': prospect.login,
                    'name': prospect.name,
                    'company': prospect.company,
                    'email': prospect.get_best_email(),
                    'location': prospect.location,
                    'subject': copy.get('subject'),
                    'body': copy.get('body'),
                    'template_id': copy.get('template_id'),
                    'icp_id': copy.get('icp_id')
                }
                export_data.append(export_row)

        # Write to CSV
        if export_data:
            import csv
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=export_data[0].keys())
                writer.writeheader()
                writer.writerows(export_data)

        self.logger.info(f"Exported {len(export_data)} copy items to {output_file}")
        return len(export_data)

    def validate_setup(self) -> Dict[str, Any]:
        """Validate Copy Factory setup and data integrity"""
        issues = []

        # Check ICPs
        icps = self.storage.list_icps()
        if not icps:
            issues.append("No ICP profiles found")

        # Check prospects
        prospects = self.storage.list_prospects()
        if not prospects:
            issues.append("No prospect data found")

        # Check templates
        templates = self.storage.list_templates()
        if not templates:
            issues.append("No copy templates found")

        # Check for prospects without ICP matches
        unmatched_prospects = [p for p in prospects if not p.icp_matches]
        if unmatched_prospects:
            issues.append(f"{len(unmatched_prospects)} prospects have no ICP matches")

        # Check for ICPs without templates
        icps_without_templates = []
        for icp in icps:
            icp_templates = self.storage.list_templates(icp_id=icp.id)
            if not icp_templates:
                icps_without_templates.append(icp.name)

        if icps_without_templates:
            issues.append(f"ICPs without templates: {', '.join(icps_without_templates)}")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'stats': {
                'icps': len(icps),
                'prospects': len(prospects),
                'templates': len(templates),
                'campaigns': len(self.storage.list_campaigns())
            }
        }
