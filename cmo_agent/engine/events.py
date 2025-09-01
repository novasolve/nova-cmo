from typing import Any, Dict
import time


class CLIRenderer:
    """No-op placeholder used by unified_cli in inproc mode.
    API mode uses the Phase 0 renderer from cmo_agent.scripts.cli_run.
    """

    def __init__(self, no_emoji: bool = False):
        self.no_emoji = no_emoji
        self.start_time = time.time()

    def render_event(self, event_data: Dict[str, Any]):
        pass


class SummaryCollector:
    """Collects summary data in inproc mode."""

    def __init__(self):
        self.summary: Dict[str, Any] = {}

    def add(self, key: str, value: Any):
        self.summary[key] = value

"""
Unified event system for CLI and Web UI
Single event bus with multiple renderers
"""
from typing import Protocol, List, Dict, Any, Optional
import asyncio
import json
import time
from .types import JobEvent, RunSummary


class EventSink(Protocol):
    """Protocol for event consumers"""
    def emit(self, event: JobEvent) -> None:
        """Handle a job event"""
        ...


class MultiplexSink:
    """Multiplexes events to multiple sinks"""
    def __init__(self, sinks: List[EventSink]):
        self.sinks = sinks
    
    def emit(self, event: JobEvent) -> None:
        for sink in self.sinks:
            try:
                sink.emit(event)
            except Exception as e:
                # Don't let one sink failure break others
                print(f"EventSink error: {e}")


class CLIRenderer:
    """Renders events for CLI with beautiful TTY output"""
    
    def __init__(self, no_emoji: bool = False):
        self.no_emoji = no_emoji
        self.start_time = time.time()
        self.current_stage = ""
        
    def emit(self, event: JobEvent) -> None:
        """Render event to CLI"""
        icons = self._get_icons()
        event_type = event.type
        data = event.data
        
        if event_type == "job.started":
            goal = data.get('goal', 'Unknown goal')
            print(f"\n{icons['rocket']} Starting Campaign")
            print(f"🎯 Goal: {goal}")
            print(f"📡 Job ID: {event.job_id}")
            
        elif event_type == "tool.started":
            tool_name = data.get('tool_name', 'unknown')
            print(f"{icons['tool']} Executing: {tool_name}")
            
        elif event_type == "tool.completed":
            tool_name = data.get('tool_name', 'unknown')
            duration = data.get('duration_ms', 0)
            print(f"{icons['check']} {tool_name} completed ({duration}ms)")
            
        elif event_type == "progress":
            stage = data.get('stage', 'unknown')
            current_item = data.get('current_item', '')
            progress_pct = data.get('progress_pct', 0)
            
            # Only print stage changes to avoid spam
            if stage != self.current_stage:
                self.current_stage = stage
                print(f"\n{icons['progress']} Phase: {stage.title()}")
            
            if current_item:
                print(f"  └─ {current_item}")
                
        elif event_type == "job.completed":
            duration = time.time() - self.start_time
            print(f"\n{icons['party']} Campaign completed in {duration:.1f}s!")
            
            # Print beautiful summary if available
            summary_text = data.get('summary_text')
            if summary_text:
                print(summary_text)
            else:
                # Fallback summary
                stats = data.get('stats', {})
                print(f"{icons['chart']} Results: {json.dumps(stats, indent=2)}")
                
        elif event_type == "error":
            message = data.get('message', 'Unknown error')
            print(f"{icons['error']} Error: {message}")
    
    def _get_icons(self) -> Dict[str, str]:
        """Get icons based on emoji preference"""
        if self.no_emoji:
            return {k: "" for k in ['rocket', 'tool', 'check', 'progress', 'party', 'chart', 'error']}
        return {
            'rocket': '🚀',
            'tool': '🔧',
            'check': '✅',
            'progress': '📊',
            'party': '🎉',
            'chart': '📈',
            'error': '❌'
        }


class SSEBridge:
    """Bridges events to SSE stream for Web UI"""
    
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        
    def emit(self, event: JobEvent) -> None:
        """Send event to SSE queue"""
        try:
            # Convert to SSE format
            sse_data = f"data: {json.dumps(event.to_dict())}\n\n"
            self.queue.put_nowait(sse_data)
        except Exception as e:
            print(f"SSE Bridge error: {e}")


class SummaryCollector:
    """Collects events to build final RunSummary"""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.start_time = time.time()
        self.stats: Dict[str, Any] = {}
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.artifacts: List[Dict[str, Any]] = []
        self.final_state: Optional[Dict[str, Any]] = None
        self.completed = False
        
    def emit(self, event: JobEvent) -> None:
        """Collect event data for summary"""
        if event.type == "tool.completed":
            tool_name = event.data.get('tool_name', 'unknown')
            self.stats[f"{tool_name}_calls"] = self.stats.get(f"{tool_name}_calls", 0) + 1
            
        elif event.type == "error":
            self.errors.append(event.data.get('message', 'Unknown error'))
            
        elif event.type == "warning":
            self.warnings.append(event.data.get('message', 'Unknown warning'))
            
        elif event.type == "job.completed":
            self.completed = True
            self.final_state = event.data.get('final_state')
            
            # Extract key metrics from final state
            if self.final_state:
                repos = self.final_state.get('repos', [])
                candidates = self.final_state.get('candidates', [])
                leads = self.final_state.get('leads', [])
                to_send = self.final_state.get('to_send', [])
                
                self.stats.update({
                    'repos_found': len(repos),
                    'candidates_found': len(candidates),
                    'leads_with_emails': len([l for l in leads if l.get('email')]),
                    'emails_prepared': len(to_send)
                })
    
    def get_summary(self) -> RunSummary:
        """Build final RunSummary"""
        duration = time.time() - self.start_time
        
        return RunSummary(
            ok=self.completed and len(self.errors) == 0,
            job_id=self.job_id,
            duration_seconds=duration,
            stats=self.stats,
            warnings=self.warnings,
            errors=self.errors,
            repos_found=self.stats.get('repos_found', 0),
            candidates_found=self.stats.get('candidates_found', 0),
            leads_with_emails=self.stats.get('leads_with_emails', 0),
            emails_prepared=self.stats.get('emails_prepared', 0),
            artifacts=self.artifacts,
            final_state=self.final_state
        )


class LogSink:
    """Logs events for debugging"""
    
    def __init__(self, logger):
        self.logger = logger
        
    def emit(self, event: JobEvent) -> None:
        self.logger.debug(f"Event: {event.type} - {event.data}")
