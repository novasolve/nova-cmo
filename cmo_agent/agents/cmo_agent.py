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

try:
    from ..core.state import RunState, JobMetadata, DEFAULT_CONFIG
    from ..tools.github import SearchGitHubRepos, ExtractPeople, EnrichGitHubUser, FindCommitEmails
    from ..tools.hygiene import MXCheck, ICPScores
    from ..tools.personalization import RenderCopy, SendInstantly
    from ..tools.crm import SyncAttio, SyncLinear
    from ..tools.export import ExportCSV, Done
    from ..tools.base import ToolResult
except ImportError:
    # Handle relative import issues when running as standalone
    import sys
    from pathlib import Path
    parent_dir = str(Path(__file__).parent.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    from core.state import RunState, JobMetadata, DEFAULT_CONFIG
    from tools.github import SearchGitHubRepos, ExtractPeople, EnrichGitHubUser, FindCommitEmails
    from tools.hygiene import MXCheck, ICPScores
    from tools.personalization import RenderCopy, SendInstantly
    from tools.crm import SyncAttio, SyncLinear
    from tools.export import ExportCSV, Done
    from tools.base import ToolResult

logger = logging.getLogger(__name__)


class CMOAgent:
    """Main CMO Agent class that orchestrates the entire outbound campaign pipeline"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or DEFAULT_CONFIG.copy()
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",  # Could be upgraded to gpt-5 when available
            temperature=0.0,  # Deterministic for reliability
        )

        # Initialize all tools
        self.tools = self._initialize_tools()

        # Build LangGraph
        self.graph = self._build_graph()

        # Statistics
        self.stats = {
            "jobs_processed": 0,
            "tools_executed": 0,
            "errors_encountered": 0,
        }

    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize all tools with configuration"""
        tools = {}

        # GitHub tools
        if self.config.get("GITHUB_TOKEN"):
            tools["search_github_repos"] = SearchGitHubRepos(self.config["GITHUB_TOKEN"])
            tools["extract_people"] = ExtractPeople(self.config["GITHUB_TOKEN"])
            tools["enrich_github_user"] = EnrichGitHubUser(self.config["GITHUB_TOKEN"])
            tools["find_commit_emails"] = FindCommitEmails(self.config["GITHUB_TOKEN"])

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
        # Create workflow
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

        return workflow.compile()

    async def _agent_step(self, state: RunState) -> Dict[str, Any]:
        """Main agent step - decides what tool to use next"""
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
            tool_calls = []
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

            return state

        except Exception as e:
            logger.error(f"Agent step failed: {e}")
            # Add error to state
            state.setdefault("errors", []).append({
                "stage": "agent_step",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
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

        prompt = f"""You are a CMO operator. Always use TOOLS; do not fabricate.

Order: search→extract→enrich→emails→mx→score→render→send→sync→export→done.

Respect limits:
- MAX_STEPS: {caps.get('max_steps', 40)}
- MAX_REPOS: {caps.get('max_repos', 600)}
- MAX_PEOPLE: {caps.get('max_people', 3000)}
- MAX_API_CALLS: {caps.get('max_api_calls', 10000)}

Current state:
- Step: {state.get('counters', {}).get('steps', 0)}
- Repos found: {len(state.get('repos', []))}
- Candidates: {len(state.get('candidates', []))}
- Leads enriched: {len(state.get('leads', []))}
- Emails to send: {len(state.get('to_send', []))}

If MX‑passed volume < target, expand query incrementally (lower stars, widen topics) up to caps.

Stop by calling tool: done(summary).

Available tools: {', '.join(self.tools.keys())}
"""

        return prompt

    def _should_continue(self, state: RunState) -> str:
        """Determine next step based on current state"""
        tool_calls = state.get("tool_calls", [])

        if not tool_calls:
            return "continue"

        # Check for done tool
        for call in tool_calls:
            if call.get("name") == "done":
                return "end"

        # Route to appropriate tool (only if tool exists)
        for call in tool_calls:
            tool_name = call.get("name")
            if tool_name and tool_name in self.tools:
                return f"tool_{tool_name}"

        # If no valid tool found, continue to next agent step
        logger.warning(f"No valid tool found in tool_calls: {[call.get('name') for call in tool_calls]}")
        return "continue"

    async def run_job(self, goal: str, created_by: str = "user") -> Dict[str, Any]:
        """Run a complete job from start to finish"""
        try:
            # Create job metadata
            job_meta = JobMetadata(goal, created_by)

            # Initialize state
            initial_state = RunState(
                **job_meta.to_dict(),
                icp=self.config.get("default_icp", {}),
                config=self.config,
                current_stage="initialization",
                counters={"steps": 0, "api_calls": 0, "tokens": 0},
            )

            # Run the graph
            logger.info(f"Starting CMO Agent job: {job_meta.job_id}")
            final_state = await self.graph.ainvoke(initial_state)

            # Update stats
            self.stats["jobs_processed"] += 1

            return {
                "job_id": job_meta.job_id,
                "success": final_state.get("ended", False),
                "final_state": final_state,
                "stats": self.stats.copy(),
            }

        except Exception as e:
            logger.error(f"Job execution failed: {e}")
            self.stats["errors_encountered"] += 1
            return {
                "success": False,
                "error": str(e),
                "stats": self.stats.copy(),
            }
