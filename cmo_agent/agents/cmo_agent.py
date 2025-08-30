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
        self.config = config or DEFAULT_CONFIG.copy()
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
        if self.config.get("INSTANTLY_API_KEY"):
            tools["render_copy"] = RenderCopy()
            tools["send_instantly"] = SendInstantly(self.config["INSTANTLY_API_KEY"])

        # CRM tools
        if self.config.get("ATTIO_API_KEY") and self.config.get("ATTIO_WORKSPACE_ID"):
            tools["sync_attio"] = SyncAttio(
                self.config["ATTIO_API_KEY"],
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

        # Create workflow without any checkpointer
        workflow = StateGraph(RunState)

        # Add main agent node
        workflow.add_node("agent", self._agent_step)

        # Add tool execution nodes
        for tool_name, tool in self.tools.items():
            workflow.add_node(f"tool_{tool_name}", self._create_tool_node(tool_name))

        # Set entry point
        workflow.set_entry_point("agent")

        # Build conditional edges dynamically based on available tools
        conditional_edges = {}

        # Add edges for all initialized tools
        for tool_name in self.tools.keys():
            conditional_edges[f"tool_{tool_name}"] = f"tool_{tool_name}"

        # Add special edges
        conditional_edges["continue"] = "agent"  # Continue to next agent step
        conditional_edges["end"] = END  # End the workflow

        # Add conditional edges from agent to tools
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            conditional_edges
        )

        # Add edges from tools back to agent
        for tool_name in self.tools.keys():
            workflow.add_edge(f"tool_{tool_name}", "agent")

        # Compile without any checkpointer or config
        return workflow.compile()

    async def _agent_step(self, state: RunState) -> Dict[str, Any]:
        """Main agent step - decides what tool to use next"""
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

            # Get LLM response
            response = await self.llm.ainvoke(messages)

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

            # Store tool calls for conditional routing
            state["tool_calls"] = tool_calls

            # Update counters
            state.setdefault("counters", {})
            state["counters"]["steps"] = state["counters"].get("steps", 0) + 1

            # Log state persistence info for debugging
            logger.debug(f"Agent step completed - ended: {state.get('ended')}, steps: {state['counters']['steps']}")

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

    def _create_tool_node(self, tool_name: str):
        """Create a node function for a specific tool"""
        async def tool_node(state: RunState) -> Dict[str, Any]:
            tool = self.tools[tool_name]

            # Get tool call arguments
            tool_calls = state.get("tool_calls", [])
            if not tool_calls:
                return state

            # Execute tool calls
            for call in tool_calls:
                if call.get("name") == tool_name:
                    try:
                        # Execute tool
                        result = await tool.execute(**call.get("args", {}))

                        # Store result in state
                        state = self._reduce_tool_result(state, tool_name, result)

                        # Update stats
                        self.stats["tools_executed"] += 1

                    except Exception as e:
                        logger.error(f"Tool {tool_name} execution failed: {e}")
                        error_result = ToolResult(success=False, error=str(e))

                        # Add detailed error to state
                        error_info = {
                            "stage": f"tool_{tool_name}",
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "timestamp": datetime.now().isoformat(),
                            "tool_name": tool_name,
                            "tool_args": call.get("args", {}),
                        }
                        state.setdefault("errors", []).append(error_info)

                        # Update error counter
                        state.setdefault("counters", {})
                        state["counters"]["tool_errors"] = state["counters"].get("tool_errors", 0) + 1

                        state = self._reduce_tool_result(state, tool_name, error_result)
                        self.stats["errors_encountered"] += 1

            return state

        return tool_node

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

        elif tool_name == "extract_people" and result.success:
            state["candidates"] = result.data.get("candidates", [])

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

        elif tool_name == "find_commit_emails" and result.success:
            # Add email to the corresponding lead
            login = result.data.get("login")
            emails = result.data.get("emails", [])
            if login and emails:
                for lead in state.get("leads", []):
                    if lead.get("login") == login:
                        lead["email"] = emails[0]  # Take first email
                        break

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

        elif tool_name == "mx_check" and result.success:
            # Mark emails as valid/invalid
            valid_emails = set(result.data.get("valid_emails", []))
            for lead in state.get("leads", []):
                email = lead.get("email")
                if email:
                    lead["email_valid"] = email in valid_emails

        elif tool_name == "score_icp" and result.success:
            # This would be handled per-lead in the enrichment phase
            pass

        elif tool_name == "render_copy" and result.success:
            # Add rendered email to to_send
            state.setdefault("to_send", [])
            state["to_send"].append(result.data)

        elif tool_name == "send_instantly" and result.success:
            # Update reports
            state.setdefault("reports", {})
            state["reports"]["instantly"] = result.data

        elif tool_name == "sync_attio" and result.success:
            # Update reports
            state.setdefault("reports", {})
            state["reports"]["attio"] = result.data

        elif tool_name == "sync_linear" and result.success:
            # Update reports
            state.setdefault("reports", {})
            state["reports"]["linear"] = result.data

        elif tool_name == "export_csv" and result.success:
            # Add to checkpoints
            state.setdefault("checkpoints", [])
            state["checkpoints"].append({
                "type": "csv_export",
                "path": result.data.get("path"),
                "count": result.data.get("count"),
                "timestamp": datetime.now().isoformat(),
            })

        elif tool_name == "done" and result.success:
            state["ended"] = True
            state["completed_at"] = result.data.get("completed_at")

        return state

    def _build_system_prompt(self, state: RunState) -> str:
        """Build the system prompt for the agent"""
        caps = self.config

        prompt = f"""You are a CMO operator managing an outbound campaign. Use tools to complete tasks efficiently.

CURRENT TASK: {state['goal']}

WORKFLOW STEPS:
1. Search for relevant repositories
2. Extract contributors from repositories  
3. Enrich user profiles in batches
4. Find email addresses in batches
5. Validate emails with MX check
6. Score leads for quality
7. Render personalized emails
8. Send emails (DRY RUN - no actual sending)
9. Sync to CRM systems
10. Export results to CSV
11. Call done() to finish

IMPORTANT: Use BATCHED tools when available:
- enrich_github_users (for multiple users)
- find_commit_emails_batch (for multiple users)

CURRENT PROGRESS:
- Steps completed: {state.get('counters', {}).get('steps', 0)}
- Repositories found: {len(state.get('repos', []))}
- Candidates extracted: {len(state.get('candidates', []))}
- Profiles enriched: {len(state.get('leads', []))}
- Emails ready to send: {len(state.get('to_send', []))}

WHEN TO STOP: Call done("Campaign completed successfully") when you have found leads and prepared emails to send.

Available tools: {', '.join(self.tools.keys())}
"""

        return prompt

    def _should_continue(self, state: RunState) -> str:
        """Determine next step based on current state"""
        # Check for explicit termination conditions first
        if state.get("ended"):
            logger.info(f"Workflow terminated: ended flag is set (steps: {state.get('counters', {}).get('steps', 0)})")
            return "end"

        # Check step count limit
        counters = state.get("counters", {})
        current_steps = counters.get("steps", 0)
        max_steps = self.config.get("max_steps", 40)
        if current_steps >= max_steps:
            logger.warning(f"Workflow terminated: reached max_steps limit ({current_steps}/{max_steps})")
            # Auto-call done tool if we hit the limit
            state["ended"] = True
            return "end"

        tool_calls = state.get("tool_calls", [])

        if not tool_calls:
            return "continue"

        # Check for done tool
        for call in tool_calls:
            if call.get("name") == "done":
                logger.info("Workflow terminated: done tool called")
                return "end"

        # Route to appropriate tool (only if tool exists)
        for call in tool_calls:
            tool_name = call.get("name")
            if tool_name and tool_name in self.tools:
                return f"tool_{tool_name}"

        # If no valid tool found, continue to next agent step
        logger.warning(f"No valid tool found in tool_calls: {[call.get('name') for call in tool_calls]}")
        return "continue"

    async def run_job(self, goal: str, created_by: str = "user", progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Run a complete job from start to finish with progress updates"""
        job_meta = None
        try:
            # Create job metadata
            job_meta = JobMetadata(goal, created_by)

            # Initialize state
            initial_state = RunState(
                **job_meta.to_dict(),
                icp=self.config.get("default_icp", {}),
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

            # Use invoke method instead of astream to avoid checkpointer issues
            try:
                final_state = await self.graph.ainvoke(initial_state)
                logger.info("Job completed successfully via invoke method")

                # Extract final progress information
                progress_info = self._extract_progress_info(final_state)
                if progress_callback:
                    await progress_callback(progress_info)

                # Save final checkpoint
                await self._save_checkpoint(job_meta.job_id, final_state, "completed")

            except Exception as e:
                logger.error(f"Job execution failed via invoke: {e}")
                # Try to save error checkpoint if we have a state
                if 'final_state' in locals() and final_state:
                    await self._save_checkpoint(job_meta.job_id, final_state, "error")
                raise

            # Update stats
            self.stats["jobs_processed"] += 1

            # Save final checkpoint
            if final_state:
                await self._save_checkpoint(job_meta.job_id, final_state, "completed")

            # Collect artifacts
            artifacts = await self._collect_artifacts(job_meta.job_id)

            return {
                "success": True,
                "job_id": job_meta.job_id,
                "final_state": final_state,
                "artifacts": artifacts,
            }

        except Exception as e:
            logger.error(f"Job execution failed: {e}")
            job_id = job_meta.job_id if job_meta else "unknown"

            # Save error checkpoint
            if final_state:
                await self._save_checkpoint(job_id, final_state, "error")

                # Add critical error to final state
                error_info = {
                    "stage": "job_execution",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "timestamp": datetime.now().isoformat(),
                    "job_id": job_id,
                    "critical": True,
                }
                final_state.setdefault("errors", []).append(error_info)

            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "job_id": job_id,
                "final_state": final_state,
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

    async def _collect_artifacts(self, job_id: str) -> List[str]:
        """Collect artifacts generated during job execution"""
        # This would scan the artifacts directory for job-specific files
        # For now, return empty list
        return []

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

            # Prepare checkpoint data
            checkpoint_data = {
                "job_id": job_id,
                "checkpoint_type": checkpoint_type,
                "timestamp": datetime.now().isoformat(),
                "state": state,
                "counters": state.get("counters", {}),
                "progress": state.get("progress", {}),
            }

            # Save to file
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2, default=str)

            # Add to state's checkpoints list
            state.setdefault("checkpoints", []).append({
                "type": checkpoint_type,
                "path": str(checkpoint_file),
                "timestamp": datetime.now().isoformat(),
                "counters": state.get("counters", {}),
            })

            logger.info(f"Checkpoint saved: {checkpoint_file}")
            return str(checkpoint_file)

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return None

    async def _should_checkpoint(self, state: RunState) -> bool:
        """Determine if we should create a checkpoint"""
        counters = state.get("counters", {})
        current_step = counters.get("steps", 0)

        # Checkpoint every 5 steps or when significant milestones are reached
        if current_step % 5 == 0:
            return True

        # Checkpoint when we have significant data
        repos_count = len(state.get("repos", []))
        leads_count = len(state.get("leads", []))

        if repos_count > 0 and repos_count % 10 == 0:
            return True

        if leads_count > 0 and leads_count % 20 == 0:
            return True

        return False
