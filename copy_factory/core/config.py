#!/usr/bin/env python3
"""
Configuration management for Copy Factory
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CopyFactoryConfig:
    """Configuration manager for Copy Factory"""

    def __init__(self, config_file: str = "copy_factory/config/copy_factory.yaml"):
        self.config_file = Path(config_file)
        self.config_dir = self.config_file.parent
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""

        default_config = {
            'database': {
                'path': 'copy_factory/data/copy_factory.db',
                'backup_enabled': True,
                'backup_schedule': 'daily',
                'optimize_schedule': 'weekly'
            },
            'storage': {
                'backend': 'database',  # 'database' or 'json'
                'json_data_dir': 'copy_factory/data',
                'cache_enabled': True,
                'cache_ttl_hours': 24
            },
            'ai': {
                'openai_api_key': os.environ.get('OPENAI_API_KEY', ''),
                'model': 'gpt-4o-mini',
                'max_tokens': 2000,
                'temperature': 0.7,
                'cache_enabled': True
            },
            'performance': {
                'tracking_enabled': True,
                'metrics_retention_days': 90,
                'auto_optimization': True,
                'ab_test_enabled': True
            },
            'security': {
                'encrypt_sensitive_data': False,
                'api_key_rotation_days': 30,
                'audit_log_enabled': True
            },
            'limits': {
                'max_prospects_per_campaign': 1000,
                'max_ai_requests_per_hour': 100,
                'max_cache_size_mb': 500,
                'max_database_size_mb': 1000
            },
            'features': {
                'ai_copy_generation': True,
                'smart_icp_matching': True,
                'content_analysis': True,
                'campaign_automation': True,
                'performance_tracking': True,
                'ab_testing': True
            }
        }

        if self.config_file.exists():
            try:
                import yaml
                with open(self.config_file, 'r') as f:
                    loaded_config = yaml.safe_load(f)
                    # Merge with defaults
                    self._merge_configs(default_config, loaded_config)
            except Exception as e:
                logger.warning(f"Could not load config file: {e}")
        else:
            logger.info(f"Config file not found, using defaults: {self.config_file}")

        return default_config

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Recursively merge configuration dictionaries"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_configs(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        keys = key.split('.')
        value = self._config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        keys = key.split('.')
        config = self._config

        # Navigate to the parent of the final key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set the final value
        config[keys[-1]] = value

    def save(self) -> None:
        """Save configuration to file"""
        try:
            import yaml
            with open(self.config_file, 'w') as f:
                yaml.dump(self._config, f, default_flow_style=False, indent=2)
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Could not save config: {e}")

    def get_database_path(self) -> str:
        """Get database path from config"""
        return self.get('database.path', 'copy_factory/data/copy_factory.db')

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled"""
        return self.get(f'features.{feature}', False)

    def get_ai_config(self) -> Dict[str, Any]:
        """Get AI configuration"""
        return {
            'api_key': self.get('ai.openai_api_key'),
            'model': self.get('ai.model'),
            'max_tokens': self.get('ai.max_tokens'),
            'temperature': self.get('ai.temperature'),
            'cache_enabled': self.get('ai.cache_enabled')
        }

    def get_storage_config(self) -> Dict[str, Any]:
        """Get storage configuration"""
        return {
            'backend': self.get('storage.backend', 'database'),
            'data_dir': self.get('storage.json_data_dir'),
            'cache_enabled': self.get('storage.cache_enabled'),
            'cache_ttl_hours': self.get('storage.cache_ttl_hours')
        }

    def validate_config(self) -> Dict[str, Any]:
        """Validate configuration"""
        issues = []

        # Check required configurations
        if not self.get('ai.openai_api_key'):
            issues.append("OpenAI API key not configured")

        if self.get('storage.backend') not in ['database', 'json']:
            issues.append("Invalid storage backend")

        # Check limits
        max_prospects = self.get('limits.max_prospects_per_campaign')
        if max_prospects and max_prospects < 1:
            issues.append("Invalid max prospects per campaign")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'config_version': '1.0'
        }

    def create_default_config(self) -> None:
        """Create default configuration file"""
        if not self.config_file.exists():
            self.save()
            logger.info(f"Created default configuration at {self.config_file}")

    def print_config(self) -> None:
        """Print current configuration"""
        print("🔧 Copy Factory Configuration")
        print("=" * 40)

        for section, values in self._config.items():
            print(f"\n{section.upper()}:")
            if isinstance(values, dict):
                for key, value in values.items():
                    if 'api_key' in key.lower():
                        print(f"  {key}: {'*' * 10} (hidden)")
                    else:
                        print(f"  {key}: {value}")
            else:
                print(f"  {values}")

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults"""
        self._config = self._load_config()
        logger.info("Configuration reset to defaults")

    def export_config(self, export_path: str) -> None:
        """Export configuration to JSON"""
        try:
            with open(export_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            logger.info(f"Configuration exported to {export_path}")
        except Exception as e:
            logger.error(f"Could not export config: {e}")

    def import_config(self, import_path: str) -> None:
        """Import configuration from JSON"""
        try:
            with open(import_path, 'r') as f:
                imported_config = json.load(f)

            self._merge_configs(self._config, imported_config)
            logger.info(f"Configuration imported from {import_path}")
        except Exception as e:
            logger.error(f"Could not import config: {e}")


# Global configuration instance
_config_instance = None

def get_config() -> CopyFactoryConfig:
    """Get global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = CopyFactoryConfig()
    return _config_instance


def init_config() -> CopyFactoryConfig:
    """Initialize and return configuration"""
    config = get_config()
    config.create_default_config()
    return config

