#!/usr/bin/env python3
"""
Integration between Copy Factory and Lead Intelligence Engine
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import logging

# Add parent directory to path to import existing modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from copy_factory.core.factory import CopyFactory
from copy_factory.core.models import ProspectData
from lead_intelligence.core.intelligence_engine import LeadIntelligence

logger = logging.getLogger(__name__)


class CopyFactoryIntegration:
    """Integration layer between Copy Factory and Intelligence Engine"""

    def __init__(self, copy_factory_data_dir: str = "copy_factory/data"):
        self.copy_factory = CopyFactory(copy_factory_data_dir)
        self.logger = logger

    def sync_intelligence_to_copy_factory(self, intelligence_results: List[LeadIntelligence]) -> Dict[str, int]:
        """Sync intelligence engine results to Copy Factory"""

        synced_prospects = 0
        synced_icps = 0

        # First, ensure we have ICP profiles from intelligence data
        icp_ids = set()
        for result in intelligence_results:
            # Extract ICP matches from enrichment data
            if result.enrichment_data.get('icp_matches'):
                icp_ids.update(result.enrichment_data['icp_matches'])

        # Create basic ICP profiles if they don't exist
        for icp_id in icp_ids:
            if not self.copy_factory.storage.get_icp(icp_id):
                # Create a basic ICP profile
                icp = self._create_icp_from_intelligence(icp_id, intelligence_results)
                if icp:
                    self.copy_factory.storage.save_icp(icp)
                    synced_icps += 1

        # Sync prospect data
        for result in intelligence_results:
            try:
                prospect = self._convert_intelligence_to_prospect(result)
                self.copy_factory.storage.save_prospect(prospect)
                synced_prospects += 1
            except Exception as e:
                self.logger.error(f"Error syncing prospect {result.prospect.login}: {e}")

        # Update prospect-ICP matches
        matches = self.copy_factory.match_prospects_to_icps()

        self.logger.info(f"Synced {synced_prospects} prospects and {synced_icps} ICPs from intelligence engine")

        return {
            'synced_prospects': synced_prospects,
            'synced_icps': synced_icps,
            'updated_matches': len(matches)
        }

    def _convert_intelligence_to_prospect(self, intelligence: LeadIntelligence) -> ProspectData:
        """Convert LeadIntelligence to ProspectData"""

        prospect = intelligence.prospect

        # Create prospect data with intelligence enrichment
        prospect_data = ProspectData(
            lead_id=prospect.lead_id or f"intel_{prospect.login}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            login=prospect.login,
            name=prospect.name,
            company=prospect.company,
            email_public_commit=prospect.email_public_commit,
            email_profile=prospect.email_profile,
            location=prospect.location,
            bio=prospect.bio,
            pronouns=prospect.pronouns,
            repo_full_name=prospect.repo_full_name,
            repo_description=prospect.repo_description,
            signal=prospect.signal,
            signal_type=prospect.signal_type,
            topics=prospect.topics if hasattr(prospect, 'topics') else [],
            language=prospect.language,
            stars=prospect.stars,
            forks=prospect.forks,
            watchers=prospect.watchers,
            followers=prospect.followers,
            public_repos=prospect.public_repos,
            contributions_last_year=prospect.contributions_last_year,
            linkedin_username=getattr(prospect, 'linkedin_username', None),
            blog=prospect.blog,
            hireable=getattr(prospect, 'hireable', False),
            intelligence_score=intelligence.intelligence_score,
            engagement_potential=intelligence.engagement_potential,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # Add ICP matches from intelligence data
        if intelligence.enrichment_data.get('icp_matches'):
            prospect_data.icp_matches = intelligence.enrichment_data['icp_matches']

        return prospect_data

    def _create_icp_from_intelligence(self, icp_id: str, intelligence_results: List[LeadIntelligence]) -> Optional[Any]:
        """Create ICP profile from intelligence data patterns"""

        # Find prospects with this ICP match
        matching_prospects = []
        for result in intelligence_results:
            if result.enrichment_data.get('icp_matches') and icp_id in result.enrichment_data['icp_matches']:
                matching_prospects.append(result.prospect)

        if not matching_prospects:
            return None

        # Infer ICP characteristics from matching prospects
        languages = set()
        companies = set()
        locations = set()

        for prospect in matching_prospects:
            if prospect.language:
                languages.add(prospect.language)
            if prospect.company:
                companies.add(prospect.company)
            if prospect.location:
                locations.add(prospect.location)

        # Create basic ICP profile
        from copy_factory.core.models import ICPProfile

        icp = ICPProfile(
            id=icp_id,
            name=f"Inferred ICP: {icp_id}",
            description=f"Automatically inferred ICP profile from {len(matching_prospects)} prospects",
            technographics={
                'language': list(languages) if languages else ['Unknown'],
                'frameworks': []  # Could be inferred from topics/repo analysis
            },
            firmographics={
                'size': 'Unknown',  # Could be inferred from company analysis
                'geo': list(locations)[:5] if locations else ['Global']  # Limit to top 5
            },
            triggers=[
                f"Matches {len(matching_prospects)} identified prospects",
                "Based on intelligence engine analysis"
            ],
            github_queries=[],  # Would need to be manually added
            outreach_sequence_tag=f"auto_{icp_id}"
        )

        return icp

    def create_campaign_from_intelligence_segment(self, segment_name: str,
                                                 intelligence_results: List[LeadIntelligence],
                                                 min_score: float = 3.0) -> Optional[str]:
        """Create a Copy Factory campaign from intelligence results"""

        # Filter high-quality prospects
        high_quality_prospects = [
            result for result in intelligence_results
            if result.intelligence_score >= min_score
        ]

        if not high_quality_prospects:
            self.logger.warning(f"No prospects meet minimum score of {min_score}")
            return None

        # Find common ICP patterns
        icp_counts = {}
        for result in high_quality_prospects:
            if result.enrichment_data.get('icp_matches'):
                for icp_id in result.enrichment_data['icp_matches']:
                    icp_counts[icp_id] = icp_counts.get(icp_id, 0) + 1

        if not icp_counts:
            self.logger.warning("No ICP matches found in intelligence results")
            return None

        # Use most common ICP
        primary_icp = max(icp_counts.items(), key=lambda x: x[1])[0]

        # Sync data first
        self.sync_intelligence_to_copy_factory(high_quality_prospects)

        # Create template if it doesn't exist
        icp = self.copy_factory.storage.get_icp(primary_icp)
        if icp:
            template_id = f"{primary_icp}_email_template"
            if not self.copy_factory.storage.get_template(template_id):
                template = self.copy_factory.create_icp_template(icp, "email")
                template_id = template.id

            # Create campaign
            campaign = self.copy_factory.create_campaign(
                name=f"{segment_name} - {icp.name}",
                icp_id=primary_icp,
                template_id=template_id
            )

            self.logger.info(f"Created campaign '{campaign.name}' with {len(campaign.prospect_ids)} prospects")
            return campaign.id

        return None

    def export_intelligence_campaign_copy(self, intelligence_results: List[LeadIntelligence],
                                         output_file: str, min_score: float = 3.0) -> int:
        """Export generated copy for intelligence results"""

        # Create temporary campaign
        campaign_id = self.create_campaign_from_intelligence_segment(
            "Intelligence Export",
            intelligence_results,
            min_score
        )

        if not campaign_id:
            return 0

        # Generate and export copy
        exported = self.copy_factory.export_campaign_data(campaign_id, output_file)

        # Clean up temporary campaign
        self.copy_factory.storage.delete_campaign(campaign_id)

        return exported

    def get_copy_factory_stats_from_intelligence(self, intelligence_results: List[LeadIntelligence]) -> Dict[str, Any]:
        """Get Copy Factory-style statistics from intelligence results"""

        total_prospects = len(intelligence_results)
        prospects_with_emails = len([r for r in intelligence_results if r.prospect.has_email()])
        high_potential = len([r for r in intelligence_results if r.engagement_potential == 'high'])
        avg_score = sum(r.intelligence_score for r in intelligence_results) / total_prospects if total_prospects > 0 else 0

        # ICP distribution
        icp_distribution = {}
        for result in intelligence_results:
            if result.enrichment_data.get('icp_matches'):
                for icp_id in result.enrichment_data['icp_matches']:
                    icp_distribution[icp_id] = icp_distribution.get(icp_id, 0) + 1

        return {
            'total_prospects': total_prospects,
            'prospects_with_emails': prospects_with_emails,
            'email_coverage_rate': prospects_with_emails / total_prospects if total_prospects > 0 else 0,
            'high_potential_count': high_potential,
            'average_intelligence_score': round(avg_score, 2),
            'icp_distribution': icp_distribution,
            'top_icps': sorted(icp_distribution.items(), key=lambda x: x[1], reverse=True)[:5]
        }


def main():
    """Command-line integration utility"""
    import argparse

    parser = argparse.ArgumentParser(description="Copy Factory - Intelligence Engine Integration")
    parser.add_argument('--sync-results', help='Sync intelligence results JSON file')
    parser.add_argument('--create-campaign', help='Create campaign from intelligence results')
    parser.add_argument('--export-copy', help='Export generated copy to CSV')
    parser.add_argument('--min-score', type=float, default=3.0, help='Minimum intelligence score')
    parser.add_argument('--data-dir', default='copy_factory/data', help='Copy Factory data directory')

    args = parser.parse_args()

    if not any([args.sync_results, args.create_campaign, args.export_copy]):
        parser.print_help()
        return

    integration = CopyFactoryIntegration(args.data_dir)

    try:
        if args.sync_results:
            # Load intelligence results
            import json
            with open(args.sync_results, 'r') as f:
                # This would need to be adapted based on actual intelligence results format
                results_data = json.load(f)

            # Convert to LeadIntelligence objects (simplified)
            intelligence_results = []
            for item in results_data:
                # This is a placeholder - actual conversion would depend on the format
                pass

            stats = integration.sync_intelligence_to_copy_factory(intelligence_results)
            print(f"✅ Synced {stats['synced_prospects']} prospects and {stats['synced_icps']} ICPs")

        elif args.create_campaign:
            # Similar logic for creating campaigns
            print("Campaign creation from intelligence results would be implemented here")

        elif args.export_copy:
            # Similar logic for exporting copy
            print("Copy export from intelligence results would be implemented here")

    except Exception as e:
        print(f"❌ Integration failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

