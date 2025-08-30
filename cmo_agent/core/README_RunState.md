# RunState: Typed State Management for CMO Agent

## Overview

The `RunState` is the central state management system for the CMO Agent's LangGraph workflow. It provides a structured, typed approach to managing the complete lifecycle of outbound sales campaigns, from GitHub discovery through CRM synchronization.

## Core Architecture

```python
class RunState(TypedDict, total=False):
    """Typed state for CMO Agent LangGraph workflow"""

    # Job metadata
    job_id: str
    goal: str
    created_at: str
    created_by: str

    # ICP (Ideal Customer Profile) criteria
    icp: Dict[str, Any]

    # Discovery phase
    repos: List[Dict[str, Any]]
    candidates: List[Dict[str, Any]]

    # Enrichment phase
    leads: List[Dict[str, Any]]

    # Personalization phase
    to_send: List[Dict[str, Any]]

    # Execution reports
    reports: Dict[str, Any]

    # Error handling
    errors: List[Dict[str, Any]]

    # Monitoring & metrics
    counters: Dict[str, int]
    checkpoints: List[str]

    # Configuration
    config: Dict[str, Any]

    # Control flow
    ended: bool
    current_stage: str
    history: List[Dict[str, Any]]
```

## State Fields Explained

### Job Metadata
- **`job_id`**: Unique identifier (format: `cmo-YYYYMMDD-HHMMSS`)
- **`goal`**: Original campaign objective/description
- **`created_at`**: ISO timestamp when job was created
- **`created_by`**: User or system that initiated the job

### ICP Criteria
- **`icp`**: Ideal Customer Profile configuration
  ```python
  {
      "keywords": ["testing", "ci", "devtools"],
      "languages": ["python", "javascript"],
      "stars_range": "100..2000",
      "activity_days": 90,
      "topics": ["ci", "testing", "pytest"]
  }
  ```

### Discovery Phase
- **`repos`**: GitHub repositories matching ICP criteria
  ```python
  [
      {
          "id": 12345,
          "name": "pytest-dev/pytest",
          "full_name": "pytest-dev/pytest",
          "description": "The pytest framework",
          "stars": 8500,
          "language": "python",
          "topics": ["testing", "python", "pytest"],
          "updated_at": "2024-01-15T10:30:00Z"
      }
  ]
  ```

- **`candidates`**: Potential leads identified from repositories
  ```python
  [
      {
          "login": "john-doe",
          "from_repo": "pytest-dev/pytest",
          "signal": "top_contributor",
          "contributions": 250,
          "role": "maintainer"
      }
  ]
  ```

### Enrichment Phase
- **`leads`**: Enriched prospect profiles with detailed information
  ```python
  [
      {
          "login": "john-doe",
          "name": "John Doe",
          "email": "john@example.com",
          "company": "Tech Corp",
          "location": "San Francisco, CA",
          "bio": "Python developer and open source maintainer",
          "followers": 1200,
          "following": 300,
          "public_repos": 45,
          "hireable": true,
          "icp_score": 85,
          "last_activity": "2024-01-10T08:15:00Z"
      }
  ]
  ```

### Personalization Phase
- **`to_send`**: Personalized email campaigns ready for dispatch
  ```python
  [
      {
          "email": "john@example.com",
          "subject": "Streamline Your Python Testing with Our DevTools",
          "body": "Hi John, I noticed your work on pytest-dev/pytest...",
          "meta": {
              "prospect_id": "john-doe",
              "icp_score": 85,
              "sequence_id": "seq-123",
              "priority": "high"
          }
      }
  ]
  ```

### Execution Reports
- **`reports`**: Campaign execution results and analytics
  ```python
  {
      "instantly": {
          "sent": 150,
          "delivered": 145,
          "opened": 67,
          "clicked": 23,
          "bounced": 3
      },
      "attio": {
          "created": 142,
          "updated": 8,
          "errors": 2
      },
      "linear": {
          "issues_created": 15,
          "follow_ups": 8
      },
      "export": {
          "csv_files": ["leads_20240115.csv"],
          "total_records": 147
      }
  }
  ```

### Error Handling
- **`errors`**: Structured error tracking with context
  ```python
  [
      {
          "stage": "enrichment",
          "payload": {"login": "john-doe"},
          "error": "GitHub API rate limit exceeded",
          "timestamp": "2024-01-15T14:30:00Z",
          "retry_count": 2
      }
  ]
  ```

### Monitoring & Metrics
- **`counters`**: Performance and usage metrics
  ```python
  {
      "steps": 23,
      "api_calls": 1450,
      "github_api_calls": 234,
      "instantly_api_calls": 156,
      "attio_api_calls": 89,
      "tokens_used": 125000,
      "emails_sent": 150,
      "leads_enriched": 147
  }
  ```

- **`checkpoints`**: Artifact paths for resumability
  ```python
  [
      "./checkpoints/job_cmo_20240115_143000_step_10.json",
      "./exports/leads_batch_1.csv",
      "./exports/campaign_report.json"
  ]
  ```

### Configuration
- **`config`**: Runtime configuration and limits
  ```python
  {
      "max_steps": 40,
      "max_repos": 600,
      "max_people": 3000,
      "per_inbox_daily": 50,
      "activity_days": 90,
      "rate_limits": {
          "github_per_hour": 5000,
          "instantly_per_inbox_daily": 50,
          "attio_per_minute": 60
      },
      "timeouts": {
          "github_api": 15,
          "instantly_api": 30,
          "attio_api": 20
      }
  }
  ```

### Control Flow
- **`ended`**: Boolean flag indicating job completion
- **`current_stage`**: Current execution stage (discovery, enrichment, etc.)
- **`history`**: Conversation and decision history
  ```python
  [
      {
          "timestamp": "2024-01-15T14:15:00Z",
          "stage": "discovery",
          "action": "search_github_repos",
          "result": "Found 234 repositories",
          "metrics": {"api_calls": 12, "tokens": 1500}
      }
  ]
  ```

## Usage Examples

### Initializing a New Campaign

```python
from core.state import RunState, JobMetadata
from datetime import datetime

# Create job metadata
metadata = JobMetadata(
    goal="Find Python testing framework maintainers",
    created_by="campaign_manager"
)

# Initialize state
initial_state: RunState = {
    "job_id": metadata.job_id,
    "goal": metadata.goal,
    "created_at": metadata.created_at,
    "created_by": metadata.created_by,
    "icp": {
        "languages": ["python"],
        "topics": ["testing", "ci"],
        "stars_range": "500..5000"
    },
    "repos": [],
    "candidates": [],
    "leads": [],
    "to_send": [],
    "reports": {},
    "errors": [],
    "counters": {"steps": 0, "api_calls": 0},
    "checkpoints": [],
    "config": DEFAULT_CONFIG,
    "ended": False,
    "current_stage": "initialization",
    "history": []
}
```

### Updating State During Execution

```python
def update_discovery_results(state: RunState, new_repos: List[Dict]) -> RunState:
    """Update state with new repository discoveries"""
    return {
        **state,
        "repos": state.get("repos", []) + new_repos,
        "counters": {
            **state.get("counters", {}),
            "api_calls": state.get("counters", {}).get("api_calls", 0) + len(new_repos)
        },
        "current_stage": "discovery",
        "history": state.get("history", []) + [{
            "timestamp": datetime.now().isoformat(),
            "stage": "discovery",
            "action": "search_github_repos",
            "result": f"Found {len(new_repos)} repositories"
        }]
    }
```

### State Persistence and Recovery

```python
import json
from pathlib import Path

def save_state_checkpoint(state: RunState, checkpoint_dir: str = "./checkpoints"):
    """Save state to disk for resumability"""
    checkpoint_path = Path(checkpoint_dir) / f"{state['job_id']}_checkpoint.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    with open(checkpoint_path, 'w') as f:
        json.dump(state, f, indent=2, default=str)

    # Update checkpoints list
    state["checkpoints"] = state.get("checkpoints", []) + [str(checkpoint_path)]

def load_state_checkpoint(job_id: str, checkpoint_dir: str = "./checkpoints") -> RunState:
    """Load state from disk"""
    checkpoint_path = Path(checkpoint_dir) / f"{job_id}_checkpoint.json"

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    with open(checkpoint_path, 'r') as f:
        return json.load(f)
```

## Integration with LangGraph

The RunState integrates seamlessly with LangGraph workflows:

```python
from langgraph.graph import StateGraph
from core.state import RunState

# Define the workflow graph
workflow = StateGraph(RunState)

# Add nodes (stages)
workflow.add_node("discover", discovery_stage)
workflow.add_node("enrich", enrichment_stage)
workflow.add_node("personalize", personalization_stage)
workflow.add_node("execute", execution_stage)

# Define edges with conditional logic
workflow.add_edge("discover", "enrich")
workflow.add_conditional_edges(
    "enrich",
    lambda state: "completed" if state.get("ended") else "personalize",
    {"completed": END, "personalize": "personalize"}
)

# Set entry point
workflow.set_entry_point("discover")

# Compile the graph
app = workflow.compile()
```

## Error Handling and Recovery

The RunState includes comprehensive error tracking:

```python
def handle_tool_error(state: RunState, error: Exception, tool_name: str, payload: Dict) -> RunState:
    """Handle and record tool execution errors"""
    error_entry = {
        "stage": state.get("current_stage", "unknown"),
        "tool": tool_name,
        "payload": payload,
        "error": str(error),
        "timestamp": datetime.now().isoformat(),
        "retry_count": 0
    }

    return {
        **state,
        "errors": state.get("errors", []) + [error_entry],
        "counters": {
            **state.get("counters", {}),
            "errors": state.get("counters", {}).get("errors", 0) + 1
        }
    }
```

## Monitoring and Observability

Track campaign progress and performance:

```python
def get_progress_summary(state: RunState) -> Dict[str, Any]:
    """Generate progress summary for monitoring"""
    counters = state.get("counters", {})

    return {
        "job_id": state.get("job_id"),
        "stage": state.get("current_stage"),
        "progress": {
            "repos_found": len(state.get("repos", [])),
            "candidates_identified": len(state.get("candidates", [])),
            "leads_enriched": len(state.get("leads", [])),
            "emails_prepared": len(state.get("to_send", []))
        },
        "metrics": {
            "api_calls": counters.get("api_calls", 0),
            "steps_completed": counters.get("steps", 0),
            "errors_encountered": len(state.get("errors", [])),
            "tokens_used": counters.get("tokens_used", 0)
        },
        "status": "completed" if state.get("ended") else "running"
    }
```

## Configuration Management

Dynamic configuration updates during execution:

```python
def update_runtime_config(state: RunState, new_config: Dict[str, Any]) -> RunState:
    """Update runtime configuration"""
    return {
        **state,
        "config": {**state.get("config", {}), **new_config},
        "history": state.get("history", []) + [{
            "timestamp": datetime.now().isoformat(),
            "stage": state.get("current_stage", "configuration"),
            "action": "update_config",
            "result": f"Updated {len(new_config)} config parameters"
        }]
    }
```

## Best Practices

### State Immutability
Always create new state objects rather than mutating existing ones:

```python
# ✅ Good: Immutable updates
new_state = {**state, "current_stage": "enrichment"}

# ❌ Bad: Direct mutation
state["current_stage"] = "enrichment"  # Modifies original
```

### Error Resilience
Include error context in all state updates:

```python
# ✅ Good: Comprehensive error tracking
state_with_error = {
    **state,
    "errors": state.get("errors", []) + [{
        "stage": stage,
        "tool": tool_name,
        "error": str(error),
        "payload": payload,
        "timestamp": datetime.now().isoformat()
    }]
}
```

### Performance Considerations
- Use selective field updates for large state objects
- Implement pagination for large lists (repos, leads, etc.)
- Regular checkpointing for resumability

### Type Safety
Leverage the TypedDict structure for IDE support and runtime validation:

```python
# Type checking helps catch errors at development time
def process_leads(state: RunState) -> RunState:
    leads = state["leads"]  # Type checker knows this is List[Dict[str, Any]]
    # ... processing logic
```

## Testing

```python
import pytest
from core.state import RunState, JobMetadata

def test_state_initialization():
    """Test proper state initialization"""
    metadata = JobMetadata("Test campaign", "test_user")

    state: RunState = {
        "job_id": metadata.job_id,
        "goal": metadata.goal,
        "created_at": metadata.created_at,
        "created_by": metadata.created_by,
        "icp": {"languages": ["python"]},
        "repos": [],
        "candidates": [],
        "leads": [],
        "to_send": [],
        "reports": {},
        "errors": [],
        "counters": {"steps": 0},
        "checkpoints": [],
        "config": {},
        "ended": False,
        "current_stage": "initialization",
        "history": []
    }

    assert state["job_id"].startswith("cmo-")
    assert state["ended"] is False
    assert len(state["repos"]) == 0

def test_state_immutability():
    """Test that state updates don't mutate original"""
    original_state: RunState = {
        "job_id": "test-123",
        "counters": {"steps": 5}
    }

    updated_state = {**original_state, "counters": {"steps": 6}}

    assert original_state["counters"]["steps"] == 5
    assert updated_state["counters"]["steps"] == 6
```

## Migration and Versioning

When adding new fields to RunState:

1. Make new fields optional with `total=False`
2. Provide default values in initialization
3. Update existing checkpoints with migration logic
4. Document field additions in this README

```python
# Adding a new optional field
class RunState(TypedDict, total=False):
    # ... existing fields ...
    new_feature_enabled: bool  # New field

# Migration helper
def migrate_state_to_v2(state: RunState) -> RunState:
    """Migrate state to version 2 with new fields"""
    return {
        **state,
        "new_feature_enabled": state.get("new_feature_enabled", True)
    }
```

This RunState system provides a robust, type-safe foundation for managing complex outbound sales campaigns with full observability, error recovery, and resumability capabilities.
