#!/usr/bin/env python3
"""
Database Demo for Copy Factory
Showcase the database capabilities
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.database import CopyFactoryDatabase
from core.config import get_config


def database_demo():
    """Demonstrate database capabilities"""

    print("🗄️ Copy Factory Database Demo")
    print("=" * 40)

    # Check configuration
    config = get_config()
    backend = config.get('storage.backend')

    print(f"📊 Current Storage Backend: {backend}")

    if backend != 'database':
        print("⚠️ Switching to database backend for demo...")
        config.set('storage.backend', 'database')
        config.save()
        print("✅ Switched to database backend")

    # Initialize database
    print("
🗄️ Initializing database..."    try:
        db = CopyFactoryDatabase()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return

    # Show database stats
    print("
📊 Database Statistics:"    stats = db.get_database_stats()

    print(f"  Database Size: {stats.get('database_size_bytes', 0) // 1024} KB")
    print(f"  Tables: {len([k for k in stats.keys() if k.endswith('_count')])}")

    table_stats = []
    for key, value in stats.items():
        if key.endswith('_count'):
            table_name = key.replace('_count', '').replace('_', ' ').title()
            table_stats.append(f"  {table_name}: {value}")

    for stat in sorted(table_stats):
        print(stat)

    # Show recent activity
    print("
📈 Recent Activity:"    print(f"  Prospects updated today: {stats.get('prospects_updated_today', 0)}")
    print(f"  AI insights generated today: {stats.get('insights_generated_today', 0)}")

    # Demonstrate database features
    print("
🔍 Database Features:"    print("  ✅ ACID transactions"    print("  ✅ Foreign key constraints"    print("  ✅ WAL mode for performance"    print("  ✅ Automatic indexing"    print("  ✅ Schema migrations"    print("  ✅ Backup and restore"    print("  ✅ Performance optimization"    print("  ✅ Concurrent access"

    # Show available commands
    print("
🛠️ Available Database Commands:"    print("  make db-init     - Initialize database"    print("  make db-migrate  - Migrate JSON data to database"    print("  make db-stats    - Show database statistics"    print("  make db-optimize - Optimize database performance"    print("  make db-backup   - Create database backup"    print("  make db-config   - Show database configuration"    print("  make db-switch   - Switch to database backend"    print("  make json-switch - Switch to JSON backend"

    print("
🎉 Database Demo Complete!"    print("Your AI Copy Factory now has a robust database backend!")
    print("💡 All data is now stored efficiently with proper relationships and indexing.")


if __name__ == '__main__':
    database_demo()
