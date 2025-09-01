"""
Beautiful logging system for CMO Agent with stage awareness, colors, and emojis.
Provides rich console output and structured file logging.
"""
import logging
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import re
import time

# Quiet noisy libraries
for noisy in ("httpx", "openai", "urllib3", "asyncio", "aiohttp"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# Quiet periodic ticks at INFO
logging.getLogger("cmo_agent.queue").setLevel(getattr(logging, os.getenv("QUEUE_STATS_LEVEL", "WARNING")))
logging.getLogger("cmo_agent.workerpool").setLevel(getattr(logging, os.getenv("WORKER_STATS_LEVEL", "WARNING")))
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Silence HTTP request logs

# Try to import tqdm for better progress bars
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Color codes for different log levels
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # Standard colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

# Stage icons and colors
STAGE_ICONS = {
    'discovery': '🔍',
    'extraction': '⚡',
    'enrichment': '💎',
    'personalization': '🎯',
    'sending': '📧',
    'validation': '✅',
    'export': '📤',
    'sync': '🔄',
    'completed': '🏁',
    'failed': '💥',
    'paused': '⏸️',
    'cancelled': '🚫',
    'started': '🚀',
    'processing': '⚙️',
    'waiting': '⏳'
}

LEVEL_ICONS = {
    'DEBUG': '🔍',
    'INFO': '✅',
    'WARNING': '⚠️',
    'ERROR': '❌',
    'CRITICAL': '💥'
}

LEVEL_COLORS = {
    'DEBUG': Colors.BRIGHT_BLACK,
    'INFO': Colors.GREEN,
    'WARNING': Colors.YELLOW,
    'ERROR': Colors.RED,
    'CRITICAL': Colors.BRIGHT_RED + Colors.BOLD
}

class BeautifulConsoleFormatter(logging.Formatter):
    """Beautiful console formatter with colors, emojis, and stage awareness"""

    def __init__(self):
        super().__init__()
        self.use_colors = self._supports_color()

    def _supports_color(self) -> bool:
        """Check if terminal supports colors"""
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False

        # Check for common terminals that support colors
        term = os.environ.get('TERM', '').lower()
        return any(x in term for x in ['color', 'ansi', 'xterm', 'linux'])

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with beautiful console output"""

        # Extract structured data if available
        structured_data = getattr(record, 'structured', {})
        metrics_data = getattr(record, 'metrics', {})
        alert_data = getattr(record, 'alert', None)

        # Determine stage and event type
        stage = self._extract_stage(record, structured_data)
        event_type = structured_data.get('event', 'general')
        job_id = structured_data.get('job_id') or structured_data.get('correlation_id')

        # Build the formatted message
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')

        # Color and icon selection
        level_color = LEVEL_COLORS.get(record.levelname, Colors.WHITE) if self.use_colors else ''
        level_icon = LEVEL_ICONS.get(record.levelname, '•')
        stage_icon = STAGE_ICONS.get(stage, '•') if stage else level_icon
        reset = Colors.RESET if self.use_colors else ''
        dim = Colors.DIM if self.use_colors else ''
        bold = Colors.BOLD if self.use_colors else ''

        # Format different types of messages
        if event_type == 'phase_start':
            return self._format_phase_start(timestamp, stage, record.getMessage(),
                                          job_id, level_color, reset, bold)
        elif event_type == 'phase_end':
            return self._format_phase_end(timestamp, stage, record.getMessage(),
                                        job_id, level_color, reset, bold, structured_data)
        elif event_type == 'progress':
            return self._format_progress(timestamp, record.getMessage(),
                                       job_id, level_color, reset, structured_data)
        elif event_type == 'error':
            return self._format_error(timestamp, record.getMessage(),
                                    job_id, level_color, reset, bold, structured_data)
        elif metrics_data:
            return self._format_metrics(timestamp, record.getMessage(),
                                      metrics_data, level_color, reset, dim)
        elif alert_data:
            return self._format_alert(timestamp, alert_data, level_color, reset, bold)
        else:
            # Standard message format
            stage_part = f"({stage})" if stage else ""
            job_part = f"[{job_id[:8]}]" if job_id else ""

            return (f"{dim}[{timestamp}]{reset} {level_color}{stage_icon} {record.levelname:<5}{reset} "
                   f"{level_color}{stage_part}{reset} {dim}{job_part}{reset} {record.getMessage()}")

    def _extract_stage(self, record: logging.LogRecord, structured_data: Dict) -> Optional[str]:
        """Extract stage information from record"""
        # Check structured data first
        stage = structured_data.get('stage') or structured_data.get('phase')
        if stage:
            return stage.lower()

        # Check logger name for stage hints
        logger_parts = record.name.split('.')
        for part in logger_parts:
            if part.lower() in STAGE_ICONS:
                return part.lower()

        # Check message content for stage keywords
        message = record.getMessage().lower()
        for stage_name in STAGE_ICONS.keys():
            if stage_name in message:
                return stage_name

        return None

    def _format_phase_start(self, timestamp: str, stage: str, message: str,
                           job_id: str, color: str, reset: str, bold: str) -> str:
        """Format phase start message"""
        stage_icon = STAGE_ICONS.get(stage, '🚀')
        job_part = f"[{job_id[:8]}]" if job_id else ""

        return (f"[{timestamp}] {color}{bold}{stage_icon} Phase: {stage.title()}{reset} "
               f"– {message} {job_part}")

    def _format_phase_end(self, timestamp: str, stage: str, message: str,
                         job_id: str, color: str, reset: str, bold: str,
                         data: Dict) -> str:
        """Format phase completion message"""
        stage_icon = '🏁'
        job_part = f"[{job_id[:8]}]" if job_id else ""

        # Add summary stats if available
        stats_parts = []
        for key in ['count', 'total', 'processed', 'found', 'sent']:
            if key in data:
                stats_parts.append(f"{key}={data[key]}")

        stats_str = f" ({', '.join(stats_parts)})" if stats_parts else ""

        return (f"[{timestamp}] {color}{bold}{stage_icon} Completed: {stage.title()}{reset} "
               f"– {message}{stats_str} {job_part}")

    def _format_progress(self, timestamp: str, message: str, job_id: str,
                        color: str, reset: str, data: Dict) -> str:
        """Format progress message with progress bar"""
        job_part = f"[{job_id[:8]}]" if job_id else ""

        # Extract progress info
        current = data.get('current', 0)
        total = data.get('total', 0)
        percentage = data.get('percentage', 0)

        if total > 0 and current > 0:
            # Create simple progress bar
            bar_width = 20
            filled = int((current / total) * bar_width)
            bar = '█' * filled + '░' * (bar_width - filled)
            progress_str = f" [{bar}] {current}/{total} ({percentage:.1f}%)"
        else:
            progress_str = ""

        return (f"[{timestamp}] {color}⚙️  PROGRESS{reset} {job_part} {message}{progress_str}")

    def _format_error(self, timestamp: str, message: str, job_id: str,
                     color: str, reset: str, bold: str, data: Dict) -> str:
        """Format error message with context"""
        job_part = f"[{job_id[:8]}]" if job_id else ""
        component = data.get('component', '')
        error_type = data.get('error_type', '')

        component_part = f"({component})" if component else ""
        error_part = f"[{error_type}]" if error_type else ""

        return (f"[{timestamp}] {color}{bold}❌ ERROR{reset} {component_part} {job_part} "
               f"{error_part} {message}")

    def _format_metrics(self, timestamp: str, message: str, metrics: Dict,
                       color: str, reset: str, dim: str) -> str:
        """Format metrics snapshot message"""
        # Extract key metrics for summary
        jobs = metrics.get('jobs', {})
        api = metrics.get('api', {})
        errors = metrics.get('errors', {})

        summary_parts = []
        if jobs.get('completed'):
            summary_parts.append(f"jobs:{jobs['completed']}")
        if api.get('calls_total'):
            summary_parts.append(f"api:{api['calls_total']}")
        if errors.get('rate_percent', 0) > 0:
            summary_parts.append(f"errors:{errors['rate_percent']:.1f}%")

        summary = f" ({', '.join(summary_parts)})" if summary_parts else ""

        return (f"{dim}[{timestamp}] 📊 METRICS{reset} {message}{summary}")

    def _format_alert(self, timestamp: str, alert: str, color: str, reset: str, bold: str) -> str:
        """Format alert message"""
        return (f"[{timestamp}] {color}{bold}⚠️  ALERT{reset} {alert}")


class JobSpecificFileHandler(logging.FileHandler):
    """File handler that creates job-specific log files"""

    def __init__(self, logs_dir: Path, job_id: str = None):
        self.logs_dir = Path(logs_dir)
        self.job_id = job_id
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Create filename based on job_id or timestamp
        if job_id:
            filename = f"{job_id}.log"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cmo_agent_{timestamp}.log"

        filepath = self.logs_dir / filename
        super().__init__(str(filepath), mode='a', encoding='utf-8')


class LiveProgressTracker:
    """Live progress tracker with email counting and tqdm-style bars"""

    def __init__(self, description: str = "", total: int = None, show_emails: bool = True, force_tqdm: bool = False):
        self.description = description
        self.total = total
        self.current = 0
        self.emails_found = 0
        self.show_emails = show_emails
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 0.1  # Update every 100ms
        self.force_tqdm = bool(force_tqdm)

        # Use tqdm if available, otherwise use simple counter
        if HAS_TQDM and (sys.stdout.isatty() or self.force_tqdm):
            if show_emails:
                self.pbar = tqdm(
                    total=total,
                    desc=description,
                    unit="items",
                    postfix={"emails": 0}
                )
            else:
                self.pbar = tqdm(
                    total=total,
                    desc=description,
                    unit="items"
                )
        else:
            self.pbar = None

    def update(self, n: int = 1, emails_delta: int = 0):
        """Update progress and email count"""
        self.current += n
        self.emails_found += emails_delta

        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return  # Throttle updates

        self.last_update = current_time

        if self.pbar:
            if self.show_emails:
                self.pbar.set_postfix(emails=self.emails_found)
            self.pbar.update(n)
        else:
            # Fallback to simple console output
            self._simple_progress_update()

    def _simple_progress_update(self):
        """Simple progress update without tqdm"""
        elapsed = time.time() - self.start_time
        rate = self.current / elapsed if elapsed > 0 else 0

        if self.total:
            percentage = (self.current / self.total) * 100
            bar_length = 30
            filled = int((self.current / self.total) * bar_length)
            bar = '█' * filled + '░' * (bar_length - filled)

            email_info = f" | Emails: {self.emails_found}" if self.show_emails else ""
            print(f"\r{self.description}: [{bar}] {self.current}/{self.total} ({percentage:.1f}%) [{rate:.1f}it/s]{email_info}", end="", flush=True)
        else:
            email_info = f" | Emails: {self.emails_found}" if self.show_emails else ""
            print(f"\r{self.description}: {self.current} [{rate:.1f}it/s]{email_info}", end="", flush=True)

    def set_description(self, description: str):
        """Update the progress bar description"""
        self.description = description
        if self.pbar:
            self.pbar.set_description(description)

    def set_total(self, total: int):
        """Update the total count"""
        self.total = total
        if self.pbar:
            self.pbar.total = total

    def close(self):
        """Close the progress bar"""
        if self.pbar:
            self.pbar.close()
        else:
            print()  # New line after progress


class StageAwareLogger:
    """Logger that automatically tracks and logs pipeline stages"""

    def __init__(self, logger: logging.Logger, job_id: str = None):
        self.logger = logger
        self.job_id = job_id
        self.current_stage = None
        self.stage_start_time = None
        self.stage_counters = {}
        self.progress_tracker = None
        # Optional: path to the job-specific log file (when available)
        self.log_file_path = None

    def start_stage(self, stage: str, message: str = None, **kwargs):
        """Log the start of a pipeline stage"""
        if self.current_stage:
            self.end_stage(f"Interrupted by {stage}")

        self.current_stage = stage
        self.stage_start_time = datetime.now()
        self.stage_counters[stage] = self.stage_counters.get(stage, 0) + 1

        default_message = f"Starting {stage} phase"
        log_message = message or default_message

        structured_data = {
            'event': 'phase_start',
            'stage': stage,
            'job_id': self.job_id,
            'stage_count': self.stage_counters[stage],
            **kwargs
        }

        self.logger.info(log_message, extra={'structured': structured_data})

    def end_stage(self, message: str = None, **kwargs):
        """Log the end of the current pipeline stage"""
        if not self.current_stage:
            return

        # Close any active progress tracker
        if self.progress_tracker:
            self.progress_tracker.close()
            self.progress_tracker = None

        duration = (datetime.now() - self.stage_start_time).total_seconds() if self.stage_start_time else 0

        default_message = f"{self.current_stage} phase completed"
        log_message = message or default_message

        structured_data = {
            'event': 'phase_end',
            'stage': self.current_stage,
            'job_id': self.job_id,
            'duration_seconds': duration,
            **kwargs
        }

        self.logger.info(log_message, extra={'structured': structured_data})

        self.current_stage = None
        self.stage_start_time = None

    def start_progress(self, description: str, total: int = None, show_emails: bool = True) -> LiveProgressTracker:
        """Start a live progress tracker"""
        if self.progress_tracker:
            self.progress_tracker.close()

        # Allow forcing tqdm even in non-TTY environments via config
        force_tqdm = getattr(self, "force_tqdm", False)
        self.progress_tracker = LiveProgressTracker(description, total, show_emails, force_tqdm=force_tqdm)
        return self.progress_tracker

    def update_progress(self, n: int = 1, emails_delta: int = 0):
        """Update the current progress tracker"""
        if self.progress_tracker:
            self.progress_tracker.update(n, emails_delta)

    def close_progress(self):
        """Close the current progress tracker"""
        if self.progress_tracker:
            self.progress_tracker.close()
            self.progress_tracker = None

    def log_progress(self, message: str, current: int = None, total: int = None, **kwargs):
        """Log progress within the current stage"""
        percentage = (current / total * 100) if (current is not None and total and total > 0) else 0

        structured_data = {
            'event': 'progress',
            'stage': self.current_stage,
            'job_id': self.job_id,
            'current': current,
            'total': total,
            'percentage': percentage,
            **kwargs
        }

        self.logger.info(message, extra={'structured': structured_data})

    def log_stage_event(self, event: str, message: str, **kwargs):
        """Log a general event within the current stage"""
        structured_data = {
            'event': event,
            'stage': self.current_stage,
            'job_id': self.job_id,
            **kwargs
        }

        self.logger.info(message, extra={'structured': structured_data})

    def log_error(self, error: Exception, component: str, **kwargs):
        """Log an error with stage context"""
        structured_data = {
            'event': 'error',
            'stage': self.current_stage,
            'job_id': self.job_id,
            'component': component,
            'error_type': type(error).__name__,
            'error_message': str(error),
            **kwargs
        }

        self.logger.error(f"Error in {component}: {error}", extra={'structured': structured_data})

    def write_summary_header(self, title: str, summary_lines: List[str]):
        """Prepend a summary header to the job-specific log file, if available.

        This creates a readable banner at the very top of the log with key results.
        Safe no-op if file path is unknown or not writable.
        """
        try:
            if not self.log_file_path:
                return
            path = Path(self.log_file_path)
            if not path.exists():
                return
            header = [
                "# " + title,
                "",
            ] + summary_lines + ["", "---", ""]
            prefix = "\n".join(header)
            original = path.read_text(encoding='utf-8')
            path.write_text(prefix + original, encoding='utf-8')
        except Exception:
            # Best-effort; do not crash logging on failure to prepend
            pass


def setup_beautiful_logging(config: Dict[str, Any], job_id: str = None) -> StageAwareLogger:
    """Setup beautiful logging system with both console and file handlers"""

    # Get logging configuration
    log_config = config.get('logging', {})
    log_level = log_config.get('level', 'INFO').upper()
    logs_dir = Path(config.get('directories', {}).get('logs', './logs'))

    # Create main logger
    logger_name = f"cmo.{job_id}" if job_id else "cmo"
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler with beautiful formatting
    if log_config.get('console', True):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level, logging.INFO))
        console_handler.setFormatter(BeautifulConsoleFormatter())
        logger.addHandler(console_handler)

    # File handler - job-specific or general
    if log_config.get('file', True):
        if job_id and log_config.get('job_specific_files', True):
            file_handler = JobSpecificFileHandler(logs_dir, job_id)
            job_log_path = logs_dir / f"{job_id}.log"
        else:
            logs_dir.mkdir(parents=True, exist_ok=True)
            general_log_file = logs_dir / log_config.get('filename', 'cmo_agent.jsonl')
            file_handler = logging.FileHandler(str(general_log_file), mode='a', encoding='utf-8')
            job_log_path = None

        file_handler.setLevel(getattr(logging, log_level, logging.INFO))

        # Use JSON formatter for file output
        from ..core.monitoring import JsonExtraFormatter
        file_handler.setFormatter(JsonExtraFormatter())
        logger.addHandler(file_handler)

    # Return stage-aware logger wrapper
    stage_logger = StageAwareLogger(logger, job_id)
    # Propagate force_tqdm flag from config if provided
    try:
        stage_logger.force_tqdm = bool(log_config.get('force_tqdm', False))
    except Exception:
        pass
    # Attach file path if we have a job-specific file
    try:
        if job_id and log_config.get('file', True) and log_config.get('job_specific_files', True):
            stage_logger.log_file_path = str(logs_dir / f"{job_id}.log")
    except Exception:
        pass
    return stage_logger


# Convenience function for backward compatibility
def get_beautiful_logger(job_id: str = None, config: Dict[str, Any] = None) -> StageAwareLogger:
    """Get a beautiful logger instance"""
    if config is None:
        from ..core.state import DEFAULT_CONFIG
        config = DEFAULT_CONFIG

    return setup_beautiful_logging(config, job_id)
