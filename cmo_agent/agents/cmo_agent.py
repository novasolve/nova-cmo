"""
Main CMO Agent - LangGraph orchestration for outbound campaigns
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

import sys
import os
from pathlib import Path

# Add current directory and parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
cmo_agent_dir = parent_dir
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if cmo_agent_dir not in sys.path:
    sys.path.insert(0, cmo_agent_dir)

try:
    from ..core.state import RunState, JobMetadata, DEFAULT_CONFIG
    from ..obs.beautiful_logging import setup_beautiful_logging, StageAwareLogger
    from ..tools.github import SearchGitHubRepos, ExtractPeople, EnrichGitHubUser, FindCommitEmails, EnrichGitHubUsers, FindCommitEmailsBatch
    from ..tools.hygiene import MXCheck, ICPScores
    from ..tools.personalization import RenderCopy, SendInstantly
    from ..tools.crm import SyncAttio, SyncLinear
    from ..tools.export import ExportCSV, Done
    from ..tools.base import ToolResult
except ImportError:
    # Handle relative import issues when running as standalone
    try:
        from core.state import RunState, JobMetadata, DEFAULT_CONFIG
        from obs.beautiful_logging import setup_beautiful_logging, StageAwareLogger
        from tools.github import SearchGitHubRepos, ExtractPeople, EnrichGitHubUser, FindCommitEmails, EnrichGitHubUsers, FindCommitEmailsBatch
        from tools.hygiene import MXCheck, ICPScores
        from tools.personalization import RenderCopy, SendInstantly
        from tools.crm import SyncAttio, SyncLinear
        from tools.export import ExportCSV, Done
        from tools.base import ToolResult
    except ImportError:
        # Create minimal fallback classes for testing
        from typing import Dict, Any, List

        class ToolResult:
            def __init__(self, success: bool, data: Any = None, error: str = None, metadata: Dict = None):
                self.success = success
                self.data = data or {}
                self.error = error
                self.metadata = metadata or {}

            def to_dict(self) -> Dict[str, Any]:
                return {
                    "success": self.success,
                    "data": self.data,
                    "error": self.error,
                    "metadata": self.metadata,
                }

        # Mock classes for testing
        class RunState(dict):
            pass

        class JobMetadata:
            def __init__(self, goal: str, created_by: str = "user"):
                self.job_id = f"cmo-test-{hash(goal) % 10000}"
                self.goal = goal
                self.created_at = "2024-01-01T00:00:00"
                self.created_by = created_by

            def to_dict(self) -> Dict[str, Any]:
                return {
                    "job_id": self.job_id,
                    "goal": self.goal,
                    "created_at": self.created_at,
                    "created_by": self.created_by,
                }

        DEFAULT_CONFIG = {}

        # Mock tool classes
        class SearchGitHubRepos:
            def __init__(self, token): pass
            async def execute(self, **kwargs): return ToolResult(True)

        class ExtractPeople:
            def __init__(self, token): pass
            async def execute(self, **kwargs): return ToolResult(True)

        class EnrichGitHubUser:
            def __init__(self, token): pass
            async def execute(self, **kwargs): return ToolResult(True)

        class FindCommitEmails:
            def __init__(self, token): pass
            async def execute(self, **kwargs): return ToolResult(True)

        class EnrichGitHubUsers:
            def __init__(self, token): pass
            async def execute(self, **kwargs): return ToolResult(True)

        class FindCommitEmailsBatch:
            def __init__(self, token): pass
            async def execute(self, **kwargs): return ToolResult(True)

        class MXCheck:
            async def execute(self, **kwargs): return ToolResult(True)

        class ICPScores:
            async def execute(self, **kwargs): return ToolResult(True)

        class RenderCopy:
            async def execute(self, **kwargs): return ToolResult(True)

        class SendInstantly:
            def __init__(self, token): pass
            async def execute(self, **kwargs): return ToolResult(True)

        class SyncAttio:
            def __init__(self, api_key, workspace_id): pass
            async def execute(self, **kwargs): return ToolResult(True)

        class SyncLinear:
            def __init__(self, token): pass
            async def execute(self, **kwargs): return ToolResult(True)

        class ExportCSV:
            def __init__(self, export_dir="./exports"): pass
            async def execute(self, **kwargs): return ToolResult(True)

        class Done:
            async def execute(self, **kwargs): return ToolResult(True, data={"completed_at": "2024-01-01T00:00:00"})

logger = logging.getLogger(__name__)


class CMOAgent:
    """Main CMO Agent class that orchestrates the entire outbound campaign pipeline"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or DEFAULT_CONFIG.copy()

        # Normalize directories: default to cmo_agent/* to keep paths consistent
        try:
            pkg_dir = Path(__file__).resolve().parents[1]  # cmo_agent/
            dirs = dict(self.config.get("directories", {}))
            dirs.setdefault("checkpoints", str((pkg_dir / "checkpoints").resolve()))
            dirs.setdefault("exports", str((pkg_dir / "exports").resolve()))
            dirs.setdefault("logs", str((pkg_dir / "logs").resolve()))
            dirs.setdefault("artifacts", str((pkg_dir / "artifacts").resolve()))
            self.config["directories"] = dirs
        except Exception:
            # Fall back silently if path resolution fails
            pass
        # Initialize all tools first
        self.tools = self._initialize_tools()

        # Create tool schemas for binding to LLM
        tool_schemas = self._create_tool_schemas()

        # Initialize LLM with tool binding
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",  # Could be upgraded to gpt-5 when available
            temperature=0.0,  # Deterministic for reliability
        )

        # Bind tools to LLM
        if tool_schemas:
            self.llm = self.llm.bind_tools(tool_schemas)

        # Build LangGraph
        self.graph = self._build_graph()

        # Statistics
        self.stats = {
            "jobs_processed": 0,
            "tools_executed": 0,
            "errors_encountered": 0,
        }

        # Pause/Resume state management
        self._pause_requested = False
        self._job_states = {}  # job_id -> saved state for resume

        # Error handling and retry logic
        from ..core.state import ErrorHandler
        self.error_handler = ErrorHandler(self.config)

        # Artifact management
        from ..core.artifacts import get_artifact_manager
        self.artifact_manager = get_artifact_manager(self.config)

    def request_pause(self, job_id: str):
        """Request to pause a running job"""
        logger.info(f"Pause requested for job {job_id}")
        self._pause_requested = True

    def request_resume(self, job_id: str):
        """Request to resume a paused job"""
        logger.info(f"Resume requested for job {job_id}")
        self._pause_requested = False

    def save_job_state(self, job_id: str, state: RunState):
        """Save job state for potential resume"""
        logger.info(f"Saving state for job {job_id}")
        self._job_states[job_id] = state

    def get_job_state(self, job_id: str) -> Optional[RunState]:
        """Get saved job state for resume"""
        return self._job_states.get(job_id)

    def clear_job_state(self, job_id: str):
        """Clear saved job state"""
        self._job_states.pop(job_id, None)

    def is_pause_requested(self) -> bool:
        """Check if pause has been requested"""
        return self._pause_requested

    def _create_tool_schemas(self) -> List[Dict[str, Any]]:
        """Create tool schemas for LLM binding"""
        tool_schemas = []

        # GitHub tools
        tool_schemas.extend([
            {
                "name": "search_github_repos",
                "description": "Search GitHub repositories by query and return matching repos. Use this first to find repositories.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "q": {
                            "type": "string",
                            "description": "Search query (e.g., 'python CI testing')"
                        },
                        "max_repos": {
                            "type": "integer",
                            "description": "Maximum number of repos to return",
                            "default": 200
                        }
                    },
                    "required": ["q"]
                }
            },
            {
                "name": "extract_people",
                "description": "Extract top contributors from GitHub repositories. Use after finding repos.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repos": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of repository objects from search_github_repos"
                        },
                        "top_authors_per_repo": {
                            "type": "integer",
                            "description": "Number of top contributors per repo",
                            "default": 5
                        }
                    },
                    "required": ["repos"]
                }
            },
            {
                "name": "enrich_github_users",
                "description": "Get detailed GitHub user profiles for multiple users. Use this for batch enrichment.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "logins": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of GitHub usernames to enrich"
                        }
                    },
                    "required": ["logins"]
                }
            },
            {
                "name": "find_commit_emails_batch",
                "description": "Find email addresses from multiple users' commit history. Use after enrichment.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_repo_pairs": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of objects with 'login' and 'repo_full_name' fields"
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to look back in commit history",
                            "default": 90
                        }
                    },
                    "required": ["user_repo_pairs"]
                }
            }
        ])

        # Hygiene tools
        tool_schemas.extend([
            {
                "name": "mx_check",
                "description": "Validate email domains by checking MX records. Use after finding emails.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "emails": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of email addresses to validate"
                        }
                    },
                    "required": ["emails"]
                }
            },
            {
                "name": "score_icp",
                "description": "Score prospects against ICP criteria. Use after enrichment.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "profile": {
                            "type": "object",
                            "description": "User profile object from enrichment"
                        }
                    },
                    "required": ["profile"]
                }
            }
        ])

        # Personalization tools
        tool_schemas.extend([
            {
                "name": "render_copy",
                "description": "Render personalized email copy using templates. Use after enrichment.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lead": {
                            "type": "object",
                            "description": "Lead profile object"
                        }
                    },
                    "required": ["lead"]
                }
            },
            {
                "name": "send_instantly",
                "description": "Send personalized emails via Instantly API. Use after copy rendering.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contacts": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of contact objects with email and personalization data"
                        },
                        "seq_id": {
                            "type": "string",
                            "description": "Instantly sequence ID"
                        },
                        "per_inbox_cap": {
                            "type": "integer",
                            "description": "Maximum contacts per inbox",
                            "default": 50
                        }
                    },
                    "required": ["contacts", "seq_id"]
                }
            }
        ])

        # CRM tools
        tool_schemas.extend([
            {
                "name": "sync_attio",
                "description": "Sync people data to Attio CRM. Use after email validation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "people": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of person objects to sync"
                        },
                        "list_id": {
                            "type": "string",
                            "description": "Attio list ID to add people to"
                        }
                    },
                    "required": ["people", "list_id"]
                }
            },
            {
                "name": "sync_linear",
                "description": "Create Linear issues for tracking. Use for errors or follow-ups.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parent_title": {
                            "type": "string",
                            "description": "Title for the parent issue"
                        },
                        "events": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of event objects to create issues for"
                        }
                    },
                    "required": ["parent_title", "events"]
                }
            }
        ])

        # Export tools
        tool_schemas.extend([
            {
                "name": "export_csv",
                "description": "Export data to CSV format. Use near the end of the campaign.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rows": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of data rows to export"
                        },
                        "path": {
                            "type": "string",
                            "description": "Output file path",
                            "default": "leads.csv"
                        }
                    },
                    "required": ["rows"]
                }
            },
            {
                "name": "done",
                "description": "Signal job completion with summary. Call this when the campaign is finished.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Summary of what was accomplished"
                        }
                    },
                    "required": ["summary"]
                }
            }
        ])

        return tool_schemas

    async def _validate_github_token(self) -> None:
        """Validate GitHub token with a simple API call"""
        if not self.config.get("GITHUB_TOKEN"):
            raise ValueError("GITHUB_TOKEN is required but not provided")
        
        import aiohttp
        token = self.config["GITHUB_TOKEN"]
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "CMO-Agent/1.0"
                }
                
                # Test with a simple rate limit check call
                async with session.get("https://api.github.com/rate_limit", headers=headers) as response:
                    if response.status == 401:
                        raise ValueError(f"GitHub authentication failed: Invalid token. Please check your GITHUB_TOKEN.")
                    elif response.status == 403:
                        raise ValueError(f"GitHub authentication failed: Access forbidden. Token may lack required permissions.")
                    elif response.status != 200:
                        raise ValueError(f"GitHub API error: HTTP {response.status}")
                    
                    # Check if we have any remaining requests
                    data = await response.json()
                    remaining = data.get("rate", {}).get("remaining", 0)
                    if remaining == 0:
                        reset_time = data.get("rate", {}).get("reset", 0)
                        logger.warning(f"GitHub API rate limit exhausted. Resets at {reset_time}")
                    else:
                        logger.info(f"GitHub API validated successfully. {remaining} requests remaining.")
                        
        except aiohttp.ClientError as e:
            raise ValueError(f"GitHub API connection failed: {e}")
        except Exception as e:
            if "Invalid token" in str(e) or "authentication failed" in str(e):
                raise e
            raise ValueError(f"GitHub token validation failed: {e}")

    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize all tools with configuration"""
        tools = {}

        # GitHub tools
        if self.config.get("GITHUB_TOKEN"):
            tools["search_github_repos"] = SearchGitHubRepos(self.config["GITHUB_TOKEN"])
            tools["extract_people"] = ExtractPeople(self.config["GITHUB_TOKEN"])
            tools["enrich_github_user"] = EnrichGitHubUser(self.config["GITHUB_TOKEN"])
            tools["find_commit_emails"] = FindCommitEmails(self.config["GITHUB_TOKEN"])
            # Add batched versions for efficiency
            tools["enrich_github_users"] = EnrichGitHubUsers(self.config["GITHUB_TOKEN"])
            tools["find_commit_emails_batch"] = FindCommitEmailsBatch(self.config["GITHUB_TOKEN"])

        # Hygiene tools
        tools["mx_check"] = MXCheck()
        tools["score_icp"] = ICPScores()

        # Personalization tools
        tools["render_copy"] = RenderCopy()
        if self.config.get("INSTANTLY_API_KEY"):
            tools["send_instantly"] = SendInstantly(self.config["INSTANTLY_API_KEY"])

        # CRM tools
        # Attio: prefer access token, fall back to legacy API key for compatibility
        attio_token = self.config.get("ATTIO_ACCESS_TOKEN") or self.config.get("ATTIO_API_KEY")
        if attio_token and self.config.get("ATTIO_WORKSPACE_ID"):
            tools["sync_attio"] = SyncAttio(
                attio_token,
                self.config["ATTIO_WORKSPACE_ID"]
            )

        if self.config.get("LINEAR_API_KEY"):
            tools["sync_linear"] = SyncLinear(self.config["LINEAR_API_KEY"])

        # Export tools: honor directories.exports for consistency with JSON artifacts
        try:
            exports_dir = (
                self.config.get("directories", {}).get("exports")
                or self.config.get("EXPORT_DIR")
                or "./exports"
            )
        except Exception:
            exports_dir = self.config.get("EXPORT_DIR", "./exports")
        tools["export_csv"] = ExportCSV(exports_dir)
        tools["done"] = Done()

        return tools

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        from langgraph.graph import END

        # Create simple workflow - agent executes tools directly
        workflow = StateGraph(RunState)

        # Add main agent node (handles both reasoning and tool execution)
        workflow.add_node("agent", self._agent_step)

        # Set entry point
        workflow.set_entry_point("agent")

        # Simple conditional: continue until done or max steps reached
        def should_end(state: RunState) -> str:
            if state.get("ended") or state.get("counters", {}).get("steps", 0) >= self.config.get("max_steps", 40):
                return END
            return "agent"

        workflow.add_conditional_edges("agent", should_end)

        # Compile without any checkpointer or config
        return workflow.compile()

    async def _agent_step(self, state: RunState) -> Dict[str, Any]:
        """Main agent step - decides what tool to use next and executes it"""
        tool_calls = []  # Initialize to avoid scoping issues

        try:
            # Build system prompt
            system_prompt = self._build_system_prompt(state)

            # Build conversation history
            messages = [SystemMessage(content=system_prompt)]

            # Add conversation history if available
            if state.get("history"):
                for msg in state["history"]:
                    if msg.get("type") == "human":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg.get("type") == "ai":
                        messages.append(SystemMessage(content=msg["content"]))

            # Add current goal as human message
            messages.append(HumanMessage(content=state["goal"]))

            # Get LLM response with timeout to avoid hangs
            llm_timeout = (
                self.config.get("timeouts", {}).get("openai_llm")
                if isinstance(self.config.get("timeouts"), dict)
                else None
            ) or 60
            try:
                response = await asyncio.wait_for(self.llm.ainvoke(messages), timeout=llm_timeout)
            except asyncio.TimeoutError:
                logger.error(f"LLM timed out after {llm_timeout}s; continuing with auto-progression")
                state.setdefault("errors", []).append({
                    "stage": "agent_step",
                    "error": f"LLM timeout after {llm_timeout}s",
                    "error_type": "TimeoutError",
                    "timestamp": datetime.now().isoformat(),
                })
                # Bump step counter and fall through to auto-progression block
                state.setdefault("counters", {})
                state["counters"]["steps"] = state["counters"].get("steps", 0) + 1
                response = type("Resp", (), {"content": "", "tool_calls": []})()

            # Parse tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_calls = response.tool_calls

            # Update state with response
            state.setdefault("history", []).append({
                "type": "ai",
                "content": response.content,
                "tool_calls": [call.dict() if hasattr(call, 'dict') else call for call in tool_calls],
                "timestamp": datetime.now().isoformat(),
            })

            # Safeguard against repeated no-tool-call responses
            if not tool_calls:
                state.setdefault("counters", {})
                state["counters"]["no_tool_call_streak"] = state["counters"].get("no_tool_call_streak", 0) + 1
                limit = self.config.get("no_tool_call_limit", 3)

                if state["counters"]["no_tool_call_streak"] >= limit:
                    logger.warning(f"No tool calls for {state['counters']['no_tool_call_streak']} steps; marking job failed.")
                    state.setdefault("errors", []).append({
                        "stage": "agent_step",
                        "error": "No tool calls from LLM for consecutive iterations",
                        "error_type": "NoToolCalls",
                        "timestamp": datetime.now().isoformat(),
                        "critical": True,
                        "streak": state["counters"]["no_tool_call_streak"],
                    })
                    state["ended"] = True
                    state["current_stage"] = "failed"
                    state["end_reason"] = "no_tool_calls_limit"
                    return state  # stop further processing immediately
                else:
                    logger.info("No tool calls, continuing (auto-progress if enabled)")

                # Update step counter and return early
                state.setdefault("counters", {})
                state["counters"]["steps"] = state["counters"].get("steps", 0) + 1
                return state

            # Reset the no-tool-call streak on valid tool calls
            state.setdefault("counters", {})
            if state["counters"].get("no_tool_call_streak"):
                state["counters"]["no_tool_call_streak"] = 0

            # Execute tool calls directly in the agent step
            for call in tool_calls:
                tool_name = call.get("name")
                if tool_name and tool_name in self.tools:
                    logger.info(f"Executing tool: {tool_name}")
                    try:
                        start_ts = datetime.now()
                        tool = self.tools[tool_name]
                        # Hydrate missing or unsafe args from state for robustness
                        raw_args = call.get("args", {})
                        hydrated_args, hydration_note = self._hydrate_tool_args(tool_name, raw_args, state)
                        if hydration_note:
                            state.setdefault("history", []).append({
                                "type": "ai",
                                "content": hydration_note,
                                "timestamp": datetime.now().isoformat(),
                            })

                        # If we cannot safely hydrate required args, skip executing this tool
                        if hydrated_args is None:
                            logger.info(f"Skipping tool {tool_name} due to insufficient arguments after hydration")
                            continue

                        # Add beautiful_logger to tool execution for tqdm progress bars
                        if hasattr(self, 'beautiful_logger') and self.beautiful_logger:
                            hydrated_args['beautiful_logger'] = self.beautiful_logger

                        result = await tool.execute(**hydrated_args)

                        # Store result
                        state = self._reduce_tool_result(state, tool_name, result)
                        self.stats["tools_executed"] += 1

                        duration_ms = int((datetime.now() - start_ts).total_seconds() * 1000)
                        logger.info(f"Tool {tool_name} executed successfully in {duration_ms}ms")

                        # Append a function-style summary to conversation history for LLM awareness
                        try:
                            summary_msg = self._summarize_tool_result(tool_name, result, state)
                            if summary_msg:
                                state.setdefault("history", []).append({
                                    "type": "ai",
                                    "content": summary_msg,
                                    "timestamp": datetime.now().isoformat(),
                                })
                        except Exception:
                            # Non-fatal if summarization fails
                            pass

                        # Check if this is the done tool
                        if tool_name == "done":
                            state["ended"] = True
                            logger.info("Done tool called - ending workflow")
                            break

                    except Exception as e:
                        logger.error(f"Tool {tool_name} execution failed: {e}")
                        
                        # Check if this is a GitHub authentication error - fail fast
                        error_str = str(e).lower()
                        if ("github authentication failed" in error_str or 
                            "invalid or expired token" in error_str or
                            "github permissions error" in error_str or
                            ("401" in error_str and "github" in error_str)):
                            logger.error(f"GitHub authentication failure detected - stopping execution")
                            state["ended"] = True
                            state["end_reason"] = f"GitHub authentication error: {e}"
                            error_result = ToolResult(success=False, error=str(e))
                            state = self._reduce_tool_result(state, tool_name, error_result)
                            return state
                        
                        error_result = ToolResult(success=False, error=str(e))
                        state = self._reduce_tool_result(state, tool_name, error_result)
                        self.stats["errors_encountered"] += 1

            # Fallback auto-progression if the LLM keeps issuing only searches
            if not state.get("ended"):
                try:
                    repos = state.get("repos", [])
                    candidates = state.get("candidates", [])
                    leads = state.get("leads", [])

                    # If we already have repos but no candidates, extract people
                    if repos and not candidates and "extract_people" in self.tools:
                        logger.info("Auto-progress: executing extract_people based on repos present")
                        state["current_stage"] = "extraction"
                        try:
                            tool = self.tools["extract_people"]
                            result = await tool.execute(repos=repos, top_authors_per_repo=5)
                            state = self._reduce_tool_result(state, "extract_people", result)
                            self.stats["tools_executed"] += 1
                            # Inform LLM about auto-progress result
                            try:
                                summary_msg = self._summarize_tool_result("extract_people", result, state, auto_progress=True)
                                if summary_msg:
                                    state.setdefault("history", []).append({
                                        "type": "ai",
                                        "content": summary_msg,
                                        "timestamp": datetime.now().isoformat(),
                                    })
                            except Exception:
                                pass
                            # After extracting, return early to let next loop continue
                            state.setdefault("counters", {})
                            state["counters"]["steps"] = state["counters"].get("steps", 0) + 1
                            logger.info("Auto-progress: extract_people completed, yielding control")
                            return state
                        except Exception as e:
                            logger.warning(f"Auto-progress extract_people failed: {e}")

                    # If we have candidates but no leads enriched, enrich users in batch
                    if candidates and not leads and "enrich_github_users" in self.tools:
                        unique_logins = []
                        seen = set()
                        for c in candidates:
                            login = c.get("login")
                            if login and login not in seen:
                                unique_logins.append(login)
                                seen.add(login)
                        if unique_logins:
                            logger.info("Auto-progress: executing enrich_github_users based on candidates present")
                            state["current_stage"] = "enrichment"
                            try:
                                tool = self.tools["enrich_github_users"]
                                result = await tool.execute(logins=unique_logins[:25])
                                state = self._reduce_tool_result(state, "enrich_github_users", result)
                                self.stats["tools_executed"] += 1
                                # Inform LLM about auto-progress result
                                try:
                                    summary_msg = self._summarize_tool_result("enrich_github_users", result, state, auto_progress=True)
                                    if summary_msg:
                                        state.setdefault("history", []).append({
                                            "type": "ai",
                                            "content": summary_msg,
                                            "timestamp": datetime.now().isoformat(),
                                        })
                                except Exception:
                                    pass
                                state.setdefault("counters", {})
                                state["counters"]["steps"] = state["counters"].get("steps", 0) + 1
                                logger.info("Auto-progress: enrich_github_users completed, yielding control")
                                return state
                            except Exception as e:
                                logger.warning(f"Auto-progress enrich_github_users failed: {e}")

                    # If we have enriched leads but missing emails and have candidates mapping, find emails in batch
                    if state.get("leads") and "find_commit_emails_batch" in self.tools and not state.get("email_search_exhausted"):
                        leads_without_email = [l for l in state.get("leads", []) if not l.get("email") and not l.get("no_email_found")]
                        if leads_without_email and candidates:
                            user_repo_pairs = []
                            # Build (login, repo_full_name) pairs from candidates signals
                            for c in candidates:
                                login = c.get("login")
                                repo_full_name = c.get("from_repo")
                                if login and repo_full_name:
                                    user_repo_pairs.append({"login": login, "repo_full_name": repo_full_name})
                            if user_repo_pairs:
                                logger.info("Auto-progress: executing find_commit_emails_batch for leads without email")
                                state["current_stage"] = "validation"
                                try:
                                    # Track before/after counts to detect progress
                                    before_with_email = len([l for l in state.get("leads", []) if l.get("email")])
                                    tool = self.tools["find_commit_emails_batch"]
                                    result = await tool.execute(user_repo_pairs=user_repo_pairs[:50], days=90)
                                    state = self._reduce_tool_result(state, "find_commit_emails_batch", result)
                                    after_with_email = len([l for l in state.get("leads", []) if l.get("email")])

                                    self.stats["tools_executed"] += 1
                                    state.setdefault("counters", {})
                                    state["counters"]["steps"] = state["counters"].get("steps", 0) + 1

                                    # Inform LLM about auto-progress result
                                    try:
                                        summary_msg = self._summarize_tool_result("find_commit_emails_batch", result, state, auto_progress=True, extra_info={
                                            "before": before_with_email,
                                            "after": after_with_email,
                                        })
                                        if summary_msg:
                                            state.setdefault("history", []).append({
                                                "type": "ai",
                                                "content": summary_msg,
                                                "timestamp": datetime.now().isoformat(),
                                            })
                                    except Exception:
                                        pass

                                    # Detect no-progress attempts and set exhaustion flag to break loops
                                    if after_with_email <= before_with_email:
                                        streak = state["counters"].get("email_find_noop_streak", 0) + 1
                                        state["counters"]["email_find_noop_streak"] = streak
                                        if streak >= 2:
                                            # Mark unresolvable leads and stop auto email search
                                            for lead in state.get("leads", []):
                                                if not lead.get("email"):
                                                    attempts = lead.get("_email_attempts", 0) + 1
                                                    lead["_email_attempts"] = attempts
                                                    if attempts >= 2:
                                                        lead["no_email_found"] = True
                                            state["email_search_exhausted"] = True
                                            logger.info("Auto-progress: email search exhausted; marking unresolvable leads and stopping further attempts")
                                    else:
                                        # Reset noop streak on progress
                                        if state["counters"].get("email_find_noop_streak"):
                                            state["counters"]["email_find_noop_streak"] = 0

                                    logger.info("Auto-progress: find_commit_emails_batch completed, yielding control")
                                    return state
                                except Exception as e:
                                    logger.warning(f"Auto-progress find_commit_emails_batch failed: {e}")

                    # Auto-finalization: if we have leads with emails, check if we've reached target before finishing
                    leads_with_email = [l for l in state.get("leads", []) if l.get("email")]
                    
                    # Check if we've reached the target number of emails
                    icp = state.get("icp", {})
                    target_emails = icp.get("target_emails")
                    target_leads = icp.get("target_leads")
                    
                    # Count unique emails
                    unique_emails = set()
                    for lead in leads_with_email:
                        email = lead.get("email")
                        if email and '@' in email:
                            unique_emails.add(email.lower())
                    
                    current_email_count = len(unique_emails)
                    should_continue_searching = False
                    
                    # Determine if we should continue searching
                    if target_emails and current_email_count < target_emails:
                        should_continue_searching = True
                        logger.info(f"Target: {target_emails} emails, found: {current_email_count} - continuing search")
                    elif target_leads and len(leads_with_email) < target_leads:
                        should_continue_searching = True
                        logger.info(f"Target: {target_leads} leads, found: {len(leads_with_email)} - continuing search")
                    
                    # If we should continue searching, prioritize finding emails for existing leads first
                    if should_continue_searching and not state.get("email_search_exhausted"):
                        # PRIORITY 1: Find emails for existing leads without emails
                        leads_without_email = [l for l in state.get("leads", []) if not l.get("email")]
                        
                        if leads_without_email:
                            logger.info(f"Priority: Finding emails for {len(leads_without_email)} existing leads before searching more repos")
                            # Let the agent continue with email finding for existing leads
                            return state
                        
                        # PRIORITY 2: Only search for more repos if we've exhausted email finding
                        repos = state.get("repos", [])
                        max_repos = int(os.getenv("GITHUB_MAX_REPOS", "200"))  # Configurable limit
                        
                        if len(repos) < max_repos:
                            logger.info(f"Searching for more repositories to reach target... (current: {len(repos)}/{max_repos})")
                            # Let the agent continue with more repository searches
                            return state
                        else:
                            # Mark search as exhausted if we've hit the repo limit
                            state["email_search_exhausted"] = True
                            logger.info(f"Search exhausted: reached repo limit {len(repos)}/{max_repos}, proceeding with {current_email_count} emails")
                    
                    # Proceed with finalization if target is reached or search is exhausted
                    if leads_with_email and not state.get("ended"):
                        try:
                            # Attempt personalization: render copy for leads with emails if tool is available
                            if "render_copy" in self.tools:
                                try:
                                    # Render only for leads that don't already have prepared messages
                                    existing_to_send = state.get("to_send", [])
                                    def lead_email(lead):
                                        return lead.get("best_email") or lead.get("email")
                                    already_prepared_emails = set(
                                        [item.get("email") for item in existing_to_send if isinstance(item, dict) and item.get("email")]
                                    )

                                    leads_to_render = [
                                        l for l in leads_with_email
                                        if (lead_email(l) and lead_email(l) not in already_prepared_emails)
                                    ]

                                    # Cap auto-rendering to a reasonable batch size
                                    for lead in leads_to_render[:25]:
                                        rc_tool = self.tools["render_copy"]
                                        rc_result = await rc_tool.execute(lead=lead)
                                        state = self._reduce_tool_result(state, "render_copy", rc_result)
                                        self.stats["tools_executed"] += 1
                                except Exception as e:
                                    logger.warning(f"Auto-personalization (render_copy) failed: {e}")

                            # Export leads with email (CSV + JSON sidecar)
                            if "export_csv" in self.tools:
                                export_tool = self.tools["export_csv"]
                                job_id = state.get("job_id", "job")
                                export_path = f"{job_id}_leads.csv"
                                export_rows = leads_with_email
                                export_result = await export_tool.execute(rows=export_rows, path=export_path)
                                state = self._reduce_tool_result(state, "export_csv", export_result)
                                try:
                                    summary_msg = self._summarize_tool_result("export_csv", export_result, state, auto_progress=True)
                                    if summary_msg:
                                        state.setdefault("history", []).append({
                                            "type": "ai",
                                            "content": summary_msg,
                                            "timestamp": datetime.now().isoformat(),
                                        })
                                except Exception:
                                    pass

                                # Write JSON export next to CSV for easy consumption
                                try:
                                    from pathlib import Path
                                    import json as _json
                                    exports_dir = (
                                        self.config.get("directories", {}).get("exports")
                                        or self.config.get("EXPORT_DIR")
                                        or "./exports"
                                    )
                                    Path(exports_dir).mkdir(parents=True, exist_ok=True)
                                    json_path = Path(exports_dir) / f"{job_id}_leads.json"
                                    # Prefer leads_with_email subset for JSON as well
                                    with open(json_path, "w", encoding="utf-8") as f:
                                        _json.dump({
                                            "job_id": job_id,
                                            "export_timestamp": datetime.now().isoformat(),
                                            "data_type": "leads",
                                            "count": len(leads_with_email),
                                            "leads": leads_with_email,
                                        }, f, indent=2, default=str)
                                except Exception as e:
                                    logger.warning(f"Failed to write JSON leads export: {e}")

                            # Signal completion
                            if "done" in self.tools:
                                done_tool = self.tools["done"]
                                summary_text = f"Campaign completed: {len(leads_with_email)} leads with emails, repos={len(repos)}, candidates={len(candidates)}."
                                done_result = await done_tool.execute(summary=summary_text)
                                state = self._reduce_tool_result(state, "done", done_result)
                                try:
                                    summary_msg = self._summarize_tool_result("done", done_result, state, auto_progress=True)
                                    if summary_msg:
                                        state.setdefault("history", []).append({
                                            "type": "ai",
                                            "content": summary_msg,
                                            "timestamp": datetime.now().isoformat(),
                                        })
                                except Exception:
                                    pass
                                state["ended"] = True
                                logger.info("Auto-progress: finalized job via export and done")
                                return state
                        except Exception as e:
                            logger.warning(f"Auto-finalization failed: {e}")
                except Exception as e:
                    logger.warning(f"Auto-progress block encountered an error: {e}")

            # Update counters
            state.setdefault("counters", {})
            state["counters"]["steps"] = state["counters"].get("steps", 0) + 1

            # Log state persistence info for debugging
            logger.info(f"Agent step completed - executed {len(tool_calls)} tools, ended: {state.get('ended')}, steps: {state['counters']['steps']}")

            return state

        except Exception as e:
            logger.error(f"Agent step failed: {e}")
            # Add detailed error to state
            error_info = {
                "stage": "agent_step",
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.now().isoformat(),
                "tool_calls": [call.get("name") for call in tool_calls] if tool_calls else [],
                "current_step": state.get("counters", {}).get("steps", 0),
            }
            state.setdefault("errors", []).append(error_info)

            # Update error counter
            state.setdefault("counters", {})
            state["counters"]["errors"] = state["counters"].get("errors", 0) + 1

            return state

    # _create_tool_node is not used in the single-node workflow and has been removed for clarity

    def _reduce_tool_result(self, state: RunState, tool_name: str, result: ToolResult) -> Dict[str, Any]:
        """Reduce tool result into the RunState"""
        # Store tool result
        state.setdefault("tool_results", {})
        state["tool_results"][tool_name] = result.to_dict()

        # Update counters
        state.setdefault("counters", {})
        state["counters"]["api_calls"] = state["counters"].get("api_calls", 0) + 1

        # Handle tool errors
        if not result.success and result.error:
            error_info = {
                "stage": f"tool_result_{tool_name}",
                "error": result.error,
                "timestamp": datetime.now().isoformat(),
                "tool_name": tool_name,
                "result_data": result.data if hasattr(result, 'data') else None,
            }
            state.setdefault("errors", []).append(error_info)

        # Handle different tool types
        if tool_name == "search_github_repos" and result.success:
            state["repos"] = result.data.get("repos", [])
            state["current_stage"] = "discovery"

        elif tool_name == "extract_people" and result.success:
            state["candidates"] = result.data.get("candidates", [])
            state["current_stage"] = "extraction"

        elif tool_name == "enrich_github_user" and result.success:
            # Add enriched profile to leads
            profile = result.data.get("profile", {})
            state.setdefault("leads", [])
            # Find and update existing lead or add new one
            updated = False
            for i, lead in enumerate(state["leads"]):
                if lead.get("login") == profile.get("login"):
                    state["leads"][i] = {**lead, **profile}
                    updated = True
                    break
            if not updated:
                state["leads"].append(profile)

        elif tool_name == "enrich_github_users" and result.success:
            # Handle batched user enrichment
            profiles = result.data.get("profiles", [])
            state.setdefault("leads", [])

            for profile in profiles:
                if profile.get("enriched") == False:
                    # Skip failed enrichments but log them
                    logger.warning(f"Failed to enrich user {profile.get('login')}: {profile.get('error')}")
                    continue

                # Find and update existing lead or add new one
                updated = False
                for i, lead in enumerate(state["leads"]):
                    if lead.get("login") == profile.get("login"):
                        state["leads"][i] = {**lead, **profile}
                        updated = True
                        break
                if not updated:
                    state["leads"].append(profile)
            state["current_stage"] = "enrichment"

        elif tool_name == "find_commit_emails" and result.success:
            # Add email to the corresponding lead
            login = result.data.get("login")
            emails = result.data.get("emails", [])
            if login and emails:
                for lead in state.get("leads", []):
                    if lead.get("login") == login:
                        lead["email"] = emails[0]  # Take first email
                        break
            state["current_stage"] = "validation"

        elif tool_name == "find_commit_emails_batch" and result.success:
            # Handle batched email lookup
            user_emails = result.data.get("user_emails", {})
            for login, email_data in user_emails.items():
                emails = email_data.get("emails", [])
                if emails:
                    # Find the corresponding lead and add email
                    for lead in state.get("leads", []):
                        if lead.get("login") == login:
                            lead["email"] = emails[0]  # Take first email
                            break
            state["current_stage"] = "validation"

        elif tool_name == "mx_check" and result.success:
            # Mark emails as valid/invalid
            valid_emails = set(result.data.get("valid_emails", []))
            for lead in state.get("leads", []):
                email = lead.get("email")
                if email:
                    lead["email_valid"] = email in valid_emails
            state["current_stage"] = "validation"

        elif tool_name == "score_icp" and result.success:
            # This would be handled per-lead in the enrichment phase
            pass

        elif tool_name == "render_copy" and result.success:
            # Add rendered email to to_send
            state.setdefault("to_send", [])
            state["to_send"].append(result.data)
            state["current_stage"] = "personalization"

        elif tool_name == "send_instantly" and result.success:
            # Update reports
            state.setdefault("reports", {})
            state["reports"]["instantly"] = result.data
            state["current_stage"] = "sending"

        elif tool_name == "sync_attio" and result.success:
            # Update reports
            state.setdefault("reports", {})
            state["reports"]["attio"] = result.data
            state["current_stage"] = "sync"

        elif tool_name == "sync_linear" and result.success:
            # Update reports
            state.setdefault("reports", {})
            state["reports"]["linear"] = result.data
            state["current_stage"] = "sync"

        elif tool_name == "export_csv" and result.success:
            # Add to checkpoints
            state.setdefault("checkpoints", [])
            state["checkpoints"].append({
                "type": "csv_export",
                "path": result.data.get("path"),
                "count": result.data.get("count"),
                "timestamp": datetime.now().isoformat(),
            })
            state["current_stage"] = "export"

        elif tool_name == "done" and result.success:
            state["ended"] = True
            state["completed_at"] = result.data.get("completed_at")
            state["current_stage"] = "completed"

        return state

    def _summarize_tool_result(self, tool_name: str, result: ToolResult, state: RunState, auto_progress: bool = False, extra_info: Dict[str, Any] = None) -> str:
        """Create a concise summary line for a tool result to feed back to the LLM."""
        try:
            prefix = "[auto] " if auto_progress else ""
            if not getattr(result, "success", False):
                return f"{prefix}{tool_name} failed: {getattr(result, 'error', 'unknown error')}"

            if tool_name == "search_github_repos":
                count = len(state.get("repos", []))
                return f"{prefix}search_github_repos: found {count} repositories."
            if tool_name == "extract_people":
                count = len(state.get("candidates", []))
                return f"{prefix}extract_people: extracted {count} candidates from repositories."
            if tool_name in ("enrich_github_user", "enrich_github_users"):
                count = len(state.get("leads", []))
                return f"{prefix}{tool_name}: enriched {count} profiles total."
            if tool_name == "find_commit_emails_batch":
                count = len([l for l in state.get("leads", []) if l.get("email")])
                if extra_info and "before" in extra_info and "after" in extra_info:
                    return f"{prefix}find_commit_emails_batch: emails on leads {extra_info['before']} -> {extra_info['after']} (now {count} leads have emails)."
                return f"{prefix}find_commit_emails_batch: now {count} leads have emails."
            if tool_name == "mx_check":
                valid = len([l for l in state.get("leads", []) if l.get("email_valid")])
                return f"{prefix}mx_check: validated emails, {valid} marked valid."
            if tool_name == "export_csv":
                path = result.data.get("path") if hasattr(result, "data") else None
                count = result.data.get("count") if hasattr(result, "data") else None
                return f"{prefix}export_csv: exported {count} rows to {path}."
            if tool_name == "done":
                return f"{prefix}done: job completed."
        except Exception:
            return ""
        return ""

    def _hydrate_tool_args(self, tool_name: str, args: Dict[str, Any], state: RunState) -> (Optional[Dict[str, Any]], Optional[str]):
        """Best-effort fill of missing required args from state to avoid LLM mis-calls.

        Returns (args_or_none, note). If args_or_none is None, caller should skip execution.
        """
        try:
            note = None
            # Shallow copy to avoid mutating original
            hydrated = dict(args or {})

            if tool_name == "search_github_repos":
                # Auto-fill ICP criteria from state if not provided
                icp = state.get("icp", {})
                if icp:
                    # Add language filter if not specified
                    if not hydrated.get("language") and icp.get("languages"):
                        hydrated["language"] = icp["languages"][0]  # Use first language
                    
                    # Add stars range if not specified
                    if not hydrated.get("stars_range") and icp.get("stars_range"):
                        hydrated["stars_range"] = icp["stars_range"]
                    
                    # Add activity days if not specified
                    if not hydrated.get("activity_days") and icp.get("activity_days"):
                        hydrated["activity_days"] = icp["activity_days"]
                    
                    # Build search query from ICP if not provided
                    if not hydrated.get("q") or hydrated.get("q").strip() == "":
                        query_parts = []
                        
                        # Add keywords
                        if icp.get("keywords"):
                            query_parts.extend(icp["keywords"])
                        
                        # Add topics
                        if icp.get("topics"):
                            query_parts.extend(icp["topics"][:3])  # Limit to avoid too long query
                        
                        if query_parts:
                            hydrated["q"] = " ".join(query_parts)
                            note = f"[auto] Built search query from ICP: {hydrated['q']}"
                        else:
                            # Fallback to generic search
                            hydrated["q"] = "python testing"
                            note = "[auto] Using fallback search query"
                    
                return hydrated, note

            if tool_name == "enrich_github_users":
                # Always constrain to discovered candidates to avoid LLM-invented usernames
                candidates = state.get("candidates", [])
                candidate_set = {c.get("login") for c in candidates if c.get("login")}

                provided = list(hydrated.get("logins") or [])
                if provided:
                    # Intersect with candidate set; if intersection empty, fall back to candidates
                    filtered = [l for l in provided if l in candidate_set]
                    
                    # Additional validation: reject usernames that are clearly fake/test patterns
                    validated = []
                    for login in filtered:
                        # Only reject usernames that are obviously fake/test patterns
                        if any(pattern in login.lower() for pattern in ['test', 'fake', 'example', 'dummy']):
                            logger.warning(f"Rejecting test/fake username: {login}")
                            continue
                        validated.append(login)
                    
                    if validated:
                        hydrated["logins"] = validated[:25]
                        note = f"[auto] Restricted enrich_github_users logins to {len(hydrated['logins'])} validated candidates"
                    else:
                        provided = []  # force fallback

                if not provided:
                    unique_logins = []
                    seen = set()
                    for c in candidates:
                        login = c.get("login")
                        if login and login not in seen:
                            # Same validation for auto-filled candidates - only reject obvious test patterns
                            if any(pattern in login.lower() for pattern in ['test', 'fake', 'example', 'dummy']):
                                logger.warning(f"Skipping test/fake candidate username: {login}")
                                continue
                            unique_logins.append(login)
                            seen.add(login)
                    if unique_logins:
                        hydrated["logins"] = unique_logins[:25]
                        note = f"[auto] Filled enrich_github_users logins from validated candidates: {len(hydrated['logins'])}"
                    else:
                        return None, "[auto] enrich_github_users skipped: no valid candidates available."

                return hydrated, note

            if tool_name == "extract_people":
                # Requires repos list - auto-fill from state if not provided
                if "repos" not in hydrated or not hydrated.get("repos"):
                    repos = state.get("repos", [])
                    if not repos:
                        return None, "[auto] extract_people skipped: no repos available in state."
                    hydrated["repos"] = repos
                    note = f"[auto] Filled extract_people repos: {len(repos)} repositories"
                return hydrated, note

            if tool_name == "find_commit_emails_batch":
                # Build pairs from candidates if not provided
                if not hydrated.get("user_repo_pairs"):
                    pairs = []
                    for c in state.get("candidates", []):
                        login = c.get("login")
                        repo_full_name = c.get("from_repo")
                        if login and repo_full_name:
                            pairs.append({"login": login, "repo_full_name": repo_full_name})
                    if pairs:
                        hydrated["user_repo_pairs"] = pairs[:50]
                        note = f"[auto] Filled find_commit_emails_batch pairs: {len(hydrated['user_repo_pairs'])}"
                    else:
                        return None, "[auto] find_commit_emails_batch skipped: no candidate repo pairs available."
                return hydrated, note

            if tool_name == "export_csv":
                # Requires rows and path
                if "rows" not in hydrated or not hydrated.get("rows"):
                    leads_with_email = [l for l in state.get("leads", []) if l.get("email")]
                    fallback_rows = leads_with_email or state.get("to_send", []) or state.get("leads", [])
                    if not fallback_rows:
                        return None, "[auto] export_csv skipped: no data rows available in state."
                    hydrated["rows"] = fallback_rows
                if "path" not in hydrated or not hydrated.get("path"):
                    job_id = state.get("job_id", "job")
                    hydrated["path"] = f"{job_id}_leads.csv"
                note = f"[auto] Filled export_csv args: rows={len(hydrated['rows'])}, path={hydrated['path']}"
                return hydrated, note

            if tool_name == "mx_check":
                # Requires emails list
                if "emails" not in hydrated or not hydrated.get("emails"):
                    emails = []
                    for lead in state.get("leads", []):
                        if lead.get("email"):
                            emails.append(lead["email"])
                    if not emails:
                        return None, "[auto] mx_check skipped: no emails found in state."
                    hydrated["emails"] = list(dict.fromkeys(emails))
                    note = f"[auto] Filled mx_check emails: {len(hydrated['emails'])}"
                return hydrated, note

            if tool_name == "score_icp":
                # Requires single profile
                if "profile" not in hydrated or not hydrated.get("profile"):
                    lead = None
                    # Prefer a lead with email; else any lead
                    leads = state.get("leads", [])
                    for l in leads:
                        if l.get("email"):
                            lead = l
                            break
                    if lead is None and leads:
                        lead = leads[0]
                    if lead is None:
                        return None, "[auto] score_icp skipped: no lead profile available."
                    hydrated["profile"] = lead
                    note = f"[auto] Filled score_icp profile for {lead.get('login', 'unknown')}"
                return hydrated, note

            # Default: return original args without note
            return hydrated, None
        except Exception:
            return args, None

    def _parse_goal_to_icp(self, goal: str) -> Dict[str, Any]:
        """Parse the goal string to extract ICP criteria"""
        goal_lower = goal.lower()
        
        # Extract language
        languages = []
        if "python" in goal_lower:
            languages.append("python")
        elif "javascript" in goal_lower or "js" in goal_lower:
            languages.append("javascript")
        elif "java" in goal_lower:
            languages.append("java")
        elif "go" in goal_lower:
            languages.append("go")
        elif "rust" in goal_lower:
            languages.append("rust")
        else:
            languages = ["python"]  # Default to Python
        
        # Extract activity window
        activity_days = 90  # Default
        if "30 days" in goal_lower:
            activity_days = 30
        elif "60 days" in goal_lower:
            activity_days = 60
        elif "90 days" in goal_lower:
            activity_days = 90
        elif "6 months" in goal_lower:
            activity_days = 180
        elif "1 year" in goal_lower:
            activity_days = 365
        
        # Extract keywords and topics
        keywords = []
        topics = []
        
        if "developer" in goal_lower or "dev" in goal_lower:
            keywords.append("developer")
            topics.extend(["development", "coding"])
        if "maintainer" in goal_lower:
            keywords.append("maintainer")
            topics.extend(["maintenance", "open-source"])
        if "testing" in goal_lower or "test" in goal_lower:
            topics.extend(["testing", "qa", "pytest"])
        if "ai" in goal_lower or "ml" in goal_lower or "machine learning" in goal_lower:
            topics.extend(["ai", "ml", "machine-learning"])
        if "web" in goal_lower:
            topics.extend(["web", "frontend", "backend"])
        
        # Extract stars range
        stars_range = "100..2000"  # Default
        if "popular" in goal_lower or "high star" in goal_lower:
            stars_range = "500..10000"
        elif "small" in goal_lower or "new" in goal_lower:
            stars_range = "10..500"
        
        # Extract target numbers (emails, leads, contacts, etc.)
        import re

        # If goal explicitly specifies stars range, prefer it over defaults/heuristics
        try:
            m = re.search(r"stars:(\d+)\.\.(\d+)", goal_lower)
            if m:
                stars_range = f"{m.group(1)}..{m.group(2)}"
        except Exception:
            pass
        target_emails = None
        target_leads = None
        
        # Look for patterns like "find 50 emails", "get 100 contacts", "target 25 leads"
        email_patterns = [
            r'find\s+(\d+)\s+emails?',
            r'get\s+(\d+)\s+emails?',
            r'(\d+)\s+emails?',
            r'target\s+(\d+)\s+emails?'
        ]
        
        lead_patterns = [
            r'find\s+(\d+)\s+(?:leads?|contacts?|maintainers?|developers?)',
            r'get\s+(\d+)\s+(?:leads?|contacts?|maintainers?|developers?)',
            r'(\d+)\s+(?:leads?|contacts?|maintainers?|developers?)',
            r'target\s+(\d+)\s+(?:leads?|contacts?|maintainers?|developers?)'
        ]
        
        # Try to extract email targets
        for pattern in email_patterns:
            match = re.search(pattern, goal_lower)
            if match:
                target_emails = int(match.group(1))
                break
        
        # Try to extract lead targets  
        for pattern in lead_patterns:
            match = re.search(pattern, goal_lower)
            if match:
                target_leads = int(match.group(1))
                break
        
        # If we found an email target but no lead target, assume they're the same
        if target_emails and not target_leads:
            target_leads = target_emails
        elif target_leads and not target_emails:
            target_emails = target_leads
        
        # Default targets from config params if still missing
        try:
            params_cfg = self.config.get("params", {}) if isinstance(self.config.get("params"), dict) else {}
            default_target = params_cfg.get("target_leads") or params_cfg.get("target_emails")
            if default_target and isinstance(default_target, int):
                if target_leads is None:
                    target_leads = default_target
                if target_emails is None:
                    target_emails = default_target
        except Exception:
            pass
        
        return {
            "languages": languages,
            "activity_days": activity_days,
            "keywords": keywords,
            "topics": topics,
            "stars_range": stars_range,
            "target_emails": target_emails,
            "target_leads": target_leads,
            "goal": goal  # Keep original goal for reference
        }

    def _build_system_prompt(self, state: RunState) -> str:
        """Build the system prompt for the agent"""
        caps = self.config
        
        # Include ICP information in the prompt
        icp = state.get("icp", {})
        icp_info = ""
        if icp:
            target_info = ""
            if icp.get("target_emails"):
                target_info += f"- TARGET EMAILS: {icp.get('target_emails')}\n"
            if icp.get("target_leads"):
                target_info += f"- TARGET LEADS: {icp.get('target_leads')}\n"
            
            icp_info = f"""
ICP CRITERIA:
- Languages: {icp.get('languages', [])}
- Activity: Last {icp.get('activity_days', 90)} days
- Keywords: {icp.get('keywords', [])}
- Topics: {icp.get('topics', [])}
- Stars range: {icp.get('stars_range', '100..2000')}
{target_info}"""

        prompt = f"""You are a CMO operator. Your task: {state['goal']}
{icp_info}
FOLLOW THIS EXACT SEQUENCE:
1. search_github_repos - Find relevant repositories
2. extract_people - Get contributors from those repos
3. enrich_github_users - Enrich user profiles (use this, not enrich_github_user)
4. find_commit_emails_batch - Find emails (use this, not find_commit_emails)
5. mx_check - Validate emails
6. score_icp - Score leads
7. render_copy - Create email content
8. send_instantly - Send emails (DRY RUN)
9. sync_attio - Update CRM
10. export_csv - Export results
11. done - FINISH the campaign

CRITICAL: Continue searching until you reach the TARGET number of emails/leads specified above. Only call done("Completed") when targets are met or search is exhausted.

TARGET ACHIEVEMENT:
- If TARGET EMAILS or TARGET LEADS are specified, continue searching until you reach those numbers
- Search more repositories, extract more people, find more emails until targets are met
- Only finish when you have enough emails/leads OR when search is clearly exhausted

RULES TO AVOID LOOPS:
- If repositories already exist but you need more emails, search for MORE repositories with different criteria
- Use the assistant function result summaries in the conversation to update your plan
- If you have leads with emails but haven't reached targets, continue searching for more

Available tools: {', '.join(self.tools.keys())}
"""

        return prompt

    # _should_continue is unused in the current single-node design; retaining for reference is unnecessary

    async def run_job(self, goal: str, created_by: str = "user", progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Run a complete job from start to finish with progress updates"""
        job_meta = None
        try:
            # Create job metadata
            job_meta = JobMetadata(goal, created_by)
            
            # Parse goal to create ICP criteria and print at start for visibility
            parsed_icp = self._parse_goal_to_icp(goal)
            try:
                icp_summary = {
                    "languages": parsed_icp.get("languages"),
                    "activity_days": parsed_icp.get("activity_days"),
                    "stars_range": parsed_icp.get("stars_range"),
                    "keywords": parsed_icp.get("keywords"),
                    "topics": parsed_icp.get("topics"),
                    "target_emails": parsed_icp.get("target_emails"),
                    "target_leads": parsed_icp.get("target_leads"),
                }
                # Human-readable
                logger.info(f"Campaign goal: {goal}")
                logger.info(f"Derived ICP: {icp_summary}")
                # Structured log for JSON
                try:
                    logger.info(
                        "campaign_start",
                        extra={
                            "structured": {
                                "event": "campaign_start",
                                "goal": goal,
                                "icp": icp_summary,
                                "job_id": job_meta.job_id,
                            }
                        },
                    )
                except Exception:
                    pass
                print(f"🎯 Goal: {goal}")
                print(f"🧭 ICP: {icp_summary}")
            except Exception:
                pass
            
            # Validate GitHub token early to fail fast
            if self.config.get("GITHUB_TOKEN") and not self.config.get("features", {}).get("dry_run", False):
                try:
                    await self._validate_github_token()
                except ValueError as e:
                    logger.error(f"GitHub validation failed: {e}")
                    raise Exception(f"GitHub setup error: {e}")
            
            # Initialize beautiful logging for this job
            try:
                self.beautiful_logger = setup_beautiful_logging(self.config, job_meta.job_id)
                self.beautiful_logger.start_stage("initialization", f"Starting campaign: {goal}")
            except Exception as e:
                logger.warning(f"Failed to initialize beautiful logging: {e}")
                self.beautiful_logger = None

            # (parsed_icp already computed above)
            
            # Initialize state
            initial_state = RunState(
                **job_meta.to_dict(),
                icp=parsed_icp,
                config=self.config,
                current_stage="initialization",
                counters={"steps": 0, "api_calls": 0, "tokens": 0, "errors": 0, "tool_errors": 0},
                ended=False,  # Explicitly initialize ended flag
                repos=[],     # Initialize empty lists
                candidates=[],
                leads=[],
                to_send=[],
                reports={},
                errors=[],    # Initialize empty errors list
                checkpoints=[],
                tool_results={},
            )

            # Run the graph with progress streaming
            logger.info(f"Starting CMO Agent job: {job_meta.job_id}")

            # Use astream for progress updates with recursion limit
            final_state = None
            max_steps = self.config.get("max_steps", 40)

            # Use astream to properly handle state transitions
            try:
                final_state = initial_state
                async for step_result in self.graph.astream(initial_state, {"recursion_limit": max_steps + 10}):
                    final_state = step_result

                    # Extract progress information
                    progress_info = self._extract_progress_info(step_result)
                    # Enforce valid stage values (avoid 'unknown' in UI)
                    try:
                        st = progress_info.get("stage")
                        if not isinstance(st, str) or st.strip().lower() in {"", "unknown"}:
                            progress_info["stage"] = step_result.get("current_stage") or "initialization"
                    except Exception:
                        pass
                    if progress_callback:
                        await progress_callback(progress_info)

                    # Check for pause request
                    if self.is_pause_requested():
                        logger.info(f"Pause detected for job {job_meta.job_id}, saving state and stopping")
                        # Save current state for resume
                        self.save_job_state(job_meta.job_id, step_result)
                        await self._save_checkpoint(job_meta.job_id, step_result, "paused")

                        # Return partial result
                        return {
                            "success": False,
                            "job_id": job_meta.job_id,
                            "final_state": step_result,
                            "paused": True,
                            "message": "Job paused by user request",
                        }

                    # Periodic checkpointing
                    if await self._should_checkpoint(step_result):
                        await self._save_checkpoint(job_meta.job_id, step_result, "periodic")

                logger.info("Job completed successfully via astream")

            except Exception as e:
                logger.error(f"Job execution failed via astream: {e}")
                raise

            # Update stats
            self.stats["jobs_processed"] += 1

            # Finalize job with comprehensive artifact collection
            finalization_result = await self._finalize_job(job_meta.job_id, final_state, "completed")

            return {
                "success": True,
                "job_id": job_meta.job_id,
                "final_state": final_state,
                "artifacts": finalization_result.get("artifacts", []),
                "report": finalization_result.get("report"),
            }
        except Exception as e:
            # Outer run_job failure handler
            logger.error(f"Job execution failed: {e}")
            job_id = job_meta.job_id if job_meta else "unknown"

            # Attach error to state if available
            if 'final_state' in locals() and final_state and hasattr(final_state, 'setdefault'):
                final_state.setdefault("errors", []).append({
                    "stage": "job_execution",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "timestamp": datetime.now().isoformat(),
                    "job_id": job_id,
                    "critical": True,
                })
                final_state["ended"] = True
                final_state["current_stage"] = "failed"

            # Finalize to collect partial artifacts
            try:
                finalization_result = await self._finalize_job(job_id, final_state if 'final_state' in locals() else None, "failed")
            except Exception:
                finalization_result = {"artifacts": [], "report": None}

            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "job_id": job_id,
                "final_state": final_state if 'final_state' in locals() else None,
                "artifacts": finalization_result.get("artifacts", []),
                "report": finalization_result.get("report"),
            }
    async def resume_job(self, job_id: str, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Resume a paused job from saved state"""
        logger.info(f"Attempting to resume job {job_id}")

        # Get saved state
        saved_state = self.get_job_state(job_id)
        if not saved_state:
            raise ValueError(f"No saved state found for job {job_id}")

        # Clear pause flag for resume
        self._pause_requested = False

        # Continue from saved state
        final_state = None
        max_steps = self.config.get("max_steps", 40)

        try:
            async for step_result in self.graph.astream(saved_state, {"recursion_limit": max_steps + 10}):
                final_state = step_result

                # Extract progress information
                progress_info = self._extract_progress_info(step_result)
                if progress_callback:
                    await progress_callback(progress_info)

                # Check for pause request (can pause again during resume)
                if self.is_pause_requested():
                    logger.info(f"Pause detected during resume for job {job_id}, saving state and stopping")
                    self.save_job_state(job_id, step_result)
                    await self._save_checkpoint(job_id, step_result, "paused")

                    return {
                        "success": False,
                        "job_id": job_id,
                        "final_state": step_result,
                        "paused": True,
                        "message": "Job paused again during resume",
                    }

                # Periodic checkpointing
                if await self._should_checkpoint(step_result):
                    await self._save_checkpoint(job_id, step_result, "periodic")

            logger.info(f"Job {job_id} resumed and completed successfully")

            # Clear saved state since job is complete
            self.clear_job_state(job_id)

            # Update stats
            self.stats["jobs_processed"] += 1

            # Finalize job after successful resume
            finalization_result = await self._finalize_job(job_id, final_state, "completed")

            return {
                "success": True,
                "job_id": job_id,
                "final_state": final_state,
                "artifacts": finalization_result.get("artifacts", []),
                "report": finalization_result.get("report"),
                "resumed": True,
            }

        except Exception as e:
            logger.error(f"Job resume failed for {job_id}: {e}")

            # Attach error to state
            if final_state is None:
                final_state = {"errors": [], "counters": {}}
            if hasattr(final_state, 'setdefault'):
                final_state.setdefault("errors", []).append({
                    "stage": "job_resume",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "timestamp": datetime.now().isoformat(),
                    "job_id": job_id,
                    "critical": True,
                })
                final_state["ended"] = True
                final_state["current_stage"] = "failed"

            # Finalize as failed to collect artifacts
            try:
                finalization_result = await self._finalize_job(job_id, final_state, "failed")
            except Exception:
                finalization_result = {"artifacts": [], "report": None}

            return {
                "success": False,
                "job_id": job_id,
                "final_state": final_state,
                "artifacts": finalization_result.get("artifacts", []),
                "report": finalization_result.get("report"),
                "resumed": True,
                "error": str(e),
                "error_type": type(e).__name__,
            }

        

    def _extract_progress_info(self, state: RunState) -> Dict[str, Any]:
        """Extract progress information from RunState"""
        counters = state.get("counters", {})
        current_stage = state.get("current_stage", "unknown")

        # Map stages to human-readable names
        stage_names = {
            "initialization": "Initializing",
            "discovery": "Discovering repositories",
            "extraction": "Extracting contributors",
            "enrichment": "Enriching profiles",
            "validation": "Validating emails",
            "scoring": "Scoring leads",
            "personalization": "Personalizing content",
            "sending": "Sending emails",
            "sync": "Syncing to CRM",
            "export": "Exporting results",
            "completed": "Completed",
            "failed": "Failed",
        }

        progress_info = {
            "stage": stage_names.get(current_stage, current_stage),
            "step": counters.get("steps", 0),
            "metrics": {
                "api_calls": counters.get("api_calls", 0),
                "tokens_used": counters.get("tokens", 0),
                "repos_found": len(state.get("repos", [])),
                "candidates_found": len(state.get("candidates", [])),
                "leads_enriched": len(state.get("leads", [])),
                "emails_to_send": len(state.get("to_send", [])),
            },
            "current_item": f"Processing {current_stage} phase",
        }

        # Add estimated completion if we have progress data
        if counters.get("steps", 0) > 0:
            # Rough estimation based on typical campaign progress
            total_estimated_steps = 40  # From config
            current_step = min(counters.get("steps", 0), total_estimated_steps)
            progress_percentage = current_step / total_estimated_steps

            progress_info["progress_percentage"] = progress_percentage
            progress_info["estimated_completion"] = f"~{int((1 - progress_percentage) * 60)} minutes remaining"

        return progress_info

    

    async def _save_checkpoint(self, job_id: str, state: RunState, checkpoint_type: str = "periodic"):
        """Save a checkpoint of the current job state"""
        try:
            import json
            from pathlib import Path

            # Create checkpoints directory (absolute path for clickable links)
            checkpoints_dir = Path(self.config.get("directories", {}).get("checkpoints", "./checkpoints"))
            checkpoints_dir.mkdir(parents=True, exist_ok=True)
            checkpoints_dir = checkpoints_dir.resolve()

            # Create checkpoint file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            checkpoint_file = checkpoints_dir / f"{job_id}_{checkpoint_type}_{timestamp}.json"

            # Prepare checkpoint data - EXCLUDE SENSITIVE CONFIG
            state_copy = dict(state)
            
            # Remove or sanitize sensitive data from config
            if "config" in state_copy and isinstance(state_copy["config"], dict):
                config_copy = dict(state_copy["config"])
                
                # Remove API keys and tokens
                sensitive_keys = [
                    "GITHUB_TOKEN", "OPENAI_API_KEY", "INSTANTLY_API_KEY", 
                    "ATTIO_API_KEY", "ATTIO_ACCESS_TOKEN", "LINEAR_API_KEY",
                    "LANGFUSE_SECRET_KEY", "SMTP_PASSWORD", "DATABASE_URL"
                ]
                
                for key in sensitive_keys:
                    if key in config_copy:
                        config_copy[key] = "***REDACTED***"
                
                state_copy["config"] = config_copy
            
            checkpoint_data = {
                "job_id": job_id,
                "checkpoint_type": checkpoint_type,
                "timestamp": datetime.now().isoformat(),
                "state": state_copy,
                "counters": state.get("counters", {}),
                "progress": state.get("progress", {}),
            }

            # Save to file
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2, default=str)
            try:
                # Ensure fs sync so downstream tools can find it immediately
                f.flush()
                os.fsync(f.fileno())
            except Exception:
                pass

            # Add to state's checkpoints list
            state.setdefault("checkpoints", []).append({
                "type": checkpoint_type,
                "path": str(checkpoint_file),
                "timestamp": datetime.now().isoformat(),
                "counters": state.get("counters", {}),
            })

            logger.info(f"Checkpoint saved: {checkpoint_file}")

            # Clean up old checkpoints periodically
            if checkpoint_type == "periodic":
                await self._cleanup_checkpoints(job_id)

            return str(checkpoint_file)

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return None

    async def _should_checkpoint(self, state: RunState) -> bool:
        """Determine if we should create a checkpoint using hybrid strategy"""
        import time

        counters = state.get("counters", {})
        current_step = counters.get("steps", 0)
        current_stage = state.get("current_stage", "")

        # Get checkpoint configuration
        checkpoint_config = self.config.get("job_config", {}).get("checkpoints", {})
        time_interval = checkpoint_config.get("time_interval", 300)  # 5 minutes default
        step_interval = checkpoint_config.get("step_interval", 50)   # Every 50 steps
        volume_interval = checkpoint_config.get("volume_interval", 1000)  # Every 1000 leads

        # Time-based checkpointing
        last_checkpoint_time = getattr(self, '_last_checkpoint_time', 0)
        current_time = time.time()

        if current_time - last_checkpoint_time >= time_interval:
            self._last_checkpoint_time = current_time
            logger.debug(f"Time-based checkpoint triggered after {time_interval}s")
            return True

        # Step-based checkpointing
        if current_step > 0 and current_step % step_interval == 0:
            logger.debug(f"Step-based checkpoint triggered at step {current_step}")
            return True

        # Volume-based checkpointing
        repos_count = len(state.get("repos", []))
        leads_count = len(state.get("leads", []))
        candidates_count = len(state.get("candidates", []))

        total_volume = repos_count + leads_count + candidates_count

        if total_volume > 0 and total_volume % volume_interval == 0:
            logger.debug(f"Volume-based checkpoint triggered at {total_volume} items")
            return True

        # Stage transition checkpointing
        last_checkpointed_stage = getattr(self, '_last_checkpointed_stage', None)
        if last_checkpointed_stage != current_stage and current_stage:
            self._last_checkpointed_stage = current_stage
            logger.debug(f"Stage transition checkpoint triggered: {current_stage}")
            return True

        # Milestone-based checkpointing
        if self._is_significant_milestone(state):
            logger.debug("Significant milestone checkpoint triggered")
            return True

        return False

    async def _cleanup_checkpoints(self, job_id: str):
        """Clean up old checkpoints to prevent disk space issues"""
        try:
            from pathlib import Path
            import os

            checkpoints_dir = Path(self.config.get("directories", {}).get("checkpoints", "./checkpoints"))
            if not checkpoints_dir.exists():
                return

            # Get all checkpoints for this job
            job_checkpoints = list(checkpoints_dir.glob(f"{job_id}_*.json"))

            # Sort by modification time (newest first)
            job_checkpoints.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # Keep only the most recent checkpoints
            max_checkpoints = self.config.get("persistence", {}).get("max_checkpoints", 50)

            if len(job_checkpoints) > max_checkpoints:
                checkpoints_to_delete = job_checkpoints[max_checkpoints:]

                for checkpoint_file in checkpoints_to_delete:
                    try:
                        os.remove(checkpoint_file)
                        logger.debug(f"Cleaned up old checkpoint: {checkpoint_file}")
                    except Exception as e:
                        logger.warning(f"Failed to delete checkpoint {checkpoint_file}: {e}")

                logger.info(f"Cleaned up {len(checkpoints_to_delete)} old checkpoints for job {job_id}")

        except Exception as e:
            logger.error(f"Failed to cleanup checkpoints for job {job_id}: {e}")

    async def _finalize_job(self, job_id: str, final_state: RunState, job_status: str = "completed"):
        """Finalize job with proper artifact collection and cleanup"""
        try:
            logger.info(f"Finalizing job {job_id} with status: {job_status}")

            # Collect artifacts based on job status
            artifacts = await self._collect_artifacts(job_id, final_state, job_status)

            # Save final checkpoint
            if final_state:
                await self._save_checkpoint(job_id, final_state, job_status)

            # Clean up temporary resources
            await self._cleanup_job_resources(job_id, job_status)

            # Generate final report
            final_report = self._generate_final_report(job_id, final_state, artifacts, job_status)

            return {
                "job_id": job_id,
                "status": job_status,
                "artifacts": artifacts,
                "final_state": final_state,
                "report": final_report,
            }

        except Exception as e:
            logger.error(f"Failed to finalize job {job_id}: {e}")
            return {
                "job_id": job_id,
                "status": "finalization_failed",
                "error": str(e),
                "artifacts": [],
            }

    async def _collect_artifacts(self, job_id: str, final_state: RunState = None, job_status: str = "completed"):
        """Collect and organize artifacts based on job completion status"""
        artifacts = []

        try:
            # Always collect available data regardless of completion status
            if final_state:
                # Collect repositories data
                repos = final_state.get("repos", [])
                if repos:
                    artifacts.append(await self._export_repos_data(job_id, repos, job_status))

                # Collect leads data
                leads = final_state.get("leads", [])
                if leads:
                    artifacts.append(await self._export_leads_data(job_id, leads, job_status))
                    # Also export contactable emails as CSV
                    contact_art = await self._export_contactable_emails(job_id, leads, job_status)
                    if contact_art:
                        artifacts.append(contact_art)

                # Collect candidates data
                candidates = final_state.get("candidates", [])
                if candidates:
                    artifacts.append(await self._export_candidates_data(job_id, candidates, job_status))

                # Collect personalization data if available
                to_send = final_state.get("to_send", [])
                if to_send:
                    artifacts.append(await self._export_personalization_data(job_id, to_send, job_status))

                # Collect reports if available
                reports = final_state.get("reports", {})
                if reports:
                    artifacts.append(await self._export_reports_data(job_id, reports, job_status))

            # Collect error logs if job failed
            if job_status in ["failed", "paused"]:
                error_artifact = await self._export_error_summary(job_id, final_state)
                if error_artifact:
                    artifacts.append(error_artifact)

            # Collect performance metrics
            metrics_artifact = await self._export_performance_metrics(job_id, final_state)
            if metrics_artifact:
                artifacts.append(metrics_artifact)

        except Exception as e:
            logger.error(f"Failed to collect artifacts for job {job_id}: {e}")

        return artifacts

    async def _export_repos_data(self, job_id: str, repos: list, job_status: str):
        """Export repositories data to artifact using artifact manager"""
        try:
            data = {
                "job_id": job_id,
                "job_status": job_status,
                "export_timestamp": datetime.now().isoformat(),
                "data_type": "repositories",
                "count": len(repos),
                "repositories": repos,
            }

            filename = f"repos_{job_status}.json"
            artifact_id = await self.artifact_manager.store_artifact(
                job_id=job_id,
                filename=filename,
                data=data,
                artifact_type="repositories",
                retention_policy="default",
                compress=len(repos) > 100,  # Compress large datasets
                tags=["repositories", job_status]
            )

            # Get metadata for return value
            metadata = await self.artifact_manager.get_artifact_metadata(artifact_id)

            return {
                "type": "repositories",
                "artifact_id": artifact_id,
                "path": metadata.path if metadata else None,
                "filename": metadata.filename if metadata else filename,
                "count": len(repos),
                "format": "json",
                "compressed": metadata.compressed if metadata else False,
            }

        except Exception as e:
            logger.error(f"Failed to export repos data: {e}")
            return None

    async def _export_leads_data(self, job_id: str, leads: list, job_status: str):
        """Export leads data to artifact using artifact manager"""
        try:
            data = {
                "job_id": job_id,
                "job_status": job_status,
                "export_timestamp": datetime.now().isoformat(),
                "data_type": "leads",
                "count": len(leads),
                "leads": leads,
            }

            filename = f"leads_{job_status}.json"
            artifact_id = await self.artifact_manager.store_artifact(
                job_id=job_id,
                filename=filename,
                data=data,
                artifact_type="leads",
                retention_policy="default",
                compress=len(leads) > 50,  # Compress larger datasets
                tags=["leads", job_status]
            )

            metadata = await self.artifact_manager.get_artifact_metadata(artifact_id)

            return {
                "type": "leads",
                "artifact_id": artifact_id,
                "path": metadata.path if metadata else None,
                "filename": metadata.filename if metadata else filename,
                "count": len(leads),
                "format": "json",
                "compressed": metadata.compressed if metadata else False,
            }

        except Exception as e:
            logger.error(f"Failed to export leads data: {e}")
            return None

    async def _export_contactable_emails(self, job_id: str, leads: list, job_status: str):
        """Export contactable emails as CSV excluding noreply addresses"""
        try:
            # Filter out noreply emails using unified function
            from ..utils.email_utils import filter_contactable_emails

            all_emails = []
            for lead in leads:
                email = lead.get("email") or lead.get("primary_email")
                if email:
                    all_emails.append(email)

            valid_emails = filter_contactable_emails(all_emails)
            if not valid_emails:
                return None

            # Write CSV content (one email per line)
            export_dir = Path(self.config.get("directories", {}).get("exports", "./exports"))
            job_dir = export_dir / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            csv_path = job_dir / "leads_contactable.csv"
            csv_path.write_text("\n".join(valid_emails))

            # Register artifact in index
            artifact_id = await self.artifact_manager.store_artifact(
                job_id=job_id,
                filename="leads_contactable.csv",
                data={"emails": valid_emails},        # store list as JSON for index (content already written as CSV)
                artifact_type="contacts",
                retention_policy="default",
                compress=False,
                tags=["contactable", job_status]
            )

            # Overwrite path to point to the CSV file we wrote (artifact manager stored a JSON, but we want the CSV file for download)
            meta = await self.artifact_manager.get_artifact_metadata(artifact_id)
            if meta:
                meta.path = str(csv_path)  # update to actual CSV file path
                meta.filename = "leads_contactable.csv"
                # Update internal index as well
                self.artifact_manager._index[artifact_id]["path"] = str(csv_path)
                self.artifact_manager._index[artifact_id]["filename"] = "leads_contactable.csv"

            return {
                "type": "contacts",
                "artifact_id": artifact_id,
                "filename": "leads_contactable.csv",
                "count": len(valid_emails)
            }

        except Exception as e:
            logger.error(f"Failed to export contactable emails: {e}")
            return None

    async def _export_candidates_data(self, job_id: str, candidates: list, job_status: str):
        """Export candidates data to artifact using artifact manager"""
        try:
            data = {
                "job_id": job_id,
                "job_status": job_status,
                "export_timestamp": datetime.now().isoformat(),
                "data_type": "candidates",
                "count": len(candidates),
                "candidates": candidates,
            }

            filename = f"candidates_{job_status}.json"
            artifact_id = await self.artifact_manager.store_artifact(
                job_id=job_id,
                filename=filename,
                data=data,
                artifact_type="candidates",
                retention_policy="default",
                compress=len(candidates) > 200,  # Compress for larger datasets
                tags=["candidates", job_status]
            )

            metadata = await self.artifact_manager.get_artifact_metadata(artifact_id)

            return {
                "type": "candidates",
                "artifact_id": artifact_id,
                "path": metadata.path if metadata else None,
                "filename": metadata.filename if metadata else filename,
                "count": len(candidates),
                "format": "json",
                "compressed": metadata.compressed if metadata else False,
            }

        except Exception as e:
            logger.error(f"Failed to export candidates data: {e}")
            return None

    async def _export_personalization_data(self, job_id: str, to_send: list, job_status: str):
        """Export personalization data to artifact"""
        try:
            from pathlib import Path
            import json

            exports_dir = Path(self.config.get("directories", {}).get("exports", "./exports"))
            exports_dir.mkdir(exist_ok=True)

            filename = f"{job_id}_personalization_{job_status}.json"
            filepath = exports_dir / filename

            with open(filepath, 'w') as f:
                json.dump({
                    "job_id": job_id,
                    "job_status": job_status,
                    "export_timestamp": datetime.now().isoformat(),
                    "data_type": "personalization",
                    "count": len(to_send),
                    "to_send": to_send,
                }, f, indent=2, default=str)

            return {
                "type": "personalization",
                "path": str(filepath),
                "filename": filename,
                "count": len(to_send),
                "format": "json",
            }

        except Exception as e:
            logger.error(f"Failed to export personalization data: {e}")
            return None

    async def _export_reports_data(self, job_id: str, reports: dict, job_status: str):
        """Export reports data to artifact"""
        try:
            from pathlib import Path
            import json

            exports_dir = Path(self.config.get("directories", {}).get("exports", "./exports"))
            exports_dir.mkdir(exist_ok=True)

            filename = f"{job_id}_reports_{job_status}.json"
            filepath = exports_dir / filename

            with open(filepath, 'w') as f:
                json.dump({
                    "job_id": job_id,
                    "job_status": job_status,
                    "export_timestamp": datetime.now().isoformat(),
                    "data_type": "reports",
                    "reports": reports,
                }, f, indent=2, default=str)

            return {
                "type": "reports",
                "path": str(filepath),
                "filename": filename,
                "format": "json",
            }

        except Exception as e:
            logger.error(f"Failed to export reports data: {e}")
            return None

    async def _export_error_summary(self, job_id: str, final_state: RunState):
        """Export error summary for failed/paused jobs"""
        try:
            from pathlib import Path
            import json

            errors = final_state.get("errors", []) if final_state else []
            counters = final_state.get("counters", {}) if final_state else {}

            exports_dir = Path(self.config.get("directories", {}).get("exports", "./exports"))
            exports_dir.mkdir(exist_ok=True)

            filename = f"{job_id}_error_summary.json"
            filepath = exports_dir / filename

            error_summary = {
                "job_id": job_id,
                "export_timestamp": datetime.now().isoformat(),
                "data_type": "error_summary",
                "total_errors": len(errors),
                "counters": counters,
                "errors": errors[-10:],  # Last 10 errors for summary
                "error_types": {},
            }

            # Count error types
            for error in errors:
                error_type = error.get("error_type", "unknown")
                error_summary["error_types"][error_type] = error_summary["error_types"].get(error_type, 0) + 1

            with open(filepath, 'w') as f:
                json.dump(error_summary, f, indent=2, default=str)

            return {
                "type": "error_summary",
                "path": str(filepath),
                "filename": filename,
                "error_count": len(errors),
                "format": "json",
            }

        except Exception as e:
            logger.error(f"Failed to export error summary: {e}")
            return None

    async def _export_performance_metrics(self, job_id: str, final_state: RunState):
        """Export performance metrics"""
        try:
            from pathlib import Path
            import json

            counters = final_state.get("counters", {}) if final_state else {}

            exports_dir = Path(self.config.get("directories", {}).get("exports", "./exports"))
            exports_dir.mkdir(exist_ok=True)

            filename = f"{job_id}_metrics.json"
            filepath = exports_dir / filename

            metrics = {
                "job_id": job_id,
                "export_timestamp": datetime.now().isoformat(),
                "data_type": "performance_metrics",
                "counters": counters,
                "derived_metrics": {
                    "api_efficiency": counters.get("api_calls", 0) / max(counters.get("steps", 1), 1),
                    "error_rate": counters.get("errors", 0) / max(counters.get("steps", 1), 1),
                    "tool_error_rate": counters.get("tool_errors", 0) / max(counters.get("steps", 1), 1),
                },
            }

            with open(filepath, 'w') as f:
                json.dump(metrics, f, indent=2, default=str)

            return {
                "type": "performance_metrics",
                "path": str(filepath),
                "filename": filename,
                "format": "json",
            }

        except Exception as e:
            logger.error(f"Failed to export performance metrics: {e}")
            return None

    async def _cleanup_job_resources(self, job_id: str, job_status: str):
        """Clean up temporary resources after job completion"""
        try:
            # Clean up old checkpoints if job completed successfully
            if job_status == "completed":
                await self._cleanup_checkpoints(job_id)

            # Clear job state from memory
            self.clear_job_state(job_id)

            logger.info(f"Cleaned up resources for job {job_id}")

        except Exception as e:
            logger.error(f"Failed to cleanup resources for job {job_id}: {e}")

    def _generate_final_report(self, job_id: str, final_state: RunState, artifacts: list, job_status: str):
        """Generate a final report summarizing the job"""
        try:
            counters = final_state.get("counters", {}) if final_state else {}

            report = {
                "job_id": job_id,
                "status": job_status,
                "completed_at": datetime.now().isoformat(),
                "summary": {
                    "steps_completed": counters.get("steps", 0),
                    "api_calls_made": counters.get("api_calls", 0),
                    "errors_encountered": counters.get("errors", 0),
                    "repositories_found": len(final_state.get("repos", [])) if final_state else 0,
                    "leads_processed": len(final_state.get("leads", [])) if final_state else 0,
                    "candidates_found": len(final_state.get("candidates", [])) if final_state else 0,
                    "emails_prepared": len(final_state.get("to_send", [])) if final_state else 0,
                },
                "artifacts_generated": len(artifacts),
                "artifacts": artifacts,
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate final report for job {job_id}: {e}")
            return {
                "job_id": job_id,
                "status": "report_generation_failed",
                "error": str(e),
            }

    def _is_significant_milestone(self, state: RunState) -> bool:
        """Check if current state represents a significant milestone"""
        counters = state.get("counters", {})
        current_step = counters.get("steps", 0)
        current_stage = state.get("current_stage", "")

        # First completion of major stages
        if current_stage in ["discovery", "extraction", "enrichment", "personalization"]:
            # Check if this is the first time we're in this stage
            stage_history = getattr(self, '_stage_history', set())
            if current_stage not in stage_history:
                self._stage_history = stage_history | {current_stage}
                return True

        # Significant data volume milestones
        repos_count = len(state.get("repos", []))
        leads_count = len(state.get("leads", []))
        candidates_count = len(state.get("candidates", []))

        # Milestone volumes
        milestones = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000]

        for milestone in milestones:
            if (repos_count == milestone or leads_count == milestone or
                candidates_count == milestone):
                return True

        # API call milestones
        api_calls = counters.get("api_calls", 0)
        api_milestones = [100, 500, 1000, 2500, 5000, 10000]

        for milestone in api_milestones:
            if api_calls == milestone:
                return True

        return False
