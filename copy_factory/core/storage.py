#!/usr/bin/env python3
"""
Storage system for Copy Factory data
"""

import json
import csv
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Iterator
from datetime import datetime
import logging

from .models import ICPProfile, ProspectData, CopyTemplate, OutreachCampaign
from .database import CopyFactoryDatabase
from .config import get_config

logger = logging.getLogger(__name__)


class CopyFactoryStorage:
    """Main storage system for Copy Factory"""

    def __init__(self, data_dir: str = "copy_factory/data"):
        self.config = get_config()
        self.storage_config = self.config.get_storage_config()

        # Choose storage backend
        if self.storage_config['backend'] == 'database':
            self.backend = 'database'
            self.database = CopyFactoryDatabase(self.config.get_database_path())
            self.data_dir = None
        else:
            self.backend = 'json'
            self.database = None
            self.data_dir = Path(data_dir)
            self.data_dir.mkdir(parents=True, exist_ok=True)

            # Storage paths for JSON backend
            self.icp_dir = self.data_dir / "icp"
            self.prospects_dir = self.data_dir / "prospects"
            self.templates_dir = self.data_dir / "templates"
            self.campaigns_dir = self.data_dir / "campaigns"

            # Create subdirectories
            for dir_path in [self.icp_dir, self.prospects_dir, self.templates_dir, self.campaigns_dir]:
                dir_path.mkdir(parents=True, exist_ok=True)

            # Index files
            self.icp_index = self.data_dir / "icp_index.json"
            self.prospects_index = self.data_dir / "prospects_index.json"
            self.templates_index = self.data_dir / "templates_index.json"
            self.campaigns_index = self.data_dir / "campaigns_index.json"

    # ICP Management
    def save_icp(self, icp: ICPProfile) -> None:
        """Save ICP profile"""
        if self.backend == 'database':
            self.database.save_icp(icp)
        else:
            icp_file = self.icp_dir / f"{icp.id}.json"
            with open(icp_file, 'w') as f:
                json.dump(icp.to_dict(), f, indent=2)
            self._update_icp_index()

    def get_icp(self, icp_id: str) -> Optional[ICPProfile]:
        """Get ICP profile"""
        if self.backend == 'database':
            return self.database.get_icp(icp_id)
        else:
            icp_file = self.icp_dir / f"{icp_id}.json"
            if not icp_file.exists():
                return None

            with open(icp_file, 'r') as f:
                data = json.load(f)
            return ICPProfile.from_dict(data)

    def list_icps(self) -> List[ICPProfile]:
        """List all ICP profiles"""
        if self.backend == 'database':
            return self.database.list_icps()
        else:
            icps = []
            for icp_file in self.icp_dir.glob("*.json"):
                try:
                    with open(icp_file, 'r') as f:
                        data = json.load(f)
                    icps.append(ICPProfile.from_dict(data))
                except Exception as e:
                    logger.error(f"Error loading ICP {icp_file}: {e}")
            return icps

    def delete_icp(self, icp_id: str) -> bool:
        """Delete ICP profile"""
        if self.backend == 'database':
            return self.database.delete_icp(icp_id)
        else:
            icp_file = self.icp_dir / f"{icp_id}.json"
            if icp_file.exists():
                icp_file.unlink()
                self._update_icp_index()
                return True
            return False

    # Prospect Management
    def save_prospect(self, prospect: ProspectData) -> None:
        """Save prospect data"""
        prospect_file = self.prospects_dir / f"{prospect.lead_id}.json"
        with open(prospect_file, 'w') as f:
            json.dump(prospect.to_dict(), f, indent=2)
        self._update_prospects_index()

    def get_prospect(self, lead_id: str) -> Optional[ProspectData]:
        """Get prospect by lead ID"""
        prospect_file = self.prospects_dir / f"{lead_id}.json"
        if not prospect_file.exists():
            return None

        with open(prospect_file, 'r') as f:
            data = json.load(f)
        return ProspectData.from_dict(data)

    def list_prospects(self, limit: Optional[int] = None, icp_filter: Optional[str] = None) -> List[ProspectData]:
        """List prospects with optional filtering"""
        prospects = []
        for prospect_file in self.prospects_dir.glob("*.json"):
            try:
                with open(prospect_file, 'r') as f:
                    data = json.load(f)
                prospect = ProspectData.from_dict(data)

                # Apply ICP filter if specified
                if icp_filter and icp_filter not in prospect.icp_matches:
                    continue

                prospects.append(prospect)

                if limit and len(prospects) >= limit:
                    break
            except Exception as e:
                logger.error(f"Error loading prospect {prospect_file}: {e}")

        return prospects

    def delete_prospect(self, lead_id: str) -> bool:
        """Delete prospect"""
        prospect_file = self.prospects_dir / f"{lead_id}.json"
        if prospect_file.exists():
            prospect_file.unlink()
            self._update_prospects_index()
            return True
        return False

    # Template Management
    def save_template(self, template: CopyTemplate) -> None:
        """Save copy template"""
        template_file = self.templates_dir / f"{template.id}.json"
        with open(template_file, 'w') as f:
            json.dump(template.to_dict(), f, indent=2)
        self._update_templates_index()

    def get_template(self, template_id: str) -> Optional[CopyTemplate]:
        """Get template by ID"""
        template_file = self.templates_dir / f"{template_id}.json"
        if not template_file.exists():
            return None

        with open(template_file, 'r') as f:
            data = json.load(f)
        return CopyTemplate.from_dict(data)

    def list_templates(self, icp_id: Optional[str] = None) -> List[CopyTemplate]:
        """List templates, optionally filtered by ICP"""
        templates = []
        for template_file in self.templates_dir.glob("*.json"):
            try:
                with open(template_file, 'r') as f:
                    data = json.load(f)
                template = CopyTemplate.from_dict(data)

                if icp_id and template.icp_id != icp_id:
                    continue

                templates.append(template)
            except Exception as e:
                logger.error(f"Error loading template {template_file}: {e}")
        return templates

    def delete_template(self, template_id: str) -> bool:
        """Delete template"""
        template_file = self.templates_dir / f"{template_id}.json"
        if template_file.exists():
            template_file.unlink()
            self._update_templates_index()
            return True
        return False

    # Campaign Management
    def save_campaign(self, campaign: OutreachCampaign) -> None:
        """Save outreach campaign"""
        campaign_file = self.campaigns_dir / f"{campaign.id}.json"
        with open(campaign_file, 'w') as f:
            json.dump(campaign.to_dict(), f, indent=2)
        self._update_campaigns_index()

    def get_campaign(self, campaign_id: str) -> Optional[OutreachCampaign]:
        """Get campaign by ID"""
        campaign_file = self.campaigns_dir / f"{campaign_id}.json"
        if not campaign_file.exists():
            return None

        with open(campaign_file, 'r') as f:
            data = json.load(f)
        return OutreachCampaign.from_dict(data)

    def list_campaigns(self, status_filter: Optional[str] = None) -> List[OutreachCampaign]:
        """List campaigns, optionally filtered by status"""
        campaigns = []
        for campaign_file in self.campaigns_dir.glob("*.json"):
            try:
                with open(campaign_file, 'r') as f:
                    data = json.load(f)
                campaign = OutreachCampaign.from_dict(data)

                if status_filter and campaign.status != status_filter:
                    continue

                campaigns.append(campaign)
            except Exception as e:
                logger.error(f"Error loading campaign {campaign_file}: {e}")
        return campaigns

    def delete_campaign(self, campaign_id: str) -> bool:
        """Delete campaign"""
        campaign_file = self.campaigns_dir / f"{campaign_id}.json"
        if campaign_file.exists():
            campaign_file.unlink()
            self._update_campaigns_index()
            return True
        return False

    # Index management
    def _update_icp_index(self):
        """Update ICP index file"""
        icps = self.list_icps()
        index = {icp.id: icp.to_dict() for icp in icps}
        with open(self.icp_index, 'w') as f:
            json.dump(index, f, indent=2)

    def _update_prospects_index(self):
        """Update prospects index file"""
        prospects = self.list_prospects()
        index = {p.lead_id: p.to_dict() for p in prospects}
        with open(self.prospects_index, 'w') as f:
            json.dump(index, f, indent=2)

    def _update_templates_index(self):
        """Update templates index file"""
        templates = self.list_templates()
        index = {t.id: t.to_dict() for t in templates}
        with open(self.templates_index, 'w') as f:
            json.dump(index, f, indent=2)

    def _update_campaigns_index(self):
        """Update campaigns index file"""
        campaigns = self.list_campaigns()
        index = {c.id: c.to_dict() for c in campaigns}
        with open(self.campaigns_index, 'w') as f:
            json.dump(index, f, indent=2)

    # Import/Export functionality
    def import_prospects_from_csv(self, csv_file: str) -> int:
        """Import prospects from CSV file"""
        imported_count = 0

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    # Convert CSV row to ProspectData
                    prospect = self._csv_row_to_prospect(row)
                    self.save_prospect(prospect)
                    imported_count += 1
                except Exception as e:
                    logger.error(f"Error importing row {row.get('lead_id', 'unknown')}: {e}")

        logger.info(f"Imported {imported_count} prospects from {csv_file}")
        return imported_count

    def export_prospects_to_csv(self, output_file: str, icp_filter: Optional[str] = None) -> int:
        """Export prospects to CSV"""
        prospects = self.list_prospects(icp_filter=icp_filter)
        if not prospects:
            return 0

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=prospects[0].to_dict().keys())
            writer.writeheader()

            for prospect in prospects:
                writer.writerow(prospect.to_dict())

        logger.info(f"Exported {len(prospects)} prospects to {output_file}")
        return len(prospects)

    def _csv_row_to_prospect(self, row: Dict[str, Any]) -> ProspectData:
        """Convert CSV row to ProspectData object"""
        # Handle topics
        topics = []
        if row.get('topics'):
            topics = [t.strip() for t in row['topics'].split(',') if t.strip()]

        # Handle timestamps
        created_at = updated_at = datetime.now()
        if row.get('signal_at'):
            try:
                # Parse GitHub timestamp format
                created_at = datetime.fromisoformat(row['signal_at'].replace('Z', '+00:00'))
            except:
                pass

        return ProspectData(
            lead_id=row['lead_id'],
            login=row['login'],
            name=row.get('name'),
            company=row.get('company'),
            email_public_commit=row.get('email_public_commit'),
            email_profile=row.get('email_profile'),
            location=row.get('location'),
            bio=row.get('bio'),
            pronouns=row.get('pronouns'),
            repo_full_name=row.get('repo_full_name'),
            repo_description=row.get('repo_description'),
            signal=row.get('signal'),
            signal_type=row.get('signal_type'),
            topics=topics,
            language=row.get('language'),
            stars=int(row['stars']) if row.get('stars') else None,
            forks=int(row['forks']) if row.get('forks') else None,
            watchers=int(row['watchers']) if row.get('watchers') else None,
            followers=int(row['followers']) if row.get('followers') else None,
            public_repos=int(row['public_repos']) if row.get('public_repos') else None,
            contributions_last_year=int(row['contributions_last_year']) if row.get('contributions_last_year') else None,
            linkedin_username=row.get('linkedin_username'),
            blog=row.get('blog'),
            hireable=row.get('hireable', '').lower() in ('true', '1', 'yes'),
            created_at=created_at,
            updated_at=updated_at
        )
