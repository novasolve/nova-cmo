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
from pathlib import Path

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
        # Deep copy default config to avoid shared nested state across jobs/agents
        import copy
        base_config = copy.deepcopy(DEFAULT_CONFIG)
        # Merge user config shallowly on top (keeps nested defaults unless overridden)
        if config:
            # For nested dicts, merge keys without sharing references
            for key, value in config.items():
                if isinstance(value, dict) and isinstance(base_config.get(key), dict):
                    merged = copy.deepcopy(base_config.get(key))
                    merged.update(value)
                    base_config[key] = merged
                else:
                    base_config[key] = value
        self.config = base_config
        # Ensure default_icp is populated so state.icp is never empty
        try:
            if not isinstance(self.config.get("default_icp"), dict):
                self.config["default_icp"] = {}
            icp = self.config["default_icp"]
            # Populate from top-level fallbacks if missing
            if not icp.get("languages"):
                langs = self.config.get("languages") or []
                icp["languages"] = langs if isinstance(langs, list) else [langs]
            if not icp.get("topics"):
                topics = self.config.get("include_topics") or []
                icp["topics"] = topics if isinstance(topics, list) else [topics]
            if not icp.get("stars_range"):
                icp["stars_range"] = self.config.get("stars_range", "50..1000")
            if not icp.get("activity_days"):
                icp["activity_days"] = int(self.config.get("activity_days", 90))
            self.config["default_icp"] = icp
        except Exception:
            # Non-fatal; leave as-is if anything goes wrong
            pass
        # Initialize all tools first
        self.tools = self._initialize_tools()

        # Create tool schemas for binding to LLM
        tool_schemas = self._create_tool_schemas()

        # Initialize LLM with tool binding
        llm_cfg = self.config.get("llm", {}) if isinstance(self.config.get("llm"), dict) else {}
        model_name = llm_cfg.get("model", "gpt-4o-mini")
        temperature = float(llm_cfg.get("temperature", 0.0))
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
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

        # Pause/Resume state management (per-job to avoid cross-job interference)
        self._pause_requested = set()  # set of job_ids
        self._job_states = {}  # job_id -> saved state for resume
        # Checkpoint scheduling (per-job)
        self._last_checkpoint_time_by_job = {}
        self._last_checkpointed_stage_by_job = {}

        # Error handling and retry logic
        from ..core.state import ErrorHandler
        self.error_handler = ErrorHandler(self.config)

        # Initialize Toolbelt for centralized execution (idempotency, retries, PII redaction)
        try:
            from ..tools.toolbelt import Toolbelt
            self.toolbelt = Toolbelt(self.tools, config=self.config)
        except Exception:
            self.toolbelt = None

        # Artifact management
        from ..core.artifacts import get_artifact_manager
        self.artifact_manager = get_artifact_manager(self.config)

        # Initialize beautiful logging system
        self.beautiful_logger = None  # Will be set per job

        # Configure logger level
        try:
            level_name = str(self.config.get("log_level", "INFO")).upper()
            logger.setLevel(getattr(logging, level_name, logging.INFO))
        except Exception:
            logger.setLevel(logging.INFO)

    def request_pause(self, job_id: str):
        """Request to pause a running job"""
        logger.info(f"Pause requested for job {job_id}")
        self._pause_requested.add(job_id)

    def request_resume(self, job_id: str):
        """Request to resume a paused job"""
        logger.info(f"Resume requested for job {job_id}")
        self._pause_requested.discard(job_id)

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

    def is_pause_requested(self, job_id: str) -> bool:
        """Check if pause has been requested for this job"""
        return job_id in self._pause_requested

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
                "description": "Get detailed GitHub user profiles for multiple users. Use this for batch enrichment. Keep batches small (<= 20 users) to avoid large payloads and rate limits.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "logins": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of GitHub usernames to enrich (max ~20 per call)"
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

    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize all tools with configuration"""
        tools = {}

        # GitHub tools
        if self.config.get("GITHUB_TOKEN"):
            tools["search_github_repos"] = SearchGitHubRepos(self.config["GITHUB_TOKEN"], default_icp=self.config.get("default_icp", {}))
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
        if self.config.get("INSTANTLY_API_KEY"):
            tools["render_copy"] = RenderCopy()
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

        # Export tools
        tools["export_csv"] = ExportCSV(self.config.get("EXPORT_DIR", "./exports"))
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
            if state.get("ended"):
                return END
            if state.get("counters", {}).get("steps", 0) >= self.config.get("max_steps", 40):
                # Mark state as ended due to max steps for clearer finalization
                try:
                    state["ended"] = True
                    state["current_stage"] = state.get("current_stage", "completed")
                    state["end_reason"] = "max_steps_reached"
                except Exception:
                    pass
                return END
            return "agent"

        workflow.add_conditional_edges("agent", should_end)

        # Compile without any checkpointer or config
        return workflow.compile()

    async def _agent_step(self, state: RunState) -> Dict[str, Any]:
        """Main agent step - decides what tool to use next and executes it"""
        tool_calls = []  # Initialize to avoid scoping issues

        try:
            state = self._ensure_state_basics(state)
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
                response = type("Resp", (), {"content": "", "tool_calls": []})()
            except Exception as e:
                # Broadly handle auth/model/network errors to avoid aborting the step entirely.
                logger.error(f"LLM call failed: {e}")
                state.setdefault("errors", []).append({
                    "stage": "agent_step",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "timestamp": datetime.now().isoformat(),
                })
                # Proceed with empty response so auto-progress can kick in and counters still advance
                response = type("Resp", (), {"content": "", "tool_calls": []})()
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                state.setdefault("errors", []).append({
                    "stage": "agent_step",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "timestamp": datetime.now().isoformat(),
                })
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
            # Trim conversation history to control prompt size
            self._trim_history(state)

            # Safeguard against repeated no-tool-call responses
            if not tool_calls:
                state.setdefault("counters", {})
                state["counters"]["no_tool_call_streak"] = state["counters"].get("no_tool_call_streak", 0) + 1
                limit = self.config.get("no_tool_call_limit", 3)
                if state["counters"]["no_tool_call_streak"] >= limit:
                    logger.warning(f"No tool calls for {state['counters']['no_tool_call_streak']} consecutive steps; marking job failed.")
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
                else:
                    logger.info("No tool calls, evaluating auto-progress if enabled")

            # Reset the no-tool-call streak on valid tool calls
            state.setdefault("counters", {})
            if state["counters"].get("no_tool_call_streak"):
                state["counters"]["no_tool_call_streak"] = 0

            # Execute tool calls with centralized toolbelt (idempotency + retries) when available
            for call in tool_calls:
                tool_name = call.get("name")
                if tool_name and tool_name in self.tools:
                    job_id = state.get("job_id")
                    logger.info(f"Executing tool: {tool_name} for job {job_id}", extra={"structured": {"event": "tool_started", "tool": tool_name, "job_id": job_id}})
                    try:
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
                            self._trim_history(state)

                        # If we cannot safely hydrate required args, skip executing this tool
                        if hydrated_args is None:
                            logger.info(f"Skipping tool {tool_name} due to insufficient arguments after hydration")
                            continue

                        # Pass through job_id and dry_run for idempotency and gating
                        hydrated_args = dict(hydrated_args)
                        hydrated_args.setdefault("job_id", state.get("job_id"))
                        hydrated_args.setdefault("dry_run", bool(self.config.get("features", {}).get("dry_run", False)))
                        # Add beautiful_logger to all tool executions
                        hydrated_args['beautiful_logger'] = self.beautiful_logger

                        if getattr(self, "toolbelt", None):
                            result = await self.toolbelt.execute(
                                tool_name,
                                job_id=state.get("job_id"),
                                args=hydrated_args,
                            )
                        else:
                            # Fallback direct execution with retry
                            result = await self.error_handler.execute_with_retry(tool.execute, **hydrated_args)

                        # Store result
                        state = self._reduce_tool_result(state, tool_name, result)
                        self.stats["tools_executed"] += 1

                        logger.info(
                            f"Tool {tool_name} executed successfully",
                            extra={"structured": {"event": "tool_completed", "tool": tool_name, "job_id": job_id, "success": True}}
                        )

                        # Append a function-style summary to conversation history for LLM awareness
                        try:
                            summary_msg = self._summarize_tool_result(tool_name, result, state)
                            if summary_msg:
                                state.setdefault("history", []).append({
                                    "type": "ai",
                                    "content": summary_msg,
                                    "timestamp": datetime.now().isoformat(),
                                })
                                self._trim_history(state)
                        except Exception:
                            # Non-fatal if summarization fails
                            pass

                        # Check if this is the done tool
                        if tool_name == "done":
                            state["ended"] = True
                            state["end_reason"] = "done"
                            logger.info(
                                "Done tool called - ending workflow",
                                extra={"structured": {"event": "workflow_done", "job_id": job_id}}
                            )
                            break

                    except Exception as e:
                        logger.error(
                            f"Tool {tool_name} execution failed: {e}",
                            extra={"structured": {"event": "tool_failed", "tool": tool_name, "job_id": job_id, "error": str(e)}}
                        )
                        error_result = ToolResult(success=False, error=str(e))
                        state = self._reduce_tool_result(state, tool_name, error_result)
                        self.stats["errors_encountered"] += 1

            # Fallback auto-progression if enabled
            if not state.get("ended") and bool(self.config.get("features", {}).get("enable_auto_progress", True)):
                try:
                    state = await self._auto_progress(state)
                except Exception as e:
                    logger.warning(f"Auto-progress block encountered an error: {e}")

            # Update counters
            state.setdefault("counters", {})
            state["counters"]["steps"] = state["counters"].get("steps", 0) + 1

            # Log state persistence info for debugging (demoted to DEBUG to reduce noise)
            logger.debug(
                f"Agent step completed - executed {len(tool_calls)} tools, ended: {state.get('ended')}, steps: {state['counters']['steps']}"
            )

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
            # Ensure steps advance even on failure to avoid 0-step jobs
            state["counters"]["steps"] = state["counters"].get("steps", 0) + 1

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
            # Only treat as a lead if an email is present; otherwise keep as candidate
            profile = result.data.get("profile", {})
            state.setdefault("leads", [])
            state.setdefault("candidates", [])

            def _valid_email(addr: str) -> bool:
                return bool(addr) and "@" in addr and not str(addr).endswith("@users.noreply.github.com")

            login = profile.get("login")
            email = profile.get("email")
            leads_index = {lead.get("login"): idx for idx, lead in enumerate(state["leads"]) if lead.get("login")}
            cand_index = {cand.get("login"): idx for idx, cand in enumerate(state["candidates"]) if isinstance(cand, dict) and cand.get("login")}

            if _valid_email(email):
                if login in leads_index:
                    i = leads_index[login]
                    state["leads"][i] = {**state["leads"][i], **profile, "email": email}
                else:
                    state["leads"].append({**profile, "email": email})
                # Remove from candidates if present
                if login in cand_index:
                    try:
                        state["candidates"].pop(cand_index[login])
                    except Exception:
                        pass
            else:
                # Keep/update under candidates; do not add to leads yet
                if login in cand_index:
                    j = cand_index[login]
                    state["candidates"][j] = {**state["candidates"][j], **profile}
                else:
                    state["candidates"].append({**profile, "enriched": True})

        elif tool_name == "enrich_github_users" and result.success:
            # Handle batched user enrichment; only add to leads if email present
            profiles = result.data.get("profiles", [])
            state.setdefault("leads", [])
            state.setdefault("candidates", [])

            def _valid_email(addr: str) -> bool:
                return bool(addr) and "@" in addr and not str(addr).endswith("@users.noreply.github.com")

            leads_index = {lead.get("login"): idx for idx, lead in enumerate(state["leads"]) if lead.get("login")}
            cand_index = {cand.get("login"): idx for idx, cand in enumerate(state["candidates"]) if isinstance(cand, dict) and cand.get("login")}

            for profile in profiles:
                if profile.get("enriched") == False:
                    logger.warning(f"Failed to enrich user {profile.get('login')}: {profile.get('error')}")
                    continue
                login = profile.get("login")
                email = profile.get("email")
                if _valid_email(email):
                    if login in leads_index:
                        i = leads_index[login]
                        state["leads"][i] = {**state["leads"][i], **profile, "email": email}
                    else:
                        state["leads"].append({**profile, "email": email})
                        leads_index[login] = len(state["leads"]) - 1
                    # Remove from candidates if present
                    if login in cand_index:
                        try:
                            state["candidates"].pop(cand_index[login])
                        except Exception:
                            pass
                else:
                    # Keep/update as candidate until we find an email
                    if login in cand_index:
                        j = cand_index[login]
                        state["candidates"][j] = {**state["candidates"][j], **profile}
                    else:
                        state["candidates"].append({**profile, "enriched": True})
                        cand_index[login] = len(state["candidates"]) - 1
            state["current_stage"] = "enrichment"

        elif tool_name == "find_commit_emails" and result.success:
            # Move profile to leads when an email is discovered
            login = result.data.get("login")
            emails = result.data.get("emails", [])
            if login and emails:
                email = emails[0]
                leads_index = {lead.get("login"): idx for idx, lead in enumerate(state.get("leads", [])) if lead.get("login")}
                if login in leads_index:
                    state["leads"][leads_index[login]]["email"] = email
                else:
                    # Try to find in candidates and move it over
                    cand_list = state.get("candidates", [])
                    cand_index = {cand.get("login"): idx for idx, cand in enumerate(cand_list) if isinstance(cand, dict) and cand.get("login")}
                    if login in cand_index:
                        profile = {**cand_list[cand_index[login]], "email": email}
                        try:
                            cand_list.pop(cand_index[login])
                        except Exception:
                            pass
                        state.setdefault("leads", []).append(profile)
                    else:
                        # As a fallback, create a minimal lead with login/email
                        state.setdefault("leads", []).append({"login": login, "email": email})
            state["current_stage"] = "validation"

        elif tool_name == "find_commit_emails_batch" and result.success:
            # Handle batched email lookup; move from candidates into leads as emails are found
            user_emails = result.data.get("user_emails", {})
            state.setdefault("leads", [])
            leads_index = {lead.get("login"): idx for idx, lead in enumerate(state.get("leads", [])) if lead.get("login")}
            cand_list = state.get("candidates", [])
            cand_index = {cand.get("login"): idx for idx, cand in enumerate(cand_list) if isinstance(cand, dict) and cand.get("login")}
            for login, email_data in user_emails.items():
                emails = (email_data or {}).get("emails", [])
                if not emails:
                    continue
                email = emails[0]
                if login in leads_index:
                    state["leads"][leads_index[login]]["email"] = email
                elif login in cand_index:
                    profile = {**cand_list[cand_index[login]], "email": email}
                    try:
                        cand_list.pop(cand_index[login])
                    except Exception:
                        pass
                    state["leads"].append(profile)
                    leads_index[login] = len(state["leads"]) - 1
                else:
                    state["leads"].append({"login": login, "email": email})
                    leads_index[login] = len(state["leads"]) - 1
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
            # Attach ICP score to the corresponding lead profile if present
            profile = result.data.get("profile_summary")
            final_score = result.data.get("final_score")
            is_qualified = result.data.get("is_qualified")
            # Best effort: match by login in summary text
            if profile:
                import re
                m = re.search(r"\(([^)]+)\)", profile)
                login = m.group(1) if m else None
            else:
                login = None
            if login:
                index = {lead.get("login"): idx for idx, lead in enumerate(state.get("leads", [])) if lead.get("login")}
                if login in index:
                    lead = state["leads"][index[login]]
                    lead["icp_score"] = final_score
                    lead["icp_qualified"] = is_qualified
            state["current_stage"] = "scoring"

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

            if tool_name == "enrich_github_users":
                # Normalize/validate provided logins or fallback to candidates
                import re

                def _normalize_list(value):
                    # Accept comma/space separated string or list of strings
                    if isinstance(value, str):
                        parts = [p.strip() for p in re.split(r"[\s,]+", value) if p.strip()]
                    elif isinstance(value, list):
                        parts = []
                        for v in value:
                            if isinstance(v, str):
                                parts.extend([p.strip() for p in re.split(r"[\s,]+", v) if p.strip()])
                            else:
                                parts.append(str(v))
                    else:
                        parts = []
                    # Strip leading '@' and dedupe while preserving order
                    seen_local = set()
                    normed: list[str] = []
                    for p in parts:
                        token = p.lstrip('@')
                        if token and token not in seen_local:
                            normed.append(token)
                            seen_local.add(token)
                    return normed

                def _filter_valid(logins_list):
                    valid = []
                    pattern = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
                    for l in logins_list:
                        # Basic GitHub login constraints; skip very short/invalid tokens
                        if 2 <= len(l) <= 39 and pattern.match(l):
                            valid.append(l)
                    return valid

                provided = hydrated.get("logins")
                if provided:
                    normed = _normalize_list(provided)
                    valid = _filter_valid(normed)
                    if valid:
                        hydrated["logins"] = valid[:25]
                        note = f"[auto] Normalized enrich_github_users logins: {len(hydrated['logins'])}"
                        return hydrated, note
                    # Fall through to candidates if provided list is invalid/empty after filtering

                # Prefer candidates from state
                candidates = state.get("candidates", [])
                unique_logins = []
                seen = set()
                for c in candidates:
                    login = c.get("login")
                    if login and login not in seen:
                        unique_logins.append(login)
                        seen.add(login)
                if unique_logins:
                    hydrated["logins"] = unique_logins[:25]
                    note = f"[auto] Filled enrich_github_users logins from candidates: {len(hydrated['logins'])}"
                else:
                    return None, "[auto] enrich_github_users skipped: no candidates available."
                return hydrated, note

            if tool_name == "search_github_repos":
                # search_github_repos requires q (query) minimally; hydrate from goal if missing
                if not hydrated.get("q"):
                    hydrated["q"] = state.get("goal", "")
                # Pass ICP to guide search if available
                icp = state.get("icp") or {}
                if icp:
                    hydrated["icp"] = icp
                    # Also surface common qualifiers explicitly if not already present
                    if icp.get("languages") and not hydrated.get("language"):
                        langs = icp.get("languages")
                        hydrated["language"] = langs[0] if isinstance(langs, list) and langs else icp.get("language")
                    if icp.get("stars_range") and not hydrated.get("stars_range"):
                        hydrated["stars_range"] = icp.get("stars_range")
                    if icp.get("activity_days") and not hydrated.get("activity_days"):
                        hydrated["activity_days"] = icp.get("activity_days")
                return hydrated, None

            if tool_name == "find_commit_emails_batch":
                # Build pairs from candidates if not provided
                if not hydrated.get("user_repo_pairs"):
                    import re
                    pattern = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
                    pairs = []
                    seen_pairs = set()
                    for c in state.get("candidates", []):
                        login = c.get("login")
                        repo_full_name = c.get("from_repo")
                        if not (login and repo_full_name):
                            continue
                        if not (2 <= len(login) <= 39 and pattern.match(login)):
                            continue
                        key = (login, repo_full_name)
                        if key in seen_pairs:
                            continue
                        seen_pairs.add(key)
                        pairs.append({"login": login, "repo_full_name": repo_full_name})
                    if pairs:
                        hydrated["user_repo_pairs"] = pairs[:50]
                        note = f"[auto] Filled find_commit_emails_batch pairs: {len(hydrated['user_repo_pairs'])}"
                    else:
                        return None, "[auto] find_commit_emails_batch skipped: no valid candidate repo pairs available."
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
                # Provide ICP to scoring tool for dynamic criteria
                icp = state.get("icp") or {}
                if icp:
                    hydrated["icp"] = icp
                return hydrated, note

            if tool_name == "extract_people":
                # Ensure repos are present and normalized
                repos = hydrated.get("repos")
                if not repos:
                    repos = state.get("repos", [])
                    if not repos:
                        return None, "[auto] extract_people skipped: no repositories available."
                    hydrated["repos"] = repos[: min(len(repos), int(self.config.get('max_repos', 600)))]
                    note = f"[auto] Filled extract_people repos from state: {len(hydrated['repos'])}"
                elif isinstance(repos, list) and repos and isinstance(repos[0], str):
                    # Normalize list of repo full_names -> minimal repo dicts
                    normed = []
                    for r in repos:
                        if isinstance(r, str) and "/" in r:
                            normed.append({"full_name": r, "name": r.split("/")[-1], "stars": 0})
                    if not normed:
                        return None, "[auto] extract_people skipped: invalid repo list."
                    hydrated["repos"] = normed
                    note = f"[auto] Normalized extract_people repos from strings: {len(normed)}"
                return hydrated, note

            # Default: return original args without note
            return hydrated, None
        except Exception:
            return args, None

    def _build_system_prompt(self, state: RunState) -> str:
        """Build the system prompt for the agent"""
        caps = self.config

        # Include a compact ICP summary to guide the model
        icp = state.get("icp") or {}
        icp_parts = []
        try:
            langs = icp.get("languages") or icp.get("language")
            if isinstance(langs, list):
                icp_parts.append(f"languages={', '.join(map(str, langs))}")
            elif isinstance(langs, str):
                icp_parts.append(f"language={langs}")
            if icp.get("stars_range"):
                icp_parts.append(f"stars={icp['stars_range']}")
            else:
                if icp.get("stars_min") is not None:
                    icp_parts.append(f"stars_min={icp['stars_min']}")
                if icp.get("stars_max") is not None:
                    icp_parts.append(f"stars_max={icp['stars_max']}")
            if icp.get("activity_days") is not None:
                icp_parts.append(f"active_within_days={icp['activity_days']}")
            incl = icp.get("include_topics") or icp.get("topics")
            if incl:
                icp_parts.append(f"include_topics={', '.join(map(str, incl))}")
            excl = icp.get("exclude_topics")
            if excl:
                icp_parts.append(f"exclude_topics={', '.join(map(str, excl))}")
        except Exception:
            pass
        icp_summary = ("; ".join(icp_parts)) if icp_parts else "unspecified"

        prompt = f"""You are a CMO operator. Your task: {state['goal']}

ICP CONTEXT: {icp_summary}

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

CRITICAL: Call done("Completed") immediately after any major step if you have meaningful results.

RULES TO AVOID LOOPS:
- If repositories already exist in state, do NOT call search_github_repos again. Proceed to extract_people.
- Use the assistant function result summaries in the conversation to update your plan. Do not repeat tools that already succeeded unless new inputs are provided.
- If leads have emails, proceed towards mx_check, export_csv and done.

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

            # Initialize beautiful logging for this job
            self.beautiful_logger = setup_beautiful_logging(self.config, job_meta.job_id)
            self.beautiful_logger.start_stage("initialization", f"Starting campaign: {goal}")

            # Initialize state
            initial_state = RunState(
                **job_meta.to_dict(),
                state_version=1,
                icp=self.config.get("default_icp", {}),
                config=self.config,
                current_stage="initialization",
                counters={"steps": 0, "api_calls": 0, "tokens": 0, "errors": 0, "tool_errors": 0},
                ended=False,  # Explicitly initialize ended flag
                end_reason="",
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

                    # Extract and persist progress information
                    progress_info = self._extract_progress_info(step_result)
                    if hasattr(step_result, 'setdefault'):
                        step_result.setdefault("progress", {})
                        step_result["progress"] = progress_info
                    if progress_callback:
                        await progress_callback(progress_info)

                    # Check for pause request (per-job)
                    if self.is_pause_requested(job_meta.job_id):
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

                    # Periodic checkpointing (per-job schedule)
                    if await self._should_checkpoint(step_result):
                        await self._save_checkpoint(job_meta.job_id, step_result, "periodic")

                logger.info("Job finished via astream; evaluating final status")

            except Exception as e:
                logger.error(f"Job execution failed via astream: {e}")
                raise

            # Update stats
            self.stats["jobs_processed"] += 1

            # Determine success/failure from final_state
            # Flatten nested state if graph wrapped it under node key (e.g., {"agent": {...}})
            try:
                if isinstance(final_state, dict) and isinstance(final_state.get("agent"), dict):
                    final_state = final_state.get("agent")
            except Exception:
                pass
            job_failed = self._is_failure_state(final_state)
            job_status = "failed" if job_failed else "completed"

            # Log completion with beautiful logging
            if self.beautiful_logger:
                if job_failed:
                    self.beautiful_logger.end_stage(f"Campaign failed", status="failed")
                else:
                    # Extract summary stats for completion log
                    leads_count = len(final_state.get("leads", []))
                    emails_sent = len(final_state.get("to_send", []))
                    repos_found = len(final_state.get("repos", []))

                    self.beautiful_logger.end_stage(
                        f"Campaign completed successfully",
                        status="completed",
                        leads=leads_count,
                        emails=emails_sent,
                        repos=repos_found
                    )

            # Finalize job with comprehensive artifact collection
            finalization_result = await self._finalize_job(job_meta.job_id, final_state, job_status)

            # Auto-save output files to logs directory
            try:
                await self._save_output_files_to_logs(job_meta.job_id, final_state, finalization_result)
            except Exception as e:
                logger.warning(f"Failed to save output files: {e}")

            return {
                "success": not job_failed,
                "job_id": job_meta.job_id,
                "final_state": final_state,
                "artifacts": finalization_result.get("artifacts", []),
                "report": finalization_result.get("report"),
            }
        except Exception as e:
            # Outer run_job failure handler
            logger.error(f"Job execution failed: {e}")
            job_id = job_meta.job_id if job_meta else "unknown"

            # Log error with beautiful logging
            if self.beautiful_logger:
                self.beautiful_logger.log_error(e, "job_execution")

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

        # Clear pause flag for this job on resume
        self._pause_requested.discard(job_id)

        # Continue from saved state
        final_state = None
        max_steps = self.config.get("max_steps", 40)

        try:
            async for step_result in self.graph.astream(saved_state, {"recursion_limit": max_steps + 10}):
                final_state = step_result

                # Extract and persist progress information
                progress_info = self._extract_progress_info(step_result)
                if hasattr(step_result, 'setdefault'):
                    step_result.setdefault("progress", {})
                    step_result["progress"] = progress_info
                if progress_callback:
                    await progress_callback(progress_info)

                # Check for pause request (can pause again during resume)
                if self.is_pause_requested(job_id):
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

            logger.info(f"Job {job_id} resumed and finished; evaluating final status")

            # Clear saved state since job is complete
            self.clear_job_state(job_id)

            # Update stats
            self.stats["jobs_processed"] += 1

            # Determine success/failure from final_state
            # Flatten nested state if graph wrapped it under node key (e.g., {"agent": {...}})
            try:
                if isinstance(final_state, dict) and isinstance(final_state.get("agent"), dict):
                    final_state = final_state.get("agent")
            except Exception:
                pass
            job_failed = self._is_failure_state(final_state)
            job_status = "failed" if job_failed else "completed"

            # Finalize job after resume
            finalization_result = await self._finalize_job(job_id, final_state, job_status)

            return {
                "success": not job_failed,
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
        # Default to a meaningful initial stage rather than "unknown"
        current_stage = state.get("current_stage", "initialization")

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

            # Create checkpoints directory
            checkpoints_dir = Path(self.config.get("directories", {}).get("checkpoints", "./checkpoints"))
            checkpoints_dir.mkdir(exist_ok=True)

            # Create checkpoint file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            checkpoint_file = checkpoints_dir / f"{job_id}_{checkpoint_type}_{timestamp}.json"

            # Sanitize state to avoid oversized checkpoints (e.g., huge tool arg arrays)
            def _sanitize_for_checkpoint(obj, depth: int = 0):
                try:
                    # Limit recursion depth for safety
                    if depth > 4:
                        return "__truncated__"
                    if isinstance(obj, dict):
                        sanitized = {}
                        for k, v in obj.items():
                            # Special handling: trim large args lists in tool calls
                            if k == "tool_calls" and isinstance(v, list):
                                trimmed_calls = []
                                for call in v[:5]:  # cap number of calls per message
                                    if isinstance(call, dict):
                                        call_copy = dict(call)
                                        args = call_copy.get("args")
                                        if isinstance(args, dict):
                                            # Truncate known large fields like 'logins'
                                            if isinstance(args.get("logins"), list) and len(args["logins"]) > 50:
                                                total = len(args["logins"])
                                                sample = args["logins"][:10]
                                                call_copy["args"] = {**args, "logins": sample + [f"__omitted_{total-10}_items__"]}
                                        trimmed_calls.append(call_copy)
                                    else:
                                        trimmed_calls.append(call)
                                sanitized[k] = trimmed_calls
                            elif k == "history" and isinstance(v, list):
                                # Keep only last N messages
                                sanitized[k] = [
                                    _sanitize_for_checkpoint(m, depth + 1)
                                    for m in v[-50:]
                                ]
                            elif k in ("repos", "candidates", "leads") and isinstance(v, list) and len(v) > 1000:
                                # Cap extremely large top-level collections
                                sanitized[k] = v[:1000] + [f"__omitted_{len(v)-1000}_items__"]
                            else:
                                sanitized[k] = _sanitize_for_checkpoint(v, depth + 1)
                        return sanitized
                    elif isinstance(obj, list):
                        # Cap list length to a reasonable maximum for checkpoints
                        max_len = 2000 if depth == 0 else 500
                        if len(obj) > max_len:
                            return obj[:max_len] + [f"__omitted_{len(obj)-max_len}_items__"]
                        return [ _sanitize_for_checkpoint(i, depth + 1) for i in obj ]
                    else:
                        return obj
                except Exception:
                    return obj

            sanitized_state = _sanitize_for_checkpoint(state)

            # Prepare checkpoint data
            checkpoint_data = {
                "job_id": job_id,
                "checkpoint_type": checkpoint_type,
                "timestamp": datetime.now().isoformat(),
                "state": sanitized_state,
                "counters": sanitized_state.get("counters", {}),
                "progress": sanitized_state.get("progress", {}),
            }

            # Save to file (UTF-8, preserve Unicode characters)
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, default=str, ensure_ascii=False)

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
        """Determine if we should create a checkpoint using hybrid strategy.

        Adds throttling and configurability to stage-based checkpoints to avoid
        excessive checkpointing on rapid stage transitions in short runs.
        """
        import time

        counters = state.get("counters", {})
        current_step = counters.get("steps", 0)
        current_stage = state.get("current_stage", "")
        job_id = state.get("job_id")

        # Get checkpoint configuration
        checkpoint_config = self.config.get("job_config", {}).get("checkpoints", {})
        time_interval = checkpoint_config.get("time_interval", 300)  # 5 minutes default
        step_interval = checkpoint_config.get("step_interval", 50)   # Every 50 steps
        volume_interval = checkpoint_config.get("volume_interval", 1000)  # Every 1000 leads

        # New: stage-based controls
        stage_enabled = checkpoint_config.get("enable_stage", True)
        stage_min_interval = checkpoint_config.get("stage_min_interval", 120)  # 2 minutes
        stages_only = checkpoint_config.get("stages")  # Optional: list[str]
        if isinstance(stages_only, list) and not stages_only:
            # Treat empty list as "no stage restriction"
            stages_only = None

        # Time-based checkpointing
        # Use per-job last checkpoint time to avoid cross-job interference
        last_checkpoint_time = self._last_checkpoint_time_by_job.get(job_id, 0)
        current_time = time.time()

        if current_time - last_checkpoint_time >= time_interval:
            if job_id:
                self._last_checkpoint_time_by_job[job_id] = current_time
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

        # Stage transition checkpointing (now configurable + throttled)
        if stage_enabled and current_stage:
            # Optional allowlist of stages to checkpoint on
            if stages_only is None or current_stage in stages_only:
                last_checkpointed_stage = self._last_checkpointed_stage_by_job.get(job_id)
                if last_checkpointed_stage != current_stage:
                    # Throttle: ensure a minimum time since last checkpoint
                    if current_time - last_checkpoint_time >= stage_min_interval:
                        if job_id:
                            self._last_checkpointed_stage_by_job[job_id] = current_stage
                            # Update last checkpoint time to enforce throttle going forward
                            self._last_checkpoint_time_by_job[job_id] = current_time
                        logger.debug(
                            f"Stage transition checkpoint triggered: {current_stage} (min_interval={stage_min_interval}s)"
                        )
                        return True

        # Milestone-based checkpointing
        if self._is_significant_milestone(state):
            logger.debug("Significant milestone checkpoint triggered")
            return True

        return False

    def _is_failure_state(self, state: RunState) -> bool:
        """Determine if the final state represents a failure."""
        try:
            if not state:
                return True
            # Explicit failure stage
            if state.get("current_stage") == "failed":
                return True
            # Critical error recorded
            for err in state.get("errors", []) or []:
                if err.get("critical") is True:
                    return True
            # Ended without completion
            if state.get("ended") and state.get("current_stage") != "completed":
                return True
            return False
        except Exception:
            return True

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
            # Ensure we work on a flattened view of state for exporters and report
            flat_state = final_state
            try:
                if isinstance(final_state, dict) and isinstance(final_state.get("agent"), dict):
                    flat_state = final_state.get("agent")
            except Exception:
                pass

            artifacts = await self._collect_artifacts(job_id, flat_state, job_status)

            # Save final checkpoint
            if flat_state:
                await self._save_checkpoint(job_id, flat_state, job_status)

            # Clean up temporary resources
            await self._cleanup_job_resources(job_id, job_status)

            # Generate final report
            final_report = self._generate_final_report(job_id, flat_state, artifacts, job_status)

            return {
                "job_id": job_id,
                "status": job_status,
                "artifacts": artifacts,
                "final_state": flat_state,
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
            # Build summary with unique emails and counts
            def _normalize_email(em: str) -> str:
                return (em or "").strip().lower()

            unique_emails_set = set()
            leads_with_email = 0
            for lead in leads or []:
                try:
                    email = lead.get("email") if isinstance(lead, dict) else None
                    if isinstance(email, str) and email.strip():
                        leads_with_email += 1
                        unique_emails_set.add(_normalize_email(email))
                    # Also consider optional multi-email fields
                    emails_list = lead.get("emails") if isinstance(lead, dict) else None
                    if isinstance(emails_list, list):
                        # Do not double count leads_with_email for additional addresses
                        for em in emails_list:
                            if isinstance(em, str) and em.strip():
                                unique_emails_set.add(_normalize_email(em))
                except Exception:
                    continue

            summary = {
                "total_leads": len(leads or []),
                "leads_with_email": leads_with_email,
                "unique_email_count": len(unique_emails_set),
                "unique_emails": sorted(unique_emails_set),
            }

            data = {
                "job_id": job_id,
                "job_status": job_status,
                "export_timestamp": datetime.now().isoformat(),
                "data_type": "leads",
                "count": len(leads),
                "summary": summary,
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

    def _trim_history(self, state: RunState) -> None:
        """Trim conversation history to the last N entries according to config."""
        try:
            limit = int(self.config.get("history_limit", 120))
        except Exception:
            limit = 120
        history = state.get("history")
        if isinstance(history, list) and len(history) > limit:
            # Keep the most recent entries
            state["history"] = history[-limit:]

    async def _save_output_files_to_logs(self, job_id: str, final_state: RunState, finalization_result: Dict[str, Any]):
        """Save campaign output files to logs directory for easy access"""
        try:
            import csv
            import shutil
            from pathlib import Path

            logs_dir = Path(self.config.get("directories", {}).get("logs", "./logs"))
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Get leads with emails
            leads_with_emails = [l for l in final_state.get("leads", []) if l.get("email") and "@" in str(l.get("email", ""))]

            if leads_with_emails:
                # Create CSV file in logs directory
                csv_filename = f"{job_id}_leads_with_emails.csv"
                csv_path = logs_dir / csv_filename

                with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['login', 'name', 'email', 'company', 'location', 'bio', 'public_repos', 'followers', 'html_url', 'blog', 'twitter_username']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()

                    for lead in leads_with_emails:
                        writer.writerow({
                            'login': lead.get('login', ''),
                            'name': lead.get('name', ''),
                            'email': lead.get('email', ''),
                            'company': lead.get('company', ''),
                            'location': lead.get('location', ''),
                            'bio': lead.get('bio', ''),
                            'public_repos': lead.get('public_repos', ''),
                            'followers': lead.get('followers', ''),
                            'html_url': lead.get('html_url', ''),
                            'blog': lead.get('blog', ''),
                            'twitter_username': lead.get('twitter_username', '')
                        })

                # Create campaign summary report
                report_filename = f"{job_id}_campaign_summary.md"
                report_path = logs_dir / report_filename

                # Generate summary report
                repos_count = len(final_state.get("repos", []))
                candidates_count = len(final_state.get("candidates", []))
                leads_count = len(leads_with_emails)

                report_content = f"""# Campaign Summary - {job_id}

## 📊 Results Overview
- **Repositories Found:** {repos_count}
- **Contributors Extracted:** {candidates_count}
- **Qualified Leads with Emails:** {leads_count}
- **Email Discovery Rate:** {(leads_count/candidates_count*100) if candidates_count > 0 else 0:.1f}%

## 📁 Output Files
- **Lead List:** {csv_filename}
- **Full Checkpoint:** {job_id}_completed.json
- **Campaign Log:** {job_id}.log

## 🎯 Top Leads Found
"""

                # Add top leads to summary
                for i, lead in enumerate(leads_with_emails[:5], 1):
                    name = lead.get('name') or lead.get('login', 'Unknown')
                    email = lead.get('email', '')
                    company = lead.get('company', 'Independent')
                    followers = lead.get('followers', 0)

                    report_content += f"{i}. **{name}** - {email}\n"
                    report_content += f"   - Company: {company}\n"
                    report_content += f"   - GitHub: {followers} followers\n\n"

                report_content += f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"

                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)

                # Log the file creation with beautiful logging
                if self.beautiful_logger:
                    self.beautiful_logger.log_stage_event(
                        "output_saved",
                        f"Output files saved to logs: {csv_filename}, {report_filename}",
                        csv_file=str(csv_path),
                        report_file=str(report_path),
                        leads_count=leads_count
                    )
                else:
                    logger.info(f"Output files saved to logs: {csv_filename}, {report_filename}")

        except Exception as e:
            logger.warning(f"Failed to save output files to logs: {e}")

    async def _auto_progress(self, state: RunState) -> RunState:
        """Auto-progress through pipeline stages when LLM omits obvious next steps."""
        repos = state.get("repos", [])
        candidates = state.get("candidates", [])
        leads = state.get("leads", [])

        # If we already have repos but no candidates, extract people
        if repos and not candidates and "extract_people" in self.tools:
            logger.info("Auto-progress: executing extract_people based on repos present")

            # Log stage transition with beautiful logging
            if self.beautiful_logger:
                self.beautiful_logger.start_stage("extraction", f"Extracting contributors from {len(repos)} repositories")

            try:
                tool = self.tools["extract_people"]
                result = await self.error_handler.execute_with_retry(tool.execute, repos=repos, top_authors_per_repo=5)
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
                        self._trim_history(state)
                except Exception:
                    pass

                # Log stage completion with beautiful logging
                if self.beautiful_logger:
                    candidates_found = len(state.get("candidates", []))
                    self.beautiful_logger.end_stage(f"Extracted {candidates_found} contributors", found=candidates_found)

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
                try:
                    tool = self.tools["enrich_github_users"]
                    result = await self.error_handler.execute_with_retry(tool.execute, logins=unique_logins[:25], beautiful_logger=self.beautiful_logger)
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
                            self._trim_history(state)
                    except Exception:
                        pass
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
                    try:
                        # Track before/after counts to detect progress
                        before_with_email = len([l for l in state.get("leads", []) if l.get("email")])
                        tool = self.tools["find_commit_emails_batch"]
                        # Pull discovery tuning from config
                        es = self.config.get("email_search", {}) if isinstance(self.config.get("email_search"), dict) else {}
                        days = int(es.get("days", 90))
                        batch_size = int(es.get("batch_size", 5))
                        repos_per_user = int(es.get("repos_per_user", 5))
                        commits_per_repo = int(es.get("commits_per_repo", 10))
                        include_committer_email = bool(es.get("include_committer_email", False))

                        result = await self.error_handler.execute_with_retry(
                            tool.execute,
                            user_repo_pairs=user_repo_pairs[:50],
                            days=days,
                            batch_size=batch_size,
                            repos_per_user=repos_per_user,
                            commits_per_repo=commits_per_repo,
                            include_committer_email=include_committer_email,
                            beautiful_logger=self.beautiful_logger,
                        )
                        state = self._reduce_tool_result(state, "find_commit_emails_batch", result)
                        after_with_email = len([l for l in state.get("leads", []) if l.get("email")])

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
                                self._trim_history(state)
                        except Exception:
                            pass

                        # Detect no-progress attempts and set exhaustion flag to break loops
                        if after_with_email <= before_with_email:
                            streak = state["counters"].get("email_find_noop_streak", 0) + 1
                            state["counters"]["email_find_noop_streak"] = streak
                            # Use configurable threshold for exhaustion
                            noop_threshold = int(es.get("noop_streak_threshold", 2))
                            if streak >= noop_threshold:
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

        # Auto-finalization: if we have leads with emails, export and finish if LLM doesn't
        leads_with_email = [l for l in state.get("leads", []) if l.get("email")]
        target_leads = 0
        try:
            # Check YAML-driven prompt params (e.g., target_leads) under config or metadata
            cfg_params = (
                (state.get("config", {}) or {}).get("prompt_params")
                or (state.get("metadata", {}) or {}).get("prompt_params")
                or {}
            )
            target_leads = int(cfg_params.get("target_leads") or cfg_params.get("target") or 0)
        except Exception:
            target_leads = 0

        # Finish early if we met/exceeded the target (when provided)
        if not state.get("ended") and target_leads > 0 and len(leads_with_email) >= target_leads:
            try:
                # Export leads
                if "export_csv" in self.tools:
                    export_tool = self.tools["export_csv"]
                    job_id = state.get("job_id", "job")
                    export_path = f"{job_id}_leads.csv"
                    export_rows = leads_with_email
                    export_result = await self.error_handler.execute_with_retry(export_tool.execute, rows=export_rows, path=export_path)
                    state = self._reduce_tool_result(state, "export_csv", export_result)
                # Done summary
                if "done" in self.tools:
                    done_tool = self.tools["done"]
                    repos = state.get("repos", [])
                    candidates = state.get("candidates", [])
                    summary_text = f"Campaign completed: {len(leads_with_email)} leads with emails (target {target_leads}), repos={len(repos)}, candidates={len(candidates)}."
                    done_result = await self.error_handler.execute_with_retry(done_tool.execute, summary=summary_text)
                    state = self._reduce_tool_result(state, "done", done_result)
                state["ended"] = True
                state["end_reason"] = "target_leads_met"
                logger.info("Auto-progress: finalized early after meeting target leads")
                return state
            except Exception as e:
                logger.warning(f"Auto-finalization (target) failed: {e}")

        if leads_with_email and not state.get("ended"):
            try:
                # Export leads with email
                if "export_csv" in self.tools:
                    export_tool = self.tools["export_csv"]
                    job_id = state.get("job_id", "job")
                    export_path = f"{job_id}_leads.csv"
                    export_rows = leads_with_email
                    export_result = await self.error_handler.execute_with_retry(export_tool.execute, rows=export_rows, path=export_path)
                    state = self._reduce_tool_result(state, "export_csv", export_result)
                    try:
                        summary_msg = self._summarize_tool_result("export_csv", export_result, state, auto_progress=True)
                        if summary_msg:
                            state.setdefault("history", []).append({
                                "type": "ai",
                                "content": summary_msg,
                                "timestamp": datetime.now().isoformat(),
                            })
                            self._trim_history(state)
                    except Exception:
                        pass

                # Signal completion
                if "done" in self.tools:
                    done_tool = self.tools["done"]
                    # Build unique email list
                    unique_emails = []
                    seen_emails = set()
                    for l in leads_with_email:
                        em = (l.get("email") or "").strip().lower()
                        if em and em not in seen_emails:
                            unique_emails.append(em)
                            seen_emails.add(em)
                    summary_text = (
                        f"Campaign completed: {len(leads_with_email)} leads with emails, "
                        f"unique_emails={len(unique_emails)}, repos={len(repos)}, candidates={len(candidates)}."
                    )
                    done_result = await self.error_handler.execute_with_retry(done_tool.execute, summary=summary_text)
                    state = self._reduce_tool_result(state, "done", done_result)
                    # Write summary header at top of job log, if available
                    try:
                        if self.beautiful_logger and hasattr(self.beautiful_logger, "write_summary_header"):
                            header_lines = [
                                f"Leads with emails: {len(leads_with_email)}",
                                f"Unique emails: {len(unique_emails)}",
                                "",
                                "Emails:",
                            ] + [f"- {e}" for e in unique_emails]
                            self.beautiful_logger.write_summary_header("Campaign Summary", header_lines)
                    except Exception:
                        pass
                    try:
                        summary_msg = self._summarize_tool_result("done", done_result, state, auto_progress=True)
                        if summary_msg:
                            state.setdefault("history", []).append({
                                "type": "ai",
                                "content": summary_msg,
                                "timestamp": datetime.now().isoformat(),
                            })
                            self._trim_history(state)
                    except Exception:
                        pass
                    state["ended"] = True
                    state["end_reason"] = "auto_finalization"
                    logger.info("Auto-progress: finalized job via export and done")
                    return state
            except Exception as e:
                logger.warning(f"Auto-finalization failed: {e}")

        return state

    def _ensure_state_basics(self, state: RunState) -> RunState:
        """Ensure basic state fields are present and valid"""
        if not state.get("ended"):
            state.setdefault("ended", False)
        if not state.get("current_stage"):
            state.setdefault("current_stage", "initialization")
        if not state.get("counters"):
            state.setdefault("counters", {"steps": 0, "api_calls": 0, "tokens": 0, "errors": 0, "tool_errors": 0})
        if not state.get("repos"):
            state.setdefault("repos", [])
        if not state.get("candidates"):
            state.setdefault("candidates", [])
        if not state.get("leads"):
            state.setdefault("leads", [])
        if not state.get("to_send"):
            state.setdefault("to_send", [])
        if not state.get("reports"):
            state.setdefault("reports", {})
        if not state.get("errors"):
            state.setdefault("errors", [])
        if not state.get("checkpoints"):
            state.setdefault("checkpoints", [])
        if not state.get("tool_results"):
            state.setdefault("tool_results", {})
        return state

    async def _auto_progress(self, state: RunState) -> RunState:
        """Auto-progression to avoid stalls by triggering appropriate next tools based on state.

        Returns updated state. Does not modify step counters; caller should handle.
        """
        repos = state.get("repos", [])
        candidates = state.get("candidates", [])
        leads = state.get("leads", [])

        # If we already have repos but no candidates, extract people
        if repos and not candidates and "extract_people" in self.tools:
            logger.info("Auto-progress: executing extract_people based on repos present")
            try:
                tool = self.tools["extract_people"]
                result = await self.error_handler.execute_with_retry(tool.execute, repos=repos, top_authors_per_repo=5)
                state = self._reduce_tool_result(state, "extract_people", result)
                self.stats["tools_executed"] += 1
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
                try:
                    tool = self.tools["enrich_github_users"]
                    result = await self.error_handler.execute_with_retry(tool.execute, logins=unique_logins[:25], beautiful_logger=self.beautiful_logger)
                    state = self._reduce_tool_result(state, "enrich_github_users", result)
                    self.stats["tools_executed"] += 1
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
                    return state
                except Exception as e:
                    logger.warning(f"Auto-progress enrich_github_users failed: {e}")

        # If we have enriched leads but missing emails and have candidates mapping, find emails in batch
        if state.get("leads") and "find_commit_emails_batch" in self.tools and not state.get("email_search_exhausted"):
            leads_without_email = [l for l in state.get("leads", []) if not l.get("email") and not l.get("no_email_found")]
            if leads_without_email and candidates:
                user_repo_pairs = []
                for c in candidates:
                    login = c.get("login")
                    repo_full_name = c.get("from_repo")
                    if login and repo_full_name:
                        user_repo_pairs.append({"login": login, "repo_full_name": repo_full_name})
                if user_repo_pairs:
                    logger.info("Auto-progress: executing find_commit_emails_batch for leads without email")
                    try:
                        before_with_email = len([l for l in state.get("leads", []) if l.get("email")])
                        tool = self.tools["find_commit_emails_batch"]
                        result = await self.error_handler.execute_with_retry(tool.execute, user_repo_pairs=user_repo_pairs[:50], days=90)
                        state = self._reduce_tool_result(state, "find_commit_emails_batch", result)
                        after_with_email = len([l for l in state.get("leads", []) if l.get("email")])
                        self.stats["tools_executed"] += 1
                        try:
                            summary_msg = self._summarize_tool_result(
                                "find_commit_emails_batch", result, state, auto_progress=True, extra_info={
                                    "before": before_with_email,
                                    "after": after_with_email,
                                }
                            )
                            if summary_msg:
                                state.setdefault("history", []).append({
                                    "type": "ai",
                                    "content": summary_msg,
                                    "timestamp": datetime.now().isoformat(),
                                })
                        except Exception:
                            pass
                        if after_with_email <= before_with_email:
                            streak = state["counters"].get("email_find_noop_streak", 0) + 1
                            state["counters"]["email_find_noop_streak"] = streak
                            if streak >= 2:
                                for lead in state.get("leads", []):
                                    if not lead.get("email"):
                                        attempts = lead.get("_email_attempts", 0) + 1
                                        lead["_email_attempts"] = attempts
                                        if attempts >= 2:
                                            lead["no_email_found"] = True
                                state["email_search_exhausted"] = True
                                logger.info("Auto-progress: email search exhausted; marking unresolvable leads and stopping further attempts")
                        else:
                            if state["counters"].get("email_find_noop_streak"):
                                state["counters"]["email_find_noop_streak"] = 0
                        return state
                    except Exception as e:
                        logger.warning(f"Auto-progress find_commit_emails_batch failed: {e}")

        # Auto-finalization: if we have leads with emails, export and finish if LLM doesn't
        leads_with_email = [l for l in state.get("leads", []) if l.get("email")]
        if leads_with_email and not state.get("ended"):
            try:
                if "export_csv" in self.tools:
                    export_tool = self.tools["export_csv"]
                    job_id = state.get("job_id", "job")
                    export_path = f"{job_id}_leads.csv"
                    export_rows = leads_with_email
                    export_result = await self.error_handler.execute_with_retry(export_tool.execute, rows=export_rows, path=export_path)
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
                if "done" in self.tools:
                    done_tool = self.tools["done"]
                    summary_text = f"Campaign completed: {len(leads_with_email)} leads with emails, repos={len(repos)}, candidates={len(candidates)}."
                    done_result = await self.error_handler.execute_with_retry(done_tool.execute, summary=summary_text)
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

        return state
