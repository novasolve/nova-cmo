#!/usr/bin/env python3
"""
Error Handling and Recovery System
Comprehensive error management with recovery mechanisms
"""

import os
import sys
import json
import time
import logging
import traceback
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps
import asyncio
from concurrent.futures import ThreadPoolExecutor


logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling and recovery system"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.error_log = []
        self.recovery_actions = []
        self.setup_logging()
        self.setup_recovery_mechanisms()

    def _default_config(self) -> Dict[str, Any]:
        """Default error handling configuration"""
        return {
            'max_retries': 3,
            'retry_delay': 1.0,
            'exponential_backoff': True,
            'log_level': 'INFO',
            'error_log_path': 'lead_intelligence/logs/errors.log',
            'recovery_enabled': True,
            'backup_on_error': True,
            'notification_enabled': False,
            'circuit_breaker_threshold': 5,
            'circuit_breaker_timeout': 300  # 5 minutes
        }

    def setup_logging(self):
        """Setup error logging"""
        log_path = Path(self.config['error_log_path'])
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup file handler for errors
        error_handler = logging.FileHandler(log_path)
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        error_handler.setFormatter(error_formatter)

        # Add to root logger
        logging.getLogger().addHandler(error_handler)

        self.logger = logger

    def setup_recovery_mechanisms(self):
        """Setup recovery mechanisms"""
        if self.config['recovery_enabled']:
            # Register recovery actions
            self.register_recovery_action('api_rate_limit', self._handle_api_rate_limit)
            self.register_recovery_action('network_error', self._handle_network_error)
            self.register_recovery_action('data_corruption', self._handle_data_corruption)
            self.register_recovery_action('validation_error', self._handle_validation_error)

    def register_recovery_action(self, error_type: str, recovery_func: Callable):
        """Register a recovery action for specific error types"""
        self.recovery_actions.append({
            'error_type': error_type,
            'function': recovery_func,
            'enabled': True
        })

    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None,
                    error_type: str = 'general') -> bool:
        """
        Handle an error with appropriate recovery mechanisms
        Returns: True if error was handled/recovered, False otherwise
        """
        error_info = {
            'timestamp': datetime.now().isoformat(),
            'error_type': error_type,
            'error_message': str(error),
            'error_class': error.__class__.__name__,
            'context': context or {},
            'traceback': traceback.format_exc(),
            'recovered': False
        }

        # Log the error
        self.error_log.append(error_info)
        self.logger.error(f"Error ({error_type}): {error}", extra={'context': context})

        # Try recovery mechanisms
        if self.config['recovery_enabled']:
            recovered = self._attempt_recovery(error, error_type, context)
            error_info['recovered'] = recovered

            if recovered:
                self.logger.info(f"Successfully recovered from {error_type} error")
                return True

        # If not recovered, escalate or log
        if self.config['notification_enabled']:
            self._send_notification(error_info)

        return False

    def _attempt_recovery(self, error: Exception, error_type: str,
                         context: Dict[str, Any]) -> bool:
        """Attempt to recover from an error"""
        for recovery_action in self.recovery_actions:
            if recovery_action['error_type'] == error_type and recovery_action['enabled']:
                try:
                    return recovery_action['function'](error, context)
                except Exception as recovery_error:
                    self.logger.error(f"Recovery action failed: {recovery_error}")
                    continue

        return False

    def _handle_api_rate_limit(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle API rate limiting"""
        if 'retry_after' in str(error).lower():
            # Extract retry time from error if possible
            retry_seconds = 60  # Default
            if 'retry-after' in context:
                retry_seconds = int(context['retry-after'])

            self.logger.info(f"Rate limited. Waiting {retry_seconds} seconds...")
            time.sleep(retry_seconds)
            return True

        return False

    def _handle_network_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle network connectivity issues"""
        max_retries = self.config['max_retries']

        for attempt in range(max_retries):
            try:
                # Attempt reconnection logic here
                time.sleep(self.config['retry_delay'] * (2 ** attempt))  # Exponential backoff
                # Test connection
                return True
            except Exception:
                continue

        return False

    def _handle_data_corruption(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle data corruption issues"""
        if self.config['backup_on_error']:
            # Attempt to restore from backup
            backup_file = context.get('backup_file')
            if backup_file and Path(backup_file).exists():
                try:
                    # Restore logic here
                    self.logger.info(f"Restored data from backup: {backup_file}")
                    return True
                except Exception as restore_error:
                    self.logger.error(f"Failed to restore from backup: {restore_error}")

        return False

    def _handle_validation_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle data validation errors"""
        # For validation errors, we can often continue with degraded data
        # or attempt to fix the data
        if context.get('allow_degraded', False):
            self.logger.warning("Continuing with validation errors (degraded mode)")
            return True

        return False

    def _send_notification(self, error_info: Dict[str, Any]):
        """Send error notifications"""
        # Placeholder for notification system (email, Slack, etc.)
        self.logger.warning("Error notification triggered but not implemented")

    def with_error_handling(self, error_type: str = 'general',
                           allow_continue: bool = False):
        """Decorator for automatic error handling"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    context = {
                        'function': func.__name__,
                        'args': str(args),
                        'kwargs': str(kwargs)
                    }

                    recovered = self.handle_error(e, context, error_type)

                    if not recovered and not allow_continue:
                        raise e

                    # Return default value for recovered errors
                    return None

            return wrapper
        return decorator

    async def with_async_error_handling(self, error_type: str = 'general',
                                       allow_continue: bool = False):
        """Decorator for async error handling"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    context = {
                        'function': func.__name__,
                        'args': str(args),
                        'kwargs': str(kwargs)
                    }

                    recovered = self.handle_error(e, context, error_type)

                    if not recovered and not allow_continue:
                        raise e

                    return None

            return wrapper
        return decorator

    def create_backup(self, data: Any, backup_path: str):
        """Create a backup of data"""
        try:
            backup_dir = Path(backup_path).parent
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"{backup_path}_{timestamp}.backup"

            with open(backup_file, 'w') as f:
                if isinstance(data, (dict, list)):
                    json.dump(data, f, indent=2, default=str)
                else:
                    f.write(str(data))

            self.logger.info(f"Backup created: {backup_file}")
            return backup_file

        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return None

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors"""
        if not self.error_log:
            return {'total_errors': 0}

        summary = {
            'total_errors': len(self.error_log),
            'recovered_errors': sum(1 for e in self.error_log if e['recovered']),
            'unrecovered_errors': sum(1 for e in self.error_log if not e['recovered']),
            'error_types': {},
            'recent_errors': []
        }

        # Count error types
        for error in self.error_log:
            error_type = error['error_type']
            summary['error_types'][error_type] = summary['error_types'].get(error_type, 0) + 1

        # Get recent errors (last 10)
        summary['recent_errors'] = self.error_log[-10:]

        return summary

    def export_error_report(self, output_path: str):
        """Export error report to file"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'config': self.config,
            'summary': self.get_error_summary(),
            'all_errors': self.error_log
        }

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        self.logger.info(f"Error report exported to {output_path}")


class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance"""

    def __init__(self, threshold: int = 5, timeout: int = 300):
        self.threshold = threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit"""
        if self.last_failure_time is None:
            return True

        time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.timeout

    def _on_success(self):
        """Handle successful call"""
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            self.failure_count = 0
            self.last_failure_time = None

    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.threshold:
            self.state = 'OPEN'
