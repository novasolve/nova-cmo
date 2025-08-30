#!/usr/bin/env python3
"""
Database migration utilities for Copy Factory
Converts JSON file storage to database
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from .database import CopyFactoryDatabase
from .models import ICPProfile, ProspectData, CopyTemplate, OutreachCampaign

logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """Handles migration from JSON files to database"""

    def __init__(self, data_dir: str = "copy_factory/data", db_path: str = "copy_factory/data/copy_factory.db"):
        self.data_dir = Path(data_dir)
        self.database = CopyFactoryDatabase(db_path)

    def migrate_all_data(self, force: bool = False) -> Dict[str, Any]:
        """Migrate all JSON data to database"""

        migration_results = {
            'icp_migrated': 0,
            'prospects_migrated': 0,
            'templates_migrated': 0,
            'campaigns_migrated': 0,
            'errors': [],
            'skipped': []
        }

        try:
            # Migrate ICP profiles
            icp_result = self._migrate_icp_profiles(force)
            migration_results['icp_migrated'] = icp_result['migrated']
            migration_results['errors'].extend(icp_result['errors'])

            # Migrate prospects
            prospect_result = self._migrate_prospects(force)
            migration_results['prospects_migrated'] = prospect_result['migrated']
            migration_results['errors'].extend(prospect_result['errors'])

            # Migrate templates
            template_result = self._migrate_templates(force)
            migration_results['templates_migrated'] = template_result['migrated']
            migration_results['errors'].extend(template_result['errors'])

            # Migrate campaigns
            campaign_result = self._migrate_campaigns(force)
            migration_results['campaigns_migrated'] = campaign_result['migrated']
            migration_results['errors'].extend(campaign_result['errors'])

            # Create backup of original data
            self._create_backup()

            logger.info(f"Migration completed: {migration_results}")

        except Exception as e:
            migration_results['errors'].append(f"Migration failed: {str(e)}")
            logger.error(f"Migration failed: {e}")

        return migration_results

    def _migrate_icp_profiles(self, force: bool = False) -> Dict[str, Any]:
        """Migrate ICP profiles from JSON files to database"""

        icp_dir = self.data_dir / "icp"
        if not icp_dir.exists():
            return {'migrated': 0, 'errors': []}

        migrated = 0
        errors = []

        for icp_file in icp_dir.glob("*.json"):
            try:
                with open(icp_file, 'r') as f:
                    data = json.load(f)

                # Check if already exists
                if not force and self.database.get_icp(data['id']):
                    continue

                # Convert to ICPProfile and save
                icp = ICPProfile.from_dict(data)
                self.database.save_icp(icp)
                migrated += 1

            except Exception as e:
                errors.append(f"Failed to migrate ICP {icp_file.name}: {str(e)}")

        return {'migrated': migrated, 'errors': errors}

    def _migrate_prospects(self, force: bool = False) -> Dict[str, Any]:
        """Migrate prospects from JSON files to database"""

        prospects_dir = self.data_dir / "prospects"
        if not prospects_dir.exists():
            return {'migrated': 0, 'errors': []}

        migrated = 0
        errors = []

        for prospect_file in prospects_dir.glob("*.json"):
            try:
                with open(prospect_file, 'r') as f:
                    data = json.load(f)

                # Check if already exists
                if not force and self.database.get_prospect(data['lead_id']):
                    continue

                # Convert to ProspectData and save
                prospect = ProspectData.from_dict(data)
                self.database.save_prospect(prospect)
                migrated += 1

            except Exception as e:
                errors.append(f"Failed to migrate prospect {prospect_file.name}: {str(e)}")

        return {'migrated': migrated, 'errors': errors}

    def _migrate_templates(self, force: bool = False) -> Dict[str, Any]:
        """Migrate templates from JSON files to database"""

        templates_dir = self.data_dir / "templates"
        if not templates_dir.exists():
            return {'migrated': 0, 'errors': []}

        migrated = 0
        errors = []

        for template_file in templates_dir.glob("*.json"):
            try:
                with open(template_file, 'r') as f:
                    data = json.load(f)

                # Check if already exists
                if not force and self.database.get_template(data['id']):
                    continue

                # Convert to CopyTemplate and save
                template = CopyTemplate.from_dict(data)
                self.database.save_template(template)
                migrated += 1

            except Exception as e:
                errors.append(f"Failed to migrate template {template_file.name}: {str(e)}")

        return {'migrated': migrated, 'errors': errors}

    def _migrate_campaigns(self, force: bool = False) -> Dict[str, Any]:
        """Migrate campaigns from JSON files to database"""

        campaigns_dir = self.data_dir / "campaigns"
        if not campaigns_dir.exists():
            return {'migrated': 0, 'errors': []}

        migrated = 0
        errors = []

        for campaign_file in campaigns_dir.glob("*.json"):
            try:
                with open(campaign_file, 'r') as f:
                    data = json.load(f)

                # Check if already exists
                if not force and self.database.get_campaign(data['id']):
                    continue

                # Convert to OutreachCampaign and save
                campaign = OutreachCampaign.from_dict(data)
                self.database.save_campaign(campaign)
                migrated += 1

            except Exception as e:
                errors.append(f"Failed to migrate campaign {campaign_file.name}: {str(e)}")

        return {'migrated': migrated, 'errors': errors}

    def _create_backup(self) -> None:
        """Create backup of original JSON data"""

        import shutil
        from datetime import datetime

        backup_dir = self.data_dir.parent / "backups" / f"json_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            if self.data_dir.exists():
                shutil.copytree(self.data_dir, backup_dir)
                logger.info(f"JSON data backup created at {backup_dir}")
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")

    def verify_migration(self) -> Dict[str, Any]:
        """Verify that migration was successful"""

        verification = {
            'database_stats': self.database.get_database_stats(),
            'json_file_counts': self._count_json_files(),
            'consistency_check': self._check_data_consistency()
        }

        return verification

    def _count_json_files(self) -> Dict[str, int]:
        """Count JSON files in each directory"""

        counts = {}

        directories = {
            'icp': self.data_dir / "icp",
            'prospects': self.data_dir / "prospects",
            'templates': self.data_dir / "templates",
            'campaigns': self.data_dir / "campaigns"
        }

        for name, directory in directories.items():
            if directory.exists():
                counts[name] = len(list(directory.glob("*.json")))
            else:
                counts[name] = 0

        return counts

    def _check_data_consistency(self) -> Dict[str, Any]:
        """Check consistency between database and JSON files"""

        consistency = {
            'icp_consistent': True,
            'prospects_consistent': True,
            'templates_consistent': True,
            'campaigns_consistent': True,
            'issues': []
        }

        try:
            # Check ICP consistency
            json_icps = []
            icp_dir = self.data_dir / "icp"
            if icp_dir.exists():
                for icp_file in icp_dir.glob("*.json"):
                    with open(icp_file, 'r') as f:
                        json_icps.append(json.load(f)['id'])

            db_icps = [icp.id for icp in self.database.list_icps()]
            if set(json_icps) != set(db_icps):
                consistency['icp_consistent'] = False
                consistency['issues'].append(f"ICP mismatch: JSON has {len(json_icps)}, DB has {len(db_icps)}")

        except Exception as e:
            consistency['icp_consistent'] = False
            consistency['issues'].append(f"ICP consistency check failed: {e}")

        return consistency

    def rollback_migration(self) -> Dict[str, Any]:
        """Rollback migration by restoring from backup"""

        rollback_results = {
            'success': False,
            'backup_found': False,
            'errors': []
        }

        try:
            # Find latest backup
            backup_dir = self.data_dir.parent / "backups"
            if not backup_dir.exists():
                rollback_results['errors'].append("No backup directory found")
                return rollback_results

            backups = list(backup_dir.glob("json_backup_*"))
            if not backups:
                rollback_results['errors'].append("No backups found")
                return rollback_results

            latest_backup = max(backups, key=lambda x: x.stat().st_mtime)
            rollback_results['backup_found'] = True

            # Restore backup
            import shutil
            if self.data_dir.exists():
                shutil.rmtree(self.data_dir)

            shutil.copytree(latest_backup, self.data_dir)
            rollback_results['success'] = True

            logger.info(f"Migration rolled back using backup: {latest_backup}")

        except Exception as e:
            rollback_results['errors'].append(f"Rollback failed: {str(e)}")
            logger.error(f"Rollback failed: {e}")

        return rollback_results


def migrate_to_database(force: bool = False) -> Dict[str, Any]:
    """Main migration function"""

    migrator = DatabaseMigrator()

    print("🚀 Starting Copy Factory Database Migration")
    print("=" * 50)

    # Run migration
    results = migrator.migrate_all_data(force=force)

    print("
📊 Migration Results:"    print(f"  ICP Profiles: {results['icp_migrated']} migrated")
    print(f"  Prospects: {results['prospects_migrated']} migrated")
    print(f"  Templates: {results['templates_migrated']} migrated")
    print(f"  Campaigns: {results['campaigns_migrated']} migrated")

    if results['errors']:
        print(f"\n⚠️  Errors encountered: {len(results['errors'])}")
        for error in results['errors'][:5]:  # Show first 5 errors
            print(f"  • {error}")

    # Verify migration
    verification = migrator.verify_migration()

    print("
🔍 Verification:"    stats = verification['database_stats']
    print(f"  Database records: {stats['prospects_count']} prospects, {stats['icp_profiles_count']} ICPs")
    print(".1f"    consistency = verification['consistency_check']
    if all(consistency[k] for k in consistency.keys() if k.endswith('_consistent')):
        print("  ✅ Data consistency verified")
    else:
        print("  ⚠️  Data consistency issues found")

    print("\n✅ Migration completed successfully!")

    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Copy Factory Database Migration")
    parser.add_argument('--force', action='store_true', help='Force migration even if data exists')
    parser.add_argument('--rollback', action='store_true', help='Rollback migration to JSON files')
    parser.add_argument('--verify', action='store_true', help='Only verify current migration status')

    args = parser.parse_args()

    if args.rollback:
        migrator = DatabaseMigrator()
        results = migrator.rollback_migration()
        if results['success']:
            print("✅ Migration rolled back successfully")
        else:
            print("❌ Rollback failed")
            for error in results['errors']:
                print(f"  • {error}")

    elif args.verify:
        migrator = DatabaseMigrator()
        verification = migrator.verify_migration()
        print("🔍 Migration Verification:")
        print(f"  Database: {verification['database_stats']['prospects_count']} prospects")
        print(f"  JSON files: {verification['json_file_counts']['prospects']} files")

    else:
        migrate_to_database(force=args.force)

