#!/usr/bin/env python3
"""
Beautiful Logging System
Enhanced logging with colors, icons, progress bars, and visual formatting
"""

import logging
import sys
from typing import Optional, Any
from datetime import datetime
import colorama
from colorama import Fore, Back, Style, init

# Initialize colorama
init(autoreset=True)


class BeautifulFormatter(logging.Formatter):
    """Beautiful log formatter with colors and styling"""

    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'SUCCESS': Fore.GREEN + Style.BRIGHT,
        'WARNING': Fore.YELLOW + Style.BRIGHT,
        'ERROR': Fore.RED + Style.BRIGHT,
        'CRITICAL': Fore.RED + Back.WHITE + Style.BRIGHT
    }

    ICONS = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'SUCCESS': '✅',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨',
        'PHASE': '🚀',
        'START': '🎯',
        'END': '🏁',
        'DATA': '📊',
        'ENRICH': '🔍',
        'SCORE': '🎯',
        'PERSONALIZE': '🎨',
        'EXPORT': '📤',
        'CRM': '🔗',
        'API': '🌐',
        'CACHE': '💾',
        'PROGRESS': '📈'
    }

    def format(self, record):
        # Add color and icon
        if hasattr(record, 'icon'):
            icon = record.icon
        else:
            icon = self.ICONS.get(record.levelname, '📝')

        color = self.COLORS.get(record.levelname, Fore.WHITE)

        # Format timestamp beautifully
        dt = datetime.fromtimestamp(record.created)
        timestamp = f"{Fore.BLUE}{dt.strftime('%H:%M:%S')}{Style.RESET_ALL}"

        # Format level with color
        level = f"{color}{record.levelname:>8}{Style.RESET_ALL}"

        # Format module with truncation
        module_name = record.name.split('.')[-1]
        module = f"{Fore.MAGENTA}{module_name[:12]:>12}{Style.RESET_ALL}"

        # Format message with potential enhancements
        message = record.getMessage()

        # Add visual separators for important messages
        if hasattr(record, 'separator') and record.separator:
            separator = "═" * 80
            return f"\n{Fore.CYAN}{separator}{Style.RESET_ALL}\n{timestamp} {icon} {level} {module} {message}\n{Fore.CYAN}{separator}{Style.RESET_ALL}"

        return f"{timestamp} {icon} {level} {module} {message}"


class BeautifulLogger:
    """Enhanced logger with beautiful formatting and progress tracking"""

    def __init__(self, name: str = 'lead_intelligence'):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Add beautiful console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(BeautifulFormatter())
        self.logger.addHandler(console_handler)

        # Suppress noisy loggers
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('tqdm').setLevel(logging.WARNING)

    def phase_start(self, phase_name: str, description: str = ""):
        """Log the start of a pipeline phase with visual flair"""
        message = f"🚀 Phase: {phase_name}"
        if description:
            message += f" - {description}"
        self._log_with_icon('INFO', message, 'PHASE', separator=True)

    def phase_end(self, phase_name: str, stats: Optional[dict] = None):
        """Log the end of a pipeline phase with statistics"""
        message = f"🏁 Completed: {phase_name}"
        if stats:
            stat_parts = []
            for key, value in stats.items():
                if isinstance(value, float):
                    stat_parts.append(f"{key}: {value:.1f}")
                else:
                    stat_parts.append(f"{key}: {value}")
            message += f" ({', '.join(stat_parts)})"
        self._log_with_icon('SUCCESS', message, 'END')

    def progress(self, message: str, current: Optional[int] = None, total: Optional[int] = None):
        """Log progress updates"""
        if current is not None and total is not None:
            percentage = (current / total) * 100 if total > 0 else 0
            message = f"{message} ({current}/{total}, {percentage:.1f}%)"
        self._log_with_icon('INFO', message, 'PROGRESS')

    def data_stats(self, data_type: str, count: int, details: Optional[dict] = None):
        """Log data processing statistics"""
        message = f"📊 {data_type}: {count:,} items"
        if details:
            detail_parts = []
            for key, value in details.items():
                if isinstance(value, float):
                    detail_parts.append(f"{key}: {value:.2f}")
                else:
                    detail_parts.append(f"{key}: {value}")
            message += f" ({', '.join(detail_parts)})"
        self._log_with_icon('INFO', message, 'DATA')

    def api_call(self, endpoint: str, status: str = "success", details: Optional[dict] = None):
        """Log API call results"""
        if status == "success":
            message = f"🌐 API: {endpoint}"
        else:
            message = f"❌ API: {endpoint} - {status}"

        if details:
            detail_parts = []
            for key, value in details.items():
                detail_parts.append(f"{key}: {value}")
            message += f" ({', '.join(detail_parts)})"

        self._log_with_icon('SUCCESS' if status == "success" else 'ERROR', message, 'API')

    def cache_hit(self, cache_key: str, hit: bool = True):
        """Log cache operations"""
        status = "HIT" if hit else "MISS"
        icon = "💾" if hit else "🔄"
        self._log_with_icon('INFO', f"Cache {status}: {cache_key}", 'CACHE')

    def enrichment_complete(self, repo: str, fields_enriched: list):
        """Log successful repository enrichment"""
        message = f"🔍 Enriched: {repo} ({len(fields_enriched)} fields)"
        self._log_with_icon('SUCCESS', message, 'ENRICH')

    def scoring_complete(self, leads_scored: int, high_priority: int, low_risk: int):
        """Log scoring results"""
        message = f"🎯 Scored: {leads_scored:,} leads"
        if high_priority > 0 or low_risk > 0:
            message += f" (High priority: {high_priority}, Low risk: {low_risk})"
        self._log_with_icon('SUCCESS', message, 'SCORE')

    def personalization_complete(self, briefs_generated: int, cohorts: list):
        """Log personalization results"""
        message = f"🎨 Generated: {briefs_generated:,} briefs"
        if cohorts:
            message += f" ({len(cohorts)} cohorts)"
        self._log_with_icon('SUCCESS', message, 'PERSONALIZE')

    def export_complete(self, export_type: str, files: list, record_count: int):
        """Log export completion"""
        message = f"📤 Exported: {record_count:,} records to {len(files)} {export_type} files"
        self._log_with_icon('SUCCESS', message, 'EXPORT')

    def crm_sync(self, system: str, records_synced: int, errors: int = 0):
        """Log CRM synchronization results"""
        message = f"🔗 {system}: Synced {records_synced:,} records"
        if errors > 0:
            message += f" ({errors} errors)"
        status = 'SUCCESS' if errors == 0 else 'WARNING'
        self._log_with_icon(status, message, 'CRM')

    def pipeline_summary(self, stats: dict):
        """Log beautiful pipeline summary"""
        print(f"\n{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'🏆 PIPELINE COMPLETE'}{Style.RESET_ALL}".center(80))
        print(f"{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}")

        for key, value in stats.items():
            if isinstance(value, float):
                print(f"{Fore.WHITE}  • {key.replace('_', ' ').title()}: {Fore.YELLOW}{value:,.1f}{Style.RESET_ALL}")
            else:
                print(f"{Fore.WHITE}  • {key.replace('_', ' ').title()}: {Fore.YELLOW}{value:,}{Style.RESET_ALL}")

        print(f"{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}\n")

    def error_banner(self, error_type: str, message: str):
        """Log error with visual banner"""
        print(f"\n{Fore.RED}{'═' * 80}{Style.RESET_ALL}")
        print(f"{Fore.RED}{error_type.upper()}{Style.RESET_ALL}".center(80))
        print(f"{Fore.RED}{message}{Style.RESET_ALL}".center(80))
        print(f"{Fore.RED}{'═' * 80}{Style.RESET_ALL}\n")

    def _log_with_icon(self, level: str, message: str, icon_key: str = None, separator: bool = False):
        """Internal method to log with custom icon"""
        # Create a log record with custom attributes
        record = logging.LogRecord(
            name=self.logger.name,
            level=getattr(logging, level),
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        )

        if icon_key:
            record.icon = BeautifulFormatter.ICONS.get(icon_key, '📝')
        if separator:
            record.separator = True

        self.logger.handle(record)


# Global logger instance
beautiful_logger = BeautifulLogger()


def create_progress_bar(iterable, desc="Processing", unit="items", color="green"):
    """Create a beautiful progress bar"""
    try:
        from tqdm import tqdm
        return tqdm(
            iterable,
            desc=f"{Fore.GREEN}{desc}{Style.RESET_ALL}",
            unit=unit,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            colour=color,
            ncols=80
        )
    except ImportError:
        # Fallback if tqdm not available
        return iterable


def log_separator(title: str = "", char: str = "═", length: int = 80):
    """Print a beautiful separator line"""
    if title:
        side_len = (length - len(title) - 2) // 2
        separator = char * side_len + " " + title + " " + char * side_len
        if len(separator) < length:
            separator += char * (length - len(separator))
    else:
        separator = char * length

    print(f"{Fore.CYAN}{separator}{Style.RESET_ALL}")


def log_header(title: str):
    """Print a beautiful header"""
    log_separator()
    print(f"{Fore.GREEN}{title.upper()}{Style.RESET_ALL}".center(80))
    log_separator()


def log_success(message: str):
    """Log success message with green color and checkmark"""
    print(f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}")


def log_warning(message: str):
    """Log warning message with yellow color and warning icon"""
    print(f"{Fore.YELLOW}⚠️  {message}{Style.RESET_ALL}")


def log_error(message: str):
    """Log error message with red color and X mark"""
    print(f"{Fore.RED}❌ {message}{Style.RESET_ALL}")


def log_info(message: str):
    """Log info message with blue color and info icon"""
    print(f"{Fore.BLUE}ℹ️  {message}{Style.RESET_ALL}")
