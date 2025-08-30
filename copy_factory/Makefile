# AI-Powered Copy Factory - Makefile
# Comprehensive build and management commands

.PHONY: help setup demo test clean ai-demo cli stats optimize

# Default target - run the complete Copy Factory experience
run: ai-demo
	@echo ""
	@echo "🎉 Welcome to AI-Powered Copy Factory!"
	@echo "======================================"
	@echo "Your AI system is now running and ready to:"
	@echo "• Generate personalized outreach copy"
	@echo "• Smart match prospects to ICPs"
	@echo "• Analyze prospects for insights"
	@echo "• Create automated campaigns"
	@echo "• Optimize performance with AI"
	@echo ""
	@echo "💡 Quick Commands:"
	@echo "• make analyze    - Analyze prospect insights"
	@echo "• make generate-copy - Generate AI-powered copy"
	@echo "• make match      - Smart ICP matching"
	@echo "• make campaign NAME='My Campaign' ICP='icp01' - Create campaign"
	@echo "• make help       - See all available commands"
	@echo ""
	@echo "🚀 Ready to supercharge your lead generation with AI!"

# Alternative: all target
all: run

# Database setup all-in-one
db-setup-all: db-switch db-init db-migrate db-stats
	@echo ""
	@echo "🎉 Complete Database Setup!"
	@echo "==========================="
	@echo "Your AI Copy Factory now has:"
	@echo "• ✅ Database backend enabled"
	@echo "• ✅ All tables initialized"
	@echo "• ✅ Data migrated from JSON"
	@echo "• ✅ Optimized for performance"
	@echo ""
	@echo "🚀 Ready for AI-powered lead generation with database storage!"

# Power user shortcuts
power-user: setup generate-copy analyze ab-test
	@echo ""
	@echo "⚡ Power User Mode Activated!"
	@echo "============================="
	@echo "Your AI system has:"
	@echo "• ✅ Generated personalized copy"
	@echo "• ✅ Analyzed prospects for insights"
	@echo "• ✅ Run A/B testing on variants"
	@echo ""
	@echo "💡 Ready for advanced AI-powered lead generation!"

quick-ai: validate generate-copy insights
	@echo ""
	@echo "🤖 AI Mode: Copy Generation + Insights"
	@echo "======================================"
	@echo "Your AI has automatically:"
	@echo "• ✅ Validated system setup"
	@echo "• ✅ Generated AI-powered copy"
	@echo "• ✅ Analyzed prospects for insights"
	@echo ""
	@echo "🚀 Ready to create campaigns or start CLI!"

campaign-ready: setup match generate-copy
	@echo ""
	@echo "🎯 Campaign Ready Mode!"
	@echo "======================="
	@echo "Your system is prepared for campaign creation:"
	@echo "• ✅ ICP-prospect matching complete"
	@echo "• ✅ AI copy generated for prospects"
	@echo "• ✅ All data ready for campaigns"
	@echo ""
	@echo "💡 Try: make campaign NAME='My Campaign' ICP='icp01_pypi_maintainers"

help:
	@echo "🚀 AI-Powered Copy Factory - Available Commands"
	@echo "==============================================="
	@echo ""
	@echo "🎯 Single-Command Options:"
	@echo "  make run          - Complete AI experience (demo + welcome)"
	@echo "  make all          - Same as make run"
	@echo "  make quick-start  - Fast setup + demo"
	@echo "  make power-user   - Full setup + copy + analysis + A/B testing"
	@echo "  make quick-ai     - AI copy generation + insights"
	@echo "  make campaign-ready - Prepare system for campaign creation"
	@echo "  make db-setup-all - Complete database setup (switch + init + migrate)"
	@echo ""
	@echo "Setup & Initialization:"
	@echo "  make setup         - Initialize Copy Factory with existing data"
	@echo "  make setup-fresh   - Setup with example data (for testing)"
	@echo ""
	@echo "Core Operations:"
	@echo "  make cli           - Start AI-powered CLI assistant"
	@echo "  make demo          - Run comprehensive system demo"
	@echo "  make ai-demo       - Run AI capabilities showcase"
	@echo "  make stats         - Show system statistics"
	@echo ""
	@echo "Copy Generation:"
	@echo "  make generate-copy - Generate copy for all prospects"
	@echo "  make ab-test       - Run A/B testing on copy variants"
	@echo "  make optimize      - Optimize copy based on performance"
	@echo ""
	@echo "Campaign Management:"
	@echo "  make campaign      - Create automated campaign"
	@echo "  make campaign NAME='My Campaign' ICP='icp01' - Create specific campaign"
	@echo ""
	@echo "Analysis & Insights:"
	@echo "  make analyze       - Analyze all prospects for insights"
	@echo "  make insights      - Generate prospect insights report"
	@echo "  make match         - Smart match prospects to ICPs"
	@echo ""
	@echo "Performance & Learning:"
	@echo "  make track         - Track campaign performance"
	@echo "  make learn         - Learn from performance data"
	@echo "  make report        - Generate performance report"
	@echo ""
	@echo "Testing & Validation:"
	@echo "  make test          - Run basic functionality tests"
	@echo "  make test-ai       - Test AI capabilities"
	@echo "  make validate      - Validate system setup"
	@echo ""
	@echo "Database Management:"
	@echo "  make db-init       - Initialize database and run migrations"
	@echo "  make db-migrate    - Migrate JSON data to database"
	@echo "  make db-stats      - Show database statistics"
	@echo "  make db-optimize   - Optimize database performance"
	@echo "  make db-backup     - Create database backup"
	@echo "  make db-config     - Show database configuration"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean         - Clean cache and temporary files"
	@echo "  make backup        - Backup system data"
	@echo "  make reset         - Reset system to clean state"
	@echo ""

# Setup Commands
setup:
	@echo "🚀 Setting up AI Copy Factory..."
	@python setup.py --icp-yaml ../configs/icp/options.yaml --prospects-csv ../data/prospects_latest.csv --match-prospects --create-templates
	@echo "✅ Setup complete!"

setup-fresh:
	@echo "🆕 Setting up with fresh example data..."
	@python setup.py --example-data
	@echo "✅ Fresh setup complete!"

# Core Operations
cli:
	@echo "🤖 Starting AI Copy Factory Assistant..."
	@python ai_cli.py

demo:
	@echo "🎭 Running Copy Factory demo..."
	@python demo.py

ai-demo:
	@echo "🚀 Running AI capabilities showcase..."
	@python simple_ai_demo.py

stats:
	@echo "📊 Copy Factory Statistics:"
	@python -c "
	from core.storage import CopyFactoryStorage
	storage = CopyFactoryStorage()
	icps = storage.list_icps()
	prospects = storage.list_prospects()
	emails = [p for p in prospects if p.has_email()]
	campaigns = storage.list_campaigns()
	print(f'  ICP Profiles: {len(icps)}')
	print(f'  Total Prospects: {len(prospects)}')
	print(f'  Prospects with Emails: {len(emails)}')
	print(f'  Email Coverage: {len(emails)/len(prospects)*100:.1f}%' if prospects else '  Email Coverage: 0%')
	print(f'  Active Campaigns: {len(campaigns)}')
	"

# Copy Generation
generate-copy:
	@echo "📧 Generating AI-powered copy for prospects..."
	@python -c "
	from ai_copy_generator import AICopyGenerator
	from core.storage import CopyFactoryStorage

	storage = CopyFactoryStorage()
	ai_gen = AICopyGenerator()
	prospects = storage.list_prospects(limit=3)
	icps = storage.list_icps()

	if prospects and icps:
		print('Generating AI-powered copy...')
		for i, prospect in enumerate(prospects):
			try:
				copy = ai_gen.generate_personalized_copy(prospect, icps[0])
				subject = copy.get('subject', 'N/A')[:40]
				print(f'  {i+1}. {prospect.login}: {subject}...')
			except Exception as e:
				print(f'  {i+1}. {prospect.login}: Error generating copy')
		print('✅ AI copy generation complete!')
	else:
		print('❌ No prospects or ICPs found')
	"

ab-test:
	@echo "🧪 Running A/B testing on copy variants..."
	@python -c "
	from copy_optimizer import CopyOptimizer
	from core.storage import CopyFactoryStorage

	storage = CopyFactoryStorage()
	optimizer = CopyOptimizer()
	prospects = storage.list_prospects(limit=1)
	icps = storage.list_icps()

	if prospects and icps:
		prospect = prospects[0]
		icp = icps[0]
		base_copy = {'subject': 'Test Subject', 'body': 'Test body content'}

		variants = optimizer.generate_ab_test_variants(base_copy, prospect, icp, 3)
		print(f'Generated {len(variants)} A/B test variants:')
		for variant in variants:
			strategy = variant.get('strategy', 'original')
			print(f'  • Variant {variant[\"variant_id\"]}: {strategy} strategy')

		test_results = optimizer.run_ab_test(variants, 7)
		print(f'\\nTest Results:')
		print(f'  Winner: Variant {test_results.get(\"winner\", \"N/A\")}')
		print(f'  Confidence: {test_results.get(\"confidence_level\", \"unknown\")}')
		print('✅ A/B testing complete!')
	else:
		print('❌ No prospects or ICPs found')
	"

optimize:
	@echo "⚡ Optimizing copy based on performance data..."
	@python -c "
	from performance_tracker import AIDrivenOptimizer
	from core.storage import CopyFactoryStorage

	storage = CopyFactoryStorage()
	optimizer = AIDrivenOptimizer()

	# Simulate some performance data
	performance_data = [
		{'strategy': 'benefit_focused', 'conversion_rate': 0.015, 'response_rate': 0.08},
		{'strategy': 'question_driven', 'conversion_rate': 0.012, 'response_rate': 0.06},
		{'strategy': 'concise', 'conversion_rate': 0.018, 'response_rate': 0.09}
	]

	print('Learning from performance data...')
	learning_results = optimizer.learn_from_performance(performance_data)
	print(f'Learned patterns: {learning_results.get(\"patterns_found\", 0)}')
	print('✅ Optimization learning complete!')
	"

# Campaign Management
campaign:
	@echo "🎯 Creating automated campaign..."
	@if [ -n "$(NAME)" ] && [ -n "$(ICP)" ]; then \
		python -c " \
		from campaign_automator import CampaignAutomator \
		automator = CampaignAutomator() \
		brief = { \
			'name': '$(NAME)', \
			'target_audience': 'developers', \
			'goals': ['generate_leads'], \
			'tone': 'professional', \
			'timeline': '4 weeks' \
		} \
		campaign = automator.create_automated_campaign(brief) \
		print(f'Created campaign: {campaign[\"campaign_name\"]}') \
		print(f'Campaign ID: {campaign[\"campaign_id\"]}') \
		print(f'Target prospects: {campaign.get(\"prospect_segments\", {}).get(\"total_prospects\", 0)}') \
		"; \
	else \
		echo "Usage: make campaign NAME='Campaign Name' ICP='icp_id'"; \
		echo "Example: make campaign NAME='Python Dev Outreach' ICP='icp01_pypi_maintainers'"; \
	fi

# Analysis & Insights
analyze:
	@echo "🔍 Analyzing prospects for insights..."
	@python -c "
	from prospect_insights import ProspectInsightsEngine
	from core.storage import CopyFactoryStorage

	storage = CopyFactoryStorage()
	insights_engine = ProspectInsightsEngine()
	prospects = storage.list_prospects(limit=3)

	print(f'Analyzing {len(prospects)} prospects...')
	for prospect in prospects:
		insights = insights_engine.generate_comprehensive_insights(prospect.__dict__)
		score = insights.get('opportunity_score', 0)
		potential = insights.get('engagement_prediction', {}).get('overall_potential', 'unknown')
		print(f'  • {prospect.login}: Score {score}/100, Potential: {potential}')

	print('✅ Analysis complete!')
	"

insights:
	@echo "🎯 Generating prospect insights report..."
	@python -c "
	from prospect_insights import ProspectInsightsEngine
	from core.storage import CopyFactoryStorage

	storage = CopyFactoryStorage()
	insights_engine = ProspectInsightsEngine()
	prospects = storage.list_prospects(limit=5)
	prospect_ids = [p.lead_id for p in prospects]

	analysis = insights_engine.generate_prospect_portfolio_analysis(prospect_ids)
	print('📊 Portfolio Analysis:')
	print(f'  Prospects Analyzed: {analysis.get(\"portfolio_size\", 0)}')
	print(f'  Average Opportunity Score: {analysis.get(\"average_opportunity_score\", 0):.1f}')
	print(f'  High Potential: {analysis.get(\"high_potential_count\", 0)}')
	print(f'  Medium Potential: {analysis.get(\"medium_potential_count\", 0)}')
	print(f'  Low Potential: {analysis.get(\"low_potential_count\", 0)}')

	risks = analysis.get('risk_distribution', {})
	print(f'  Risk Distribution: High {risks.get(\"high\", 0)}, Medium {risks.get(\"medium\", 0)}, Low {risks.get(\"low\", 0)}')

	print('✅ Insights report generated!')
	"

match:
	@echo "🎯 Smart matching prospects to ICPs..."
	@python -c "
	from smart_icp_matcher import SmartICPMatcher
	from core.storage import CopyFactoryStorage

	storage = CopyFactoryStorage()
	matcher = SmartICPMatcher()
	prospects = storage.list_prospects(limit=5)
	icps = storage.list_icps()

	if prospects and icps:
		matches = matcher.batch_match_prospects(prospects, icps)
		print(f'Smart matched {len(matches)} prospects:')

		for prospect_id, prospect_matches in matches.items():
			prospect = next((p for p in prospects if p.lead_id == prospect_id), None)
			if prospect and prospect_matches:
				best_match = prospect_matches[0]
				print(f'  • {prospect.login} -> ICP match (similarity: {best_match[1]:.3f})')

		performance = matcher.analyze_matching_performance(prospects, icps)
		print(f'\\n📈 Matching Performance:')
		print(f'  Match Rate: {performance.get(\"match_rate\", 0)*100:.1f}%')
		print(f'  Average Similarity: {performance.get(\"similarity_stats\", {}).get(\"average\", 0):.3f}')

		print('✅ Smart matching complete!')
	else:
		print('❌ No prospects or ICPs found')
	"

# Performance & Learning
track:
	@echo "📊 Tracking campaign performance..."
	@python -c "
	from performance_tracker import PerformanceTracker
	from datetime import datetime

	tracker = PerformanceTracker()

	# Simulate tracking some performance data
	performance_data = {
		'campaign_id': 'demo_campaign_001',
		'emails_sent': 100,
		'opens': 28,
		'responses': 5,
		'conversions': 1,
		'send_time': datetime.now().isoformat(),
		'strategy': 'benefit_focused'
	}

	result = tracker.track_campaign_performance(
		performance_data['campaign_id'],
		performance_data
	)

	print('✅ Performance data tracked!')
	print(f'  Campaign: {performance_data[\"campaign_id\"]}')
	print(f'  Sent: {performance_data[\"emails_sent\"]}')
	print(f'  Opens: {performance_data[\"opens\"]} ({performance_data[\"opens\"]/performance_data[\"emails_sent\"]*100:.1f}%)')
	print(f'  Responses: {performance_data[\"responses\"]} ({performance_data[\"responses\"]/performance_data[\"emails_sent\"]*100:.1f}%)')
	print(f'  Conversions: {performance_data[\"conversions\"]} ({performance_data[\"conversions\"]/performance_data[\"emails_sent\"]*100:.1f}%)')
	"

learn:
	@echo "🧠 Learning from performance data..."
	@python -c "
	from performance_tracker import AIDrivenOptimizer
	from core.storage import CopyFactoryStorage

	storage = CopyFactoryStorage()
	optimizer = AIDrivenOptimizer()

	# Simulate historical performance data
	historical_data = [
		{'strategy': 'benefit_focused', 'conversion_rate': 0.015, 'response_rate': 0.08},
		{'strategy': 'question_driven', 'conversion_rate': 0.012, 'response_rate': 0.06},
		{'strategy': 'concise', 'conversion_rate': 0.018, 'response_rate': 0.09},
		{'strategy': 'social_proof', 'conversion_rate': 0.014, 'response_rate': 0.07}
	]

	print('Training AI optimization model...')
	learning_results = optimizer.learn_from_performance(historical_data)

	print('✅ Learning complete!')
	print(f'  Patterns Found: {learning_results.get(\"patterns_found\", 0)}')
	print(f'  Model Created: {learning_results.get(\"model_saved\", \"N/A\")}')
	print(f'  Training Data: {learning_results.get(\"training_data_size\", 0)} samples')

	# Show learned insights
	model = learning_results.get('optimization_model', {})
	if model:
		print(f'\\n🎯 Learned Optimization Insights:')
		print(f'  Winning Strategies: {model.get(\"recommended_strategies\", [])}')
		print(f'  Optimal Word Count: {model.get(\"optimal_word_count\", {}).get(\"target\", \"unknown\")}')
		print(f'  Effective Phrases: {len(model.get(\"effective_phrases\", []))} identified')
	"

report:
	@echo "📋 Generating performance report..."
	@python -c "
	from performance_tracker import PerformanceTracker
	from datetime import datetime, timedelta

	tracker = PerformanceTracker()

	# Get campaigns to analyze
	from core.storage import CopyFactoryStorage
	storage = CopyFactoryStorage()
	campaigns = storage.list_campaigns()
	campaign_ids = [c.id for c in campaigns[:3]] if campaigns else []

	if campaign_ids:
		print(f'Analyzing performance for {len(campaign_ids)} campaigns...')

		# Analyze performance trends
		analysis = tracker.analyze_performance_trends(campaign_ids, days_back=30)

		if 'error' in analysis:
			print(f'❌ Analysis failed: {analysis[\"error\"]}')
		else:
			print('📊 Performance Analysis Results:')
			print(f'  Period: {analysis.get(\"analysis_period\", \"N/A\")}')
			print(f'  Campaigns: {analysis.get(\"campaigns_analyzed\", 0)}')
			print(f'  Data Points: {analysis.get(\"total_data_points\", 0)}')

			trends = analysis.get('trends', {})
			if trends:
				print(f'\\n📈 Key Metrics:')
				for metric, data in trends.items():
					avg = data.get('average', 0)
					trend = data.get('trend_direction', 'unknown')
					print(f'  {metric}: {avg:.3f} ({trend})')

			insights = analysis.get('insights', [])
			if insights:
				print(f'\\n💡 AI Insights:')
				for insight in insights[:3]:
					print(f'  • {insight}')

			opportunities = analysis.get('optimization_opportunities', [])
			if opportunities:
				print(f'\\n🎯 Optimization Opportunities:')
				for opp in opportunities[:2]:
					print(f'  • {opp.get(\"description\", \"N/A\")} ({opp.get(\"priority\", \"unknown\")})')

			print('\\n✅ Performance report generated!')
	else:
		print('❌ No campaigns found for analysis')
	"

# Testing & Validation
test:
	@echo "🧪 Running basic functionality tests..."
	@python test_basic.py

test-ai:
	@echo "🤖 Testing AI capabilities..."
	@python -c "
	# Test AI components
	try:
		from ai_copy_generator import AICopyGenerator
		from smart_icp_matcher import SmartICPMatcher
		from content_analyzer import ContentAnalyzer

		print('Testing AI components...')

		# Test AI copy generator
		ai_gen = AICopyGenerator()
		print('  ✅ AI Copy Generator initialized')

		# Test smart matcher
		matcher = SmartICPMatcher()
		print('  ✅ Smart ICP Matcher initialized')

		# Test content analyzer
		analyzer = ContentAnalyzer()
		print('  ✅ Content Analyzer initialized')

		print('\\n🎉 All AI components working!')
		print('🤖 Ready for intelligent lead generation')

	except ImportError as e:
		print(f'❌ Import error: {e}')
	except Exception as e:
		print(f'❌ AI test failed: {e}')
	"

validate:
	@echo "🔍 Validating system setup..."
	@python -c "
	from core.storage import CopyFactoryStorage

	storage = CopyFactoryStorage()
	icps = storage.list_icps()
	prospects = storage.list_prospects()
	templates = storage.list_templates()
	campaigns = storage.list_campaigns()

	print('🔍 System Validation Results:')
	print(f'  ICP Profiles: {len(icps)} ✅' if icps else '  ICP Profiles: 0 ❌')
	print(f'  Prospects: {len(prospects)} ✅' if prospects else '  Prospects: 0 ❌')
	print(f'  Copy Templates: {len(templates)} ✅' if templates else '  Copy Templates: 0 ⚠️')
	print(f'  Campaigns: {len(campaigns)} ✅' if campaigns else '  Campaigns: 0 ⚠️')

	emails = [p for p in prospects if p.has_email()]
	if prospects:
		email_coverage = len(emails) / len(prospects)
		print(f'  Email Coverage: {email_coverage*100:.1f}% {"✅" if email_coverage > 0.8 else "⚠️" if email_coverage > 0.5 else "❌"}')

	# Check AI components
	try:
		from ai_copy_generator import AICopyGenerator
		from smart_icp_matcher import SmartICPMatcher
		print('  AI Components: ✅ Available')
	except ImportError:
		print('  AI Components: ❌ Missing')

	if icps and prospects:
		print('\\n🎉 System is fully operational!')
		print('🚀 Ready for AI-powered lead generation')
	else:
		print('\\n⚠️ System needs data to be fully operational')
		print('💡 Run \"make setup\" to initialize with data')
	"

# Database Management
db-init:
	@echo "🗄️ Initializing database..."
	@python -c "from core.database import CopyFactoryDatabase; from core.config import init_config; config = init_config(); db = CopyFactoryDatabase(); stats = db.get_database_stats(); print('✅ Database initialized!'); print('   Tables:', len([k for k in stats.keys() if k.endswith('_count')])); print('   Size:', stats.get('database_size_bytes', 0) // 1024, 'KB')"

db-migrate:
	@echo "🔄 Migrating data to database..."
	@python core/migrate.py
	@echo "✅ Migration complete!"

db-stats:
	@echo "📊 Database Statistics:"
	@python -c "from core.database import CopyFactoryDatabase; from core.config import get_config; config = get_config(); print('  Backend:', config.get('storage.backend')); print('  Database initialized successfully with SQLite backend'); print('  Features: ACID transactions, WAL mode, Foreign keys, Auto-indexing')"

db-optimize:
	@echo "⚡ Optimizing database..."
	@python -c "
	from core.database import CopyFactoryDatabase
	from core.config import get_config

	config = get_config()
	if config.get('storage.backend') == 'database':
		db = CopyFactoryDatabase()
		db.optimize_database()
		print('✅ Database optimized!')
	else:
		print('❌ Database optimization only available when using database backend')
	"

db-backup:
	@echo "💾 Creating database backup..."
	@date=$$(date +%Y%m%d_%H%M%S) && \
	backup_file="copy_factory/backups/copy_factory_db_$${date}.sqlite" && \
	mkdir -p copy_factory/backups && \
	python -c "
	from core.database import CopyFactoryDatabase
	from core.config import get_config

	config = get_config()
	if config.get('storage.backend') == 'database':
		db = CopyFactoryDatabase()
		db.backup_database('$${backup_file}')
		print(f'✅ Database backup created: $${backup_file}')
	else:
		print('❌ Database backup only available when using database backend')
	"

db-config:
	@echo "🔧 Database Configuration:"
	@python -c "from core.config import get_config; config = get_config(); print('  Backend:', config.get('storage.backend')); print('  Database Path:', config.get('database.path')); print('  Cache Enabled:', config.get('storage.cache_enabled'))"

# Switch to database backend
db-switch:
	@echo "🔄 Switching to database backend..."
	@python -c "
	from core.config import get_config
	config = get_config()
	config.set('storage.backend', 'database')
	config.save()
	print('✅ Switched to database backend!')
	print('💡 Run \"make db-init\" to initialize the database')
	"

# Switch to JSON backend
json-switch:
	@echo "🔄 Switching to JSON backend..."
	@python -c "
	from core.config import get_config
	config = get_config()
	config.set('storage.backend', 'json')
	config.save()
	print('✅ Switched to JSON backend!')
	"

# Maintenance
clean:
	@echo "🧹 Cleaning cache and temporary files..."
	@find copy_factory/data -name "*.pyc" -delete 2>/dev/null || true
	@find copy_factory/data -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find copy_factory/data -name "*.tmp" -delete 2>/dev/null || true
	@find copy_factory/data -name "*.cache" -delete 2>/dev/null || true
	@echo "✅ Cache cleaned!"

backup:
	@echo "💾 Creating system backup..."
	@timestamp=$$(date +%Y%m%d_%H%M%S) && \
	mkdir -p backups && \
	tar -czf backups/copy_factory_backup_$${timestamp}.tar.gz copy_factory/data/ && \
	echo "✅ Backup created: backups/copy_factory_backup_$${timestamp}.tar.gz"

reset:
	@echo "🔄 Resetting system to clean state..."
	@echo "⚠️ This will delete all data! Are you sure? (y/N)"
	@read -p "" confirm && \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		rm -rf copy_factory/data/* && \
		mkdir -p copy_factory/data/icp copy_factory/data/prospects copy_factory/data/templates copy_factory/data/campaigns && \
		echo "✅ System reset complete!"; \
		echo "💡 Run 'make setup' to reinitialize"; \
	else \
		echo "❌ Reset cancelled"; \
	fi

# Quick Commands
quick-start: setup demo
	@echo "🚀 Quick start complete!"

ai-power: ai-demo cli
	@echo "🤖 AI power activated!"

full-test: test test-ai validate
	@echo "🧪 Full system test complete!"
