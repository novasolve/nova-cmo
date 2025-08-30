#!/usr/bin/env python3
"""
Phase 2 Testing Suite
Comprehensive tests for all Phase 2 Data Validation & Quality Assurance components
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timedelta

# Add lead_intelligence to path
sys.path.insert(0, str(Path(__file__).parent))

from lead_intelligence.core.icp_filter import ICPRelevanceFilter
from lead_intelligence.core.activity_filter import ActivityThresholdFilter
from lead_intelligence.core.data_normalizer import DataNormalizer
from lead_intelligence.core.quality_gate import QualityGate
from lead_intelligence.core.phase2_orchestrator import Phase2Orchestrator, Phase2Config


class TestICPFilter(unittest.TestCase):
    """Test ICP Relevance Filter"""

    def setUp(self):
        self.icp_config = {
            'relevance_threshold': 0.6,
            'company_sizes': ['seed', 'series_a'],
            'tech_stacks': ['python_ml', 'web_dev'],
            'preferred_locations': ['us', 'united kingdom']
        }
        self.filter = ICPRelevanceFilter(self.icp_config)

    def test_high_relevance_prospect(self):
        """Test prospect that should be highly relevant"""
        prospect = {
            'name': 'John Smith',
            'company': 'Acme AI Startup',
            'location': 'San Francisco, CA',
            'bio': 'Python developer working on machine learning at a seed-stage startup',
            'topics': ['machine-learning', 'python', 'tensorflow'],
            'language': 'python',
            'repo_full_name': 'acme/ml-tools',
            'signal_type': 'pr',
            'signal': 'Add ML model improvements'
        }

        result = self.filter.is_relevant(prospect)

        self.assertTrue(result.is_relevant)
        self.assertGreater(result.relevance_score, 0.8)
        self.assertIn('python_ml', [r for r in result.match_reasons if 'python' in r.lower()])

    def test_low_relevance_prospect(self):
        """Test prospect that should have low relevance"""
        prospect = {
            'name': 'Jane Doe',
            'company': 'Enterprise Corp',
            'location': 'New York, NY',
            'bio': 'Java developer at large enterprise',
            'topics': ['java', 'spring', 'enterprise'],
            'language': 'java',
            'repo_full_name': 'enterprise/legacy-system'
        }

        result = self.filter.is_relevant(prospect)

        self.assertFalse(result.is_relevant)
        self.assertLess(result.relevance_score, 0.4)

    def test_company_size_matching(self):
        """Test company size filtering"""
        # Seed stage company
        seed_prospect = {
            'company': 'Seed Stage Startup',
            'bio': 'Working at a seed-stage AI company'
        }

        result = self.filter.is_relevant(seed_prospect)
        self.assertGreater(result.relevance_score, 0.3)  # Should match seed stage

    def test_tech_stack_matching(self):
        """Test technology stack matching"""
        # Python ML prospect
        ml_prospect = {
            'bio': 'Machine learning engineer using Python and TensorFlow',
            'topics': ['machine-learning', 'python', 'tensorflow'],
            'language': 'python'
        }

        result = self.filter.is_relevant(ml_prospect)
        self.assertGreater(result.relevance_score, 0.4)  # Should match python_ml stack


class TestActivityFilter(unittest.TestCase):
    """Test Activity Threshold Filter"""

    def setUp(self):
        self.activity_config = {
            'activity_days_threshold': 90,
            'min_activity_score': 0.6,
            'require_maintainer_status': False
        }
        self.filter = ActivityThresholdFilter(self.activity_config)

    def test_recent_high_quality_activity(self):
        """Test prospect with recent high-quality activity"""
        recent_time = (datetime.now() - timedelta(days=30)).isoformat()

        prospect = {
            'signal_at': recent_time,
            'signal_type': 'pr',
            'signal': 'Improve CI pipeline performance',
            'followers': 150,
            'public_repos': 25,
            'bio': 'Maintainer of popular Python library',
            'is_maintainer': True
        }

        result = self.filter.meets_activity_requirements(prospect)

        self.assertTrue(result.passes_filter)
        self.assertGreater(result.activity_score, 0.8)

    def test_old_activity(self):
        """Test prospect with old activity"""
        old_time = (datetime.now() - timedelta(days=200)).isoformat()

        prospect = {
            'signal_at': old_time,
            'signal_type': 'commit',
            'followers': 10,
            'public_repos': 5
        }

        result = self.filter.meets_activity_requirements(prospect)

        self.assertFalse(result.passes_filter)

    def test_maintainer_status_bonus(self):
        """Test maintainer status gives activity bonus"""
        prospect = {
            'signal_at': (datetime.now() - timedelta(days=60)).isoformat(),
            'signal_type': 'issue',
            'is_maintainer': True,
            'bio': 'Project maintainer and core contributor'
        }

        result = self.filter.meets_activity_requirements(prospect)

        self.assertTrue(result.passes_filter)
        self.assertIn('maintainer', result.activity_reasons[0].lower())


class TestDataNormalizer(unittest.TestCase):
    """Test Data Normalizer"""

    def setUp(self):
        self.config = {
            'normalize_names': True,
            'normalize_companies': True,
            'normalize_emails': True,
            'lowercase_emails': True
        }
        self.normalizer = DataNormalizer(self.config)

    def test_name_normalization(self):
        """Test name normalization"""
        prospect = {
            'name': 'john DOE-smith'
        }

        result = self.normalizer.normalize_prospect(prospect)

        self.assertEqual(result.normalized_prospect['name'], 'John Doe-Smith')
        self.assertIn('name', result.changes_made)

    def test_email_normalization(self):
        """Test email normalization"""
        prospect = {
            'email_profile': 'John.DOE@EXAMPLE.COM'
        }

        result = self.normalizer.normalize_prospect(prospect)

        self.assertEqual(result.normalized_prospect['email_profile'], 'john.doe@example.com')
        self.assertIn('email_profile', result.changes_made)

    def test_company_normalization(self):
        """Test company normalization"""
        prospect = {
            'company': 'acme corp.'
        }

        result = self.normalizer.normalize_prospect(prospect)

        self.assertEqual(result.normalized_prospect['company'], 'Acme Corp')
        self.assertIn('company', result.changes_made)

    def test_bio_truncation(self):
        """Test bio length truncation"""
        long_bio = 'A' * 600
        prospect = {
            'bio': long_bio
        }

        result = self.normalizer.normalize_prospect(prospect)

        self.assertLess(len(result.normalized_prospect['bio']), 550)
        self.assertIn('bio', result.changes_made)


class TestQualityGate(unittest.TestCase):
    """Test Quality Gates"""

    def setUp(self):
        self.config = {
            'email_required': True,
            'data_completeness_threshold': 0.8,
            'data_accuracy_threshold': 0.7,
            'blocked_email_domains': ['blocked.com']
        }
        self.gate = QualityGate(self.config)

    def test_passes_all_gates(self):
        """Test prospect that passes all quality gates"""
        prospect = {
            'login': 'testuser',
            'name': 'Test User',
            'email_profile': 'test@example.com',
            'github_user_url': 'https://github.com/testuser',
            'repo_full_name': 'test/repo',
            'signal': 'Test PR',
            'signal_type': 'pr',
            'signal_at': datetime.now().isoformat(),
            'icp_relevance_score': 0.8,
            'bio': 'Good bio description',
            'company': 'Test Company'
        }

        result = self.gate.validate_prospect(prospect)

        self.assertTrue(result.passes_all_gates)
        self.assertGreater(result.quality_score, 0.7)

    def test_fails_email_gate(self):
        """Test prospect that fails email gate"""
        prospect = {
            'login': 'testuser',
            'name': 'Test User',
            # No email
            'github_user_url': 'https://github.com/testuser'
        }

        result = self.gate.validate_prospect(prospect)

        self.assertFalse(result.passes_all_gates)
        self.assertIn('email', result.gate_results)
        self.assertFalse(result.gate_results['email'])
        self.assertIn('No email address found', result.failure_reasons[0])

    def test_fails_completeness_gate(self):
        """Test prospect that fails completeness gate"""
        prospect = {
            'login': 'testuser',
            # Missing required fields
            'email_profile': 'test@example.com'
        }

        result = self.gate.validate_prospect(prospect)

        self.assertFalse(result.passes_all_gates)
        self.assertFalse(result.gate_results['completeness'])

    def test_blocked_email_domain(self):
        """Test prospect with blocked email domain"""
        prospect = {
            'login': 'testuser',
            'name': 'Test User',
            'email_profile': 'test@blocked.com',
            'github_user_url': 'https://github.com/testuser',
            'repo_full_name': 'test/repo',
            'signal': 'Test PR',
            'signal_type': 'pr',
            'signal_at': datetime.now().isoformat()
        }

        result = self.gate.validate_prospect(prospect)

        self.assertFalse(result.passes_all_gates)
        self.assertIn('blocked_email_domain', result.failure_reasons[0])


class TestPhase2Orchestrator(unittest.TestCase):
    """Test Phase 2 Orchestrator"""

    def setUp(self):
        self.config = Phase2Config(
            validation_enabled=True,
            deduplication_enabled=True,
            compliance_enabled=False,  # Disable for simpler testing
            icp_filtering_enabled=True,
            activity_filtering_enabled=True,
            normalization_enabled=True,
            quality_gates_enabled=True,
            icp_config={
                'relevance_threshold': 0.5,
                'company_sizes': ['seed', 'series_a'],
                'tech_stacks': ['python_ml']
            },
            activity_config={
                'activity_days_threshold': 90,
                'min_activity_score': 0.5
            }
        )
        self.orchestrator = Phase2Orchestrator(self.config)

    def test_full_pipeline(self):
        """Test complete Phase 2 pipeline"""
        prospects = [
            # Good prospect
            {
                'lead_id': '1',
                'login': 'gooduser',
                'name': 'Good User',
                'email_profile': 'good@example.com',
                'company': 'Seed Startup',
                'location': 'San Francisco, CA',
                'bio': 'Python ML engineer at seed-stage startup',
                'topics': ['machine-learning', 'python'],
                'language': 'python',
                'github_user_url': 'https://github.com/gooduser',
                'repo_full_name': 'gooduser/ml-project',
                'signal_type': 'pr',
                'signal': 'Improve ML model',
                'signal_at': (datetime.now() - timedelta(days=30)).isoformat(),
                'followers': 50,
                'public_repos': 15
            },
            # Bad prospect (no email)
            {
                'lead_id': '2',
                'login': 'baduser',
                'name': 'Bad User',
                'github_user_url': 'https://github.com/baduser'
            }
        ]

        result = self.orchestrator.process_phase2_sync(prospects)

        self.assertTrue(result.success)
        self.assertEqual(len(result.qualified_prospects), 1)
        self.assertEqual(len(result.rejected_prospects), 1)
        self.assertGreater(result.stats['qualification_rate'], 0)

    def test_empty_input(self):
        """Test pipeline with empty input"""
        result = self.orchestrator.process_phase2_sync([])

        self.assertTrue(result.success)
        self.assertEqual(len(result.qualified_prospects), 0)
        self.assertEqual(len(result.rejected_prospects), 0)


class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios"""

    def setUp(self):
        self.config = Phase2Config(
            icp_config={
                'relevance_threshold': 0.6,
                'company_sizes': ['seed'],
                'tech_stacks': ['python_ml'],
                'preferred_locations': ['us']
            }
        )
        self.orchestrator = Phase2Orchestrator(self.config)

    def test_monday_campaign_scenario(self):
        """Test scenario similar to Monday 2,000 email campaign preparation"""

        # Create sample prospects similar to what would come from Phase 1
        prospects = []

        # Create 10 good prospects
        for i in range(10):
            prospect = {
                'lead_id': f'good_{i}',
                'login': f'user{i}',
                'name': f'User {i}',
                'email_profile': f'user{i}@example.com',
                'company': 'Seed Stage Startup' if i % 2 == 0 else 'Series A Company',
                'location': 'San Francisco, CA' if i % 3 == 0 else 'New York, NY',
                'bio': f'Python developer working on ML at startup {i}',
                'topics': ['python', 'machine-learning', 'tensorflow'],
                'language': 'python',
                'github_user_url': f'https://github.com/user{i}',
                'repo_full_name': f'user{i}/ml-project-{i}',
                'signal_type': 'pr',
                'signal': f'Improve ML model performance #{i}',
                'signal_at': (datetime.now() - timedelta(days=30 + i)).isoformat(),
                'followers': 20 + i * 10,
                'public_repos': 5 + i,
                'is_maintainer': i % 3 == 0
            }
            prospects.append(prospect)

        # Create 5 bad prospects
        for i in range(5):
            prospect = {
                'lead_id': f'bad_{i}',
                'login': f'baduser{i}',
                'name': f'Bad User {i}',
                # No email - should fail
                'github_user_url': f'https://github.com/baduser{i}',
                'signal_at': (datetime.now() - timedelta(days=200)).isoformat()  # Too old
            }
            prospects.append(prospect)

        result = self.orchestrator.process_phase2_sync(prospects)

        # Should qualify most good prospects
        self.assertGreater(len(result.qualified_prospects), 5)
        self.assertLess(len(result.rejected_prospects), 10)

        # Check stats
        self.assertGreater(result.stats['qualification_rate'], 0.4)
        self.assertEqual(result.stats['input_prospects'], 15)


def create_sample_data_file():
    """Create a sample data file for testing"""
    sample_prospects = [
        {
            'lead_id': 'sample_1',
            'login': 'johndoe',
            'name': 'John Doe',
            'email_profile': 'john@example.com',
            'company': 'Acme AI',
            'location': 'San Francisco, CA',
            'bio': 'Python ML engineer at AI startup',
            'topics': ['python', 'machine-learning'],
            'language': 'python',
            'github_user_url': 'https://github.com/johndoe',
            'repo_full_name': 'johndoe/ml-tools',
            'signal_type': 'pr',
            'signal': 'Add ML model improvements',
            'signal_at': (datetime.now() - timedelta(days=30)).isoformat(),
            'followers': 150,
            'public_repos': 25
        },
        {
            'lead_id': 'sample_2',
            'login': 'janedoe',
            'name': 'Jane Doe',
            # No email - should be filtered out
            'github_user_url': 'https://github.com/janedoe'
        }
    ]

    return sample_prospects


def run_integration_test():
    """Run a full integration test"""
    print("🧪 Running Phase 2 Integration Test")
    print("=" * 50)

    # Create sample data
    prospects = create_sample_data_file()
    print(f"📥 Created {len(prospects)} sample prospects")

    # Create orchestrator
    config = Phase2Config(
        icp_config={
            'relevance_threshold': 0.6,
            'company_sizes': ['seed', 'series_a'],
            'tech_stacks': ['python_ml']
        }
    )
    orchestrator = Phase2Orchestrator(config)

    # Run pipeline
    print("🔄 Running Phase 2 pipeline...")
    result = orchestrator.process_phase2_sync(prospects)

    # Show results
    print("
📊 Results:"    print(f"   Qualified: {len(result.qualified_prospects)}")
    print(f"   Rejected: {len(result.rejected_prospects)}")
    print(".2%")
    print(".2f")

    if result.qualified_prospects:
        print("
✅ Qualified Prospects:"        for prospect in result.qualified_prospects:
            print(f"   • {prospect['name']} ({prospect['login']}) - {prospect['email_profile']}")

    if result.rejected_prospects:
        print("
❌ Rejected Prospects:"        for rejection in result.rejected_prospects:
            reasons = rejection.get('rejection_reasons', ['Unknown'])
            print(f"   • {rejection['prospect']['login']} - {reasons[0]}")

    print("
✅ Integration test completed successfully!"    return result.success


if __name__ == '__main__':
    # Run integration test if called directly
    if len(sys.argv) > 1 and sys.argv[1] == '--integration':
        success = run_integration_test()
        sys.exit(0 if success else 1)

    # Otherwise run unit tests
    unittest.main(verbosity=2)
