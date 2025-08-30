#!/usr/bin/env python3
"""
Database system for Copy Factory - SQLite backend
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import asdict

from .models import ICPProfile, ProspectData, CopyTemplate, OutreachCampaign

logger = logging.getLogger(__name__)


class CopyFactoryDatabase:
    """SQLite database backend for Copy Factory"""

    def __init__(self, db_path: str = "copy_factory/data/copy_factory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = None
        self._ensure_database()

    def _ensure_database(self):
        """Ensure database and tables exist"""
        self._connect()
        self._create_tables()
        self._create_indexes()
        self._run_migrations()

    def _connect(self):
        """Connect to SQLite database"""
        self.connection = sqlite3.connect(str(self.db_path))
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA synchronous = NORMAL")
        self.connection.execute("PRAGMA cache_size = 1000000")  # 1GB cache

    def _create_tables(self):
        """Create all necessary tables"""

        # ICP Profiles table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS icp_profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                personas TEXT,  -- JSON
                firmographics TEXT,  -- JSON
                technographics TEXT,  -- JSON
                triggers TEXT,  -- JSON
                disqualifiers TEXT,  -- JSON
                github_queries TEXT,  -- JSON
                outreach_sequence_tag TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Prospects table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS prospects (
                lead_id TEXT PRIMARY KEY,
                login TEXT NOT NULL,
                name TEXT,
                company TEXT,
                email_public_commit TEXT,
                email_profile TEXT,
                location TEXT,
                bio TEXT,
                pronouns TEXT,
                repo_full_name TEXT,
                repo_description TEXT,
                signal TEXT,
                signal_type TEXT,
                topics TEXT,  -- JSON
                language TEXT,
                stars INTEGER,
                forks INTEGER,
                watchers INTEGER,
                followers INTEGER,
                public_repos INTEGER,
                contributions_last_year INTEGER,
                linkedin_username TEXT,
                blog TEXT,
                hireable BOOLEAN DEFAULT 0,
                icp_matches TEXT,  -- JSON
                intelligence_score REAL DEFAULT 0.0,
                engagement_potential TEXT DEFAULT 'low',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Copy Templates table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS copy_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icp_id TEXT,
                template_type TEXT NOT NULL,
                subject_template TEXT,
                body_template TEXT NOT NULL,
                variables TEXT,  -- JSON
                tags TEXT,  -- JSON
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (icp_id) REFERENCES icp_profiles(id)
            )
        """)

        # Outreach Campaigns table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS outreach_campaigns (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icp_id TEXT,
                template_id TEXT,
                prospect_ids TEXT,  -- JSON
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (icp_id) REFERENCES icp_profiles(id),
                FOREIGN KEY (template_id) REFERENCES copy_templates(id)
            )
        """)

        # Performance Tracking table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS performance_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT,
                emails_sent INTEGER DEFAULT 0,
                opens INTEGER DEFAULT 0,
                responses INTEGER DEFAULT 0,
                conversions INTEGER DEFAULT 0,
                bounce_rate REAL DEFAULT 0.0,
                strategy TEXT,
                performance_date DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES outreach_campaigns(id)
            )
        """)

        # AI Insights table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS ai_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id TEXT,
                insight_type TEXT,
                insights_data TEXT,  -- JSON
                confidence_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (prospect_id) REFERENCES prospects(lead_id)
            )
        """)

        # Embeddings cache table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS embeddings_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE,
                content_type TEXT,
                embedding TEXT,  -- JSON array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Copy cache table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS copy_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE,
                prospect_id TEXT,
                icp_id TEXT,
                subject TEXT,
                body TEXT,
                tone TEXT,
                quality_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (prospect_id) REFERENCES prospects(lead_id),
                FOREIGN KEY (icp_id) REFERENCES icp_profiles(id)
            )
        """)

        self.connection.commit()

    def _create_indexes(self):
        """Create database indexes for performance"""

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_prospects_login ON prospects(login)",
            "CREATE INDEX IF NOT EXISTS idx_prospects_company ON prospects(company)",
            "CREATE INDEX IF NOT EXISTS idx_prospects_language ON prospects(language)",
            "CREATE INDEX IF NOT EXISTS idx_prospects_icp_score ON prospects(intelligence_score)",
            "CREATE INDEX IF NOT EXISTS idx_templates_icp ON copy_templates(icp_id)",
            "CREATE INDEX IF NOT EXISTS idx_templates_type ON copy_templates(template_type)",
            "CREATE INDEX IF NOT EXISTS idx_campaigns_icp ON outreach_campaigns(icp_id)",
            "CREATE INDEX IF NOT EXISTS idx_campaigns_status ON outreach_campaigns(status)",
            "CREATE INDEX IF NOT EXISTS idx_performance_campaign ON performance_data(campaign_id)",
            "CREATE INDEX IF NOT EXISTS idx_performance_date ON performance_data(performance_date)",
            "CREATE INDEX IF NOT EXISTS idx_insights_prospect ON ai_insights(prospect_id)",
            "CREATE INDEX IF NOT EXISTS idx_insights_type ON ai_insights(insight_type)",
            "CREATE INDEX IF NOT EXISTS idx_embeddings_hash ON embeddings_cache(content_hash)",
            "CREATE INDEX IF NOT EXISTS idx_copy_cache_key ON copy_cache(cache_key)",
            "CREATE INDEX IF NOT EXISTS idx_copy_prospect_icp ON copy_cache(prospect_id, icp_id)"
        ]

        for index_sql in indexes:
            try:
                self.connection.execute(index_sql)
            except Exception as e:
                logger.warning(f"Could not create index: {e}")

        self.connection.commit()

    def _run_migrations(self):
        """Run database migrations"""
        # Check current schema version
        cursor = self.connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("SELECT MAX(version) FROM schema_version")
        current_version = cursor.fetchone()[0] or 0

        # Apply migrations based on current version
        migrations = [
            (1, self._migration_v1_add_performance_metrics),
            (2, self._migration_v2_add_ai_insights_table),
            (3, self._migration_v3_add_embeddings_cache),
            (4, self._migration_v4_add_copy_cache),
            (5, self._migration_v5_add_campaign_metadata)
        ]

        for version, migration_func in migrations:
            if current_version < version:
                try:
                    logger.info(f"Running migration v{version}")
                    migration_func()
                    cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                    current_version = version
                except Exception as e:
                    logger.error(f"Migration v{version} failed: {e}")
                    break

        self.connection.commit()

    def _migration_v1_add_performance_metrics(self):
        """Add performance metrics columns"""
        self.connection.execute("""
            ALTER TABLE performance_data
            ADD COLUMN click_rate REAL DEFAULT 0.0
        """)

    def _migration_v2_add_ai_insights_table(self):
        """Add AI insights table (already created in _create_tables)"""
        pass

    def _migration_v3_add_embeddings_cache(self):
        """Add embeddings cache table (already created in _create_tables)"""
        pass

    def _migration_v4_add_copy_cache(self):
        """Add copy cache table (already created in _create_tables)"""
        pass

    def _migration_v5_add_campaign_metadata(self):
        """Add campaign metadata columns"""
        self.connection.execute("""
            ALTER TABLE outreach_campaigns
            ADD COLUMN metadata TEXT  -- JSON metadata
        """)

    # ICP Management
    def save_icp(self, icp: ICPProfile) -> None:
        """Save ICP profile to database"""
        data = icp.to_dict()
        data['personas'] = json.dumps(data['personas'])
        data['firmographics'] = json.dumps(data['firmographics'])
        data['technographics'] = json.dumps(data['technographics'])
        data['triggers'] = json.dumps(data['triggers'])
        data['disqualifiers'] = json.dumps(data['disqualifiers'])
        data['github_queries'] = json.dumps(data['github_queries'])

        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO icp_profiles
            (id, name, description, personas, firmographics, technographics,
             triggers, disqualifiers, github_queries, outreach_sequence_tag,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['id'], data['name'], data['description'], data['personas'],
            data['firmographics'], data['technographics'], data['triggers'],
            data['disqualifiers'], data['github_queries'], data['outreach_sequence_tag'],
            data['created_at'], data['updated_at']
        ))
        self.connection.commit()

    def get_icp(self, icp_id: str) -> Optional[ICPProfile]:
        """Get ICP profile from database"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM icp_profiles WHERE id = ?", (icp_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # Convert back to ICPProfile
        data = dict(zip([desc[0] for desc in cursor.description], row))
        data['personas'] = json.loads(data['personas'] or '[]')
        data['firmographics'] = json.loads(data['firmographics'] or '{}')
        data['technographics'] = json.loads(data['technographics'] or '{}')
        data['triggers'] = json.loads(data['triggers'] or '[]')
        data['disqualifiers'] = json.loads(data['disqualifiers'] or '[]')
        data['github_queries'] = json.loads(data['github_queries'] or '[]')

        return ICPProfile.from_dict(data)

    def list_icps(self) -> List[ICPProfile]:
        """List all ICP profiles"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM icp_profiles ORDER BY updated_at DESC")
        rows = cursor.fetchall()

        icps = []
        for row in rows:
            data = dict(zip([desc[0] for desc in cursor.description], row))
            data['personas'] = json.loads(data['personas'] or '[]')
            data['firmographics'] = json.loads(data['firmographics'] or '{}')
            data['technographics'] = json.loads(data['technographics'] or '{}')
            data['triggers'] = json.loads(data['triggers'] or '[]')
            data['disqualifiers'] = json.loads(data['disqualifiers'] or '[]')
            data['github_queries'] = json.loads(data['github_queries'] or '[]')
            icps.append(ICPProfile.from_dict(data))

        return icps

    def delete_icp(self, icp_id: str) -> bool:
        """Delete ICP profile"""
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM icp_profiles WHERE id = ?", (icp_id,))
        self.connection.commit()
        return cursor.rowcount > 0

    # Prospect Management
    def save_prospect(self, prospect: ProspectData) -> None:
        """Save prospect to database"""
        data = prospect.to_dict()
        data['topics'] = json.dumps(data['topics'])
        data['icp_matches'] = json.dumps(data['icp_matches'])
        data['hireable'] = 1 if data['hireable'] else 0

        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO prospects
            (lead_id, login, name, company, email_public_commit, email_profile,
             location, bio, pronouns, repo_full_name, repo_description, signal,
             signal_type, topics, language, stars, forks, watchers, followers,
             public_repos, contributions_last_year, linkedin_username, blog,
             hireable, icp_matches, intelligence_score, engagement_potential,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['lead_id'], data['login'], data['name'], data['company'],
            data['email_public_commit'], data['email_profile'], data['location'],
            data['bio'], data['pronouns'], data['repo_full_name'], data['repo_description'],
            data['signal'], data['signal_type'], data['topics'], data['language'],
            data['stars'], data['forks'], data['watchers'], data['followers'],
            data['public_repos'], data['contributions_last_year'], data['linkedin_username'],
            data['blog'], data['hireable'], data['icp_matches'], data['intelligence_score'],
            data['engagement_potential'], data['created_at'], data['updated_at']
        ))
        self.connection.commit()

    def get_prospect(self, lead_id: str) -> Optional[ProspectData]:
        """Get prospect from database"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM prospects WHERE lead_id = ?", (lead_id,))
        row = cursor.fetchone()

        if not row:
            return None

        data = dict(zip([desc[0] for desc in cursor.description], row))
        data['topics'] = json.loads(data['topics'] or '[]')
        data['icp_matches'] = json.loads(data['icp_matches'] or '[]')
        data['hireable'] = bool(data['hireable'])

        return ProspectData.from_dict(data)

    def list_prospects(self, limit: Optional[int] = None, icp_filter: Optional[str] = None,
                      has_email: bool = False, order_by: str = "updated_at DESC") -> List[ProspectData]:
        """List prospects with optional filtering"""
        cursor = self.connection.cursor()

        query = "SELECT * FROM prospects"
        params = []

        conditions = []
        if icp_filter:
            conditions.append("icp_matches LIKE ?")
            params.append(f'%{icp_filter}%')

        if has_email:
            conditions.append("(email_profile IS NOT NULL OR email_public_commit IS NOT NULL)")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY {order_by}"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        prospects = []
        for row in rows:
            data = dict(zip([desc[0] for desc in cursor.description], row))
            data['topics'] = json.loads(data['topics'] or '[]')
            data['icp_matches'] = json.loads(data['icp_matches'] or '[]')
            data['hireable'] = bool(data['hireable'])
            prospects.append(ProspectData.from_dict(data))

        return prospects

    # Template Management
    def save_template(self, template: CopyTemplate) -> None:
        """Save copy template"""
        data = template.to_dict()
        data['variables'] = json.dumps(data['variables'])
        data['tags'] = json.dumps(data['tags'])

        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO copy_templates
            (id, name, icp_id, template_type, subject_template, body_template,
             variables, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['id'], data['name'], data['icp_id'], data['template_type'],
            data['subject_template'], data['body_template'], data['variables'],
            data['tags'], data['created_at'], data['updated_at']
        ))
        self.connection.commit()

    def get_template(self, template_id: str) -> Optional[CopyTemplate]:
        """Get template from database"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM copy_templates WHERE id = ?", (template_id,))
        row = cursor.fetchone()

        if not row:
            return None

        data = dict(zip([desc[0] for desc in cursor.description], row))
        data['variables'] = json.loads(data['variables'] or '[]')
        data['tags'] = json.loads(data['tags'] or '[]')

        return CopyTemplate.from_dict(data)

    def list_templates(self, icp_id: Optional[str] = None, template_type: Optional[str] = None) -> List[CopyTemplate]:
        """List templates with optional filtering"""
        cursor = self.connection.cursor()

        query = "SELECT * FROM copy_templates"
        params = []

        conditions = []
        if icp_id:
            conditions.append("icp_id = ?")
            params.append(icp_id)

        if template_type:
            conditions.append("template_type = ?")
            params.append(template_type)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY updated_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        templates = []
        for row in rows:
            data = dict(zip([desc[0] for desc in cursor.description], row))
            data['variables'] = json.loads(data['variables'] or '[]')
            data['tags'] = json.loads(data['tags'] or '[]')
            templates.append(CopyTemplate.from_dict(data))

        return templates

    # Campaign Management
    def save_campaign(self, campaign: OutreachCampaign) -> None:
        """Save campaign to database"""
        data = campaign.to_dict()
        data['prospect_ids'] = json.dumps(data['prospect_ids'])

        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO outreach_campaigns
            (id, name, icp_id, template_id, prospect_ids, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['id'], data['name'], data['icp_id'], data['template_id'],
            data['prospect_ids'], data['status'], data['created_at'], data['updated_at']
        ))
        self.connection.commit()

    def get_campaign(self, campaign_id: str) -> Optional[OutreachCampaign]:
        """Get campaign from database"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM outreach_campaigns WHERE id = ?", (campaign_id,))
        row = cursor.fetchone()

        if not row:
            return None

        data = dict(zip([desc[0] for desc in cursor.description], row))
        data['prospect_ids'] = json.loads(data['prospect_ids'] or '[]')

        return OutreachCampaign.from_dict(data)

    def list_campaigns(self, status_filter: Optional[str] = None, icp_filter: Optional[str] = None) -> List[OutreachCampaign]:
        """List campaigns with optional filtering"""
        cursor = self.connection.cursor()

        query = "SELECT * FROM outreach_campaigns"
        params = []

        conditions = []
        if status_filter:
            conditions.append("status = ?")
            params.append(status_filter)

        if icp_filter:
            conditions.append("icp_id = ?")
            params.append(icp_filter)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY updated_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        campaigns = []
        for row in rows:
            data = dict(zip([desc[0] for desc in cursor.description], row))
            data['prospect_ids'] = json.loads(data['prospect_ids'] or '[]')
            campaigns.append(OutreachCampaign.from_dict(data))

        return campaigns

    # Performance Tracking
    def save_performance_data(self, performance_data: Dict[str, Any]) -> None:
        """Save performance data"""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO performance_data
            (campaign_id, emails_sent, opens, responses, conversions, bounce_rate, strategy, performance_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            performance_data.get('campaign_id'),
            performance_data.get('emails_sent', 0),
            performance_data.get('opens', 0),
            performance_data.get('responses', 0),
            performance_data.get('conversions', 0),
            performance_data.get('bounce_rate', 0.0),
            performance_data.get('strategy'),
            performance_data.get('performance_date', datetime.now().date())
        ))
        self.connection.commit()

    def get_performance_history(self, campaign_id: Optional[str] = None,
                               days_back: int = 30) -> List[Dict[str, Any]]:
        """Get performance history"""
        cursor = self.connection.cursor()

        query = """
            SELECT * FROM performance_data
            WHERE performance_date >= date('now', '-{} days')
        """.format(days_back)

        params = []
        if campaign_id:
            query += " AND campaign_id = ?"
            params.append(campaign_id)

        query += " ORDER BY performance_date DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        performance_history = []
        for row in rows:
            data = dict(zip([desc[0] for desc in cursor.description], row))
            performance_history.append(data)

        return performance_history

    # AI Insights Storage
    def save_ai_insights(self, prospect_id: str, insight_type: str,
                        insights_data: Dict[str, Any], confidence_score: float = 0.8) -> None:
        """Save AI insights"""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO ai_insights (prospect_id, insight_type, insights_data, confidence_score)
            VALUES (?, ?, ?, ?)
        """, (prospect_id, insight_type, json.dumps(insights_data), confidence_score))
        self.connection.commit()

    def get_ai_insights(self, prospect_id: str, insight_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get AI insights for prospect"""
        cursor = self.connection.cursor()

        query = "SELECT * FROM ai_insights WHERE prospect_id = ?"
        params = [prospect_id]

        if insight_type:
            query += " AND insight_type = ?"
            params.append(insight_type)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        insights = []
        for row in rows:
            data = dict(zip([desc[0] for desc in cursor.description], row))
            data['insights_data'] = json.loads(data['insights_data'])
            insights.append(data)

        return insights

    # Embeddings Cache
    def save_embedding(self, content_hash: str, content_type: str, embedding: List[float]) -> None:
        """Save embedding to cache"""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO embeddings_cache (content_hash, content_type, embedding)
            VALUES (?, ?, ?)
        """, (content_hash, content_type, json.dumps(embedding)))
        self.connection.commit()

    def get_embedding(self, content_hash: str) -> Optional[List[float]]:
        """Get embedding from cache"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT embedding FROM embeddings_cache WHERE content_hash = ?", (content_hash,))
        row = cursor.fetchone()

        if row:
            return json.loads(row[0])
        return None

    # Copy Cache
    def save_cached_copy(self, cache_key: str, prospect_id: str, icp_id: str,
                        subject: str, body: str, tone: str, quality_score: float) -> None:
        """Save cached copy"""
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO copy_cache
            (cache_key, prospect_id, icp_id, subject, body, tone, quality_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cache_key, prospect_id, icp_id, subject, body, tone, quality_score))
        self.connection.commit()

    def get_cached_copy(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached copy"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM copy_cache WHERE cache_key = ?", (cache_key,))
        row = cursor.fetchone()

        if row:
            return dict(zip([desc[0] for desc in cursor.description], row))
        return None

    # Database Maintenance
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        cursor = self.connection.cursor()

        stats = {}

        # Table counts
        tables = ['icp_profiles', 'prospects', 'copy_templates', 'outreach_campaigns',
                 'performance_data', 'ai_insights', 'embeddings_cache', 'copy_cache']

        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[f'{table}_count'] = cursor.fetchone()[0]

        # Database size
        cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        stats['database_size_bytes'] = cursor.fetchone()[0]

        # Recent activity
        cursor.execute("SELECT COUNT(*) FROM prospects WHERE updated_at >= datetime('now', '-1 day')")
        stats['prospects_updated_today'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM ai_insights WHERE created_at >= datetime('now', '-1 day')")
        stats['insights_generated_today'] = cursor.fetchone()[0]

        return stats

    def optimize_database(self) -> None:
        """Optimize database performance"""
        cursor = self.connection.cursor()

        # Vacuum database
        cursor.execute("VACUUM")

        # Rebuild indexes
        cursor.execute("REINDEX")

        # Analyze tables for query optimization
        tables = ['icp_profiles', 'prospects', 'copy_templates', 'outreach_campaigns']
        for table in tables:
            cursor.execute(f"ANALYZE {table}")

        self.connection.commit()
        logger.info("Database optimization completed")

    def backup_database(self, backup_path: str) -> None:
        """Create database backup"""
        backup_conn = sqlite3.connect(backup_path)
        self.connection.backup(backup_conn)
        backup_conn.close()
        logger.info(f"Database backup created at {backup_path}")

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None

    def __del__(self):
        """Ensure connection is closed"""
        self.close()
