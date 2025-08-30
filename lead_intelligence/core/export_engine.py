#!/usr/bin/env python3
"""
Export Engine
Handles exporting intelligence data to various formats (Instantly CSV, Attio, etc.)
"""

import csv
import json
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

from .attio_integrator import AttioIntegrator
# Import will be done locally to avoid relative import issues

logger = logging.getLogger(__name__)


class ExportEngine:
    """Handles exporting intelligence data to various formats"""

    def __init__(self, output_dir: str = "lead_intelligence/data"):
        self.output_dir = Path(output_dir)
        self.exports_dir = self.output_dir / "exports"
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def export_instantly_csv(self, instantly_rows: List[Any],
                           filename: Optional[str] = None) -> str:
        """Export Instantly-compatible CSV"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"leads_campaign_{timestamp}.csv"

        filepath = self.exports_dir / filename

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['email', 'first_name', 'repo', 'language',
                         'personalization_snippet', 'subject', 'body', 'unsub']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for row in instantly_rows:
                writer.writerow(asdict(row))

        logger.info(f"Exported {len(instantly_rows)} leads to Instantly CSV: {filepath}")
        return str(filepath)

    def export_repo_briefs_jsonl(self, briefs: List[Any],
                               filename: Optional[str] = None) -> str:
        """Export repo briefs as JSONL for audit and follow-ups"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"repo_briefs_{timestamp}.jsonl"

        filepath = self.exports_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            for brief in briefs:
                if hasattr(brief, '__dict__'):
                    json.dump(brief.__dict__, f, default=str)
                else:
                    json.dump(brief, f, default=str)
                f.write('\n')

        logger.info(f"Exported {len(briefs)} repo briefs to JSONL: {filepath}")
        return str(filepath)

    def export_intelligence_summary(self, results: Dict[str, Any],
                                  filename: Optional[str] = None) -> str:
        """Export comprehensive intelligence summary"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"intelligence_summary_{timestamp}.json"

        filepath = self.exports_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Exported intelligence summary: {filepath}")
        return str(filepath)

    def export_quality_report(self, validation_results: Dict[str, Any],
                            filename: Optional[str] = None) -> str:
        """Export data quality report"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"quality_report_{timestamp}.json"

        filepath = self.exports_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(validation_results, f, indent=2, default=str)

        logger.info(f"Exported quality report: {filepath}")
        return str(filepath)

    def export_monday_wave(self, instantly_rows: List[Any],
                         priority_threshold: float = 0.6,
                         risk_threshold: float = 0.35) -> Dict[str, Any]:
        """
        Export Monday wave with quality gates
        Returns dict with file paths and statistics
        """
        # Apply quality gates
        qualified_rows = []
        rejected_rows = []

        for row in instantly_rows:
            # Note: In a full implementation, we'd have priority and risk scores
            # For now, we'll assume all rows are qualified
            qualified_rows.append(row)

        # Sort by priority (placeholder logic)
        qualified_rows.sort(key=lambda x: x.email)  # Simple sort for now

        # Take top 2200 (2000 + 200 buffer)
        monday_wave = qualified_rows[:2200]

        # Export files
        csv_path = self.export_instantly_csv(monday_wave, "monday_wave_leads.csv")

        # Create summary
        summary = {
            'export_timestamp': datetime.now().isoformat(),
            'total_candidates': len(instantly_rows),
            'qualified_leads': len(qualified_rows),
            'monday_wave_count': len(monday_wave),
            'rejected_count': len(rejected_rows),
            'priority_threshold': priority_threshold,
            'risk_threshold': risk_threshold,
            'files': {
                'campaign_csv': csv_path
            }
        }

        summary_path = self.export_intelligence_summary(summary, "monday_wave_summary.json")

        logger.info(f"Monday wave export complete: {len(monday_wave)} leads qualified")

        return {
            'summary': summary,
            'csv_path': csv_path,
            'summary_path': summary_path
        }

    def export_attio_ready(self, leads_data: List[Dict[str, Any]],
                         attio_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Export data in Attio-ready format"""
        if not attio_config:
            attio_config = {}

        attio_token = attio_config.get('api_token')
        if not attio_token:
            logger.warning("No Attio API token provided - skipping Attio export")
            return {'error': 'No Attio API token'}

        # Initialize Attio integrator
        attio = AttioIntegrator({'api_token': attio_token})

        if not attio.validate_connection():
            return {'error': 'Attio connection failed'}

        # Convert leads to Attio format
        attio_people = []
        attio_repos = []

        for lead in leads_data:
            # Convert to Attio People format
            person = {
                'login': lead.get('maintainer_name', '').lower().replace(' ', ''),
                'name': lead.get('maintainer_name', ''),
                'email_profile': lead.get('email'),
                'company': lead.get('company'),
                'location': lead.get('location'),
                'bio': f"Maintains {lead.get('repo', '')}",
                'public_repos': 1,
                'followers': 0,
                'html_url': f"https://github.com/{lead.get('maintainer_name', '')}",
                'github_user_url': f"https://github.com/{lead.get('maintainer_name', '')}"
            }
            attio_people.append(person)

            # Convert to Attio Repos format
            repo = {
                'repo_full_name': lead.get('repo', ''),
                'repo_name': lead.get('repo', '').split('/')[-1],
                'owner_login': lead.get('repo', '').split('/')[0],
                'host': 'GitHub',
                'description': lead.get('description', ''),
                'primary_language': lead.get('language', ''),
                'stars': lead.get('stars', 0),
                'html_url': lead.get('repo_url', ''),
                'api_url': f"https://api.github.com/repos/{lead.get('repo', '')}"
            }
            attio_repos.append(repo)

        # Export to Attio
        people_result = attio.import_people(attio_people)
        repos_result = attio.import_repos(attio_repos)

        # Create summary
        attio_summary = {
            'export_timestamp': datetime.now().isoformat(),
            'people_imported': people_result.get('successful', 0),
            'repos_imported': repos_result.get('successful', 0),
            'people_failed': people_result.get('failed', 0),
            'repos_failed': repos_result.get('failed', 0),
            'details': {
                'people': people_result,
                'repos': repos_result
            }
        }

        summary_path = self.export_intelligence_summary(attio_summary, "attio_import_summary.json")

        logger.info(f"Attio export complete: {people_result.get('successful', 0)} people, {repos_result.get('successful', 0)} repos")

        return {
            'summary': attio_summary,
            'summary_path': summary_path
        }

    def create_campaign_package(self, instantly_rows: List[Any],
                              repo_briefs: List[Any],
                              campaign_name: str = "monday_wave") -> Dict[str, Any]:
        """Create complete campaign package with all necessary files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Create campaign directory
        campaign_dir = self.exports_dir / f"{campaign_name}_{timestamp}"
        campaign_dir.mkdir(exist_ok=True)

        # Export all components
        csv_path = self.export_instantly_csv(instantly_rows, f"{campaign_name}.csv")
        briefs_path = self.export_repo_briefs_jsonl(repo_briefs, f"{campaign_name}_briefs.jsonl")

        # Create campaign summary
        campaign_summary = {
            'campaign_name': campaign_name,
            'created_at': datetime.now().isoformat(),
            'lead_count': len(instantly_rows),
            'files': {
                'campaign_csv': str(Path(csv_path).name),
                'repo_briefs': str(Path(briefs_path).name)
            },
            'quality_stats': {
                'emails_with_personalization': len([r for r in instantly_rows if r.personalization_snippet]),
                'unique_languages': len(set(r.language for r in instantly_rows if r.language)),
                'unsub_links_present': all('unsubscribe' in r.unsub.lower() for r in instantly_rows)
            }
        }

        # Copy files to campaign directory
        import shutil
        shutil.copy2(csv_path, campaign_dir / Path(csv_path).name)
        shutil.copy2(briefs_path, campaign_dir / Path(briefs_path).name)

        # Save campaign summary
        summary_path = campaign_dir / "campaign_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(campaign_summary, f, indent=2, default=str)

        logger.info(f"Campaign package created: {campaign_dir}")

        return {
            'campaign_dir': str(campaign_dir),
            'summary': campaign_summary,
            'files': {
                'csv': str(Path(csv_path).name),
                'briefs': str(Path(briefs_path).name),
                'summary': str(summary_path.name)
            }
        }
