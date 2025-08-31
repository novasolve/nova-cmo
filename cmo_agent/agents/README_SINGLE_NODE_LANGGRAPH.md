## Single‑Node LangGraph Agent

A minimal, production‑grade LangGraph built as a single node that repeatedly plans and executes tools until done. This repo’s active implementation powers the CMO Agent workflow.

### Where it lives

- Core graph: `cmo_agent/agents/cmo_agent.py` (method `_build_graph` and `_agent_step`)
- Typed state: `cmo_agent/core/state.py` (`RunState`)
- Tools: `cmo_agent/tools/*`

### Graph at a glance

```python
workflow = StateGraph(RunState)
workflow.add_node("agent", self._agent_step)
workflow.set_entry_point("agent")

def should_end(state: RunState) -> str:
    if state.get("ended") or state.get("counters", {}).get("steps", 0) >= self.config.get("max_steps", 40):
        return END
    return "agent"

workflow.add_conditional_edges("agent", should_end)
graph = workflow.compile()
```

The single node (`agent`) does both: reasoning and tool execution. Each turn the LLM chooses one tool (or `done`), we run it, reduce results back into `RunState`, and loop until caps or completion.

### Quick start

```bash
cd cmo_agent
cp env.example .env    # fill in keys
pip install -r requirements.txt

# smoke test the execution engine
python scripts/test_execution_engine.py

# run a sample job with workers
python scripts/run_execution.py --job "Find 200 Python maintainers" --start-workers
```

Required env (minimum):

- `OPENAI_API_KEY`
  Optional (enables specific tools):
- `GITHUB_TOKEN`, `ATTIO_API_KEY`, `LINEAR_API_KEY`, Instantly creds, etc.

### How `_agent_step` works (high‑level)

1. Build the system prompt and messages from `RunState` (goal, history, caps).
2. Call LLM bound with tool schemas (`llm.bind_tools(...)`).
3. Execute selected tool with validated args; capture a structured `ToolResult`.
4. Reduce the result into `RunState` (counters, artifacts, logs, errors).
5. If tool is `done`, set `ended=True`.

### Extending the graph

- Add a tool in `cmo_agent/tools/` (returns a typed `ToolResult`).
- Register it in `CMOAgent._initialize_tools()` and ensure the schema is included in `llm.bind_tools`.
- Update reducer logic if the tool produces new fields in `RunState`.
- Adjust caps in `cmo_agent/config/*.yaml` (e.g., `max_steps`, per‑tool limits).

### Tuning caps & safety rails

- Step budget: `config.max_steps` (defaults to 40).
- Per‑tool caps and rate limits live in config; tools should be idempotent and externally keyed.
- The graph is checkpoint‑friendly: `RunState` is JSON‑serializable and persisted between steps.

### Files to read next

- `cmo_agent/README.md` — full system overview and architecture
- `cmo_agent/core/state.py` — `RunState` schema and reducer conventions
- `cmo_agent/agents/cmo_agent.py` — `_build_graph` and `_agent_step`
