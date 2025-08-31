# 🚀 CMO Agent - MAIN IMPLEMENTATION

**A Single-Agent, Tool-Calling LangGraph for Outbound & CRM Operations**

> **🎯 This is the ACTIVE, WORKING implementation of the CMO Agent system.**
>
> For the complete specification and architecture overview, see the root [`README.md`](../README.md).

The CMO Agent is an intelligent automation system that handles the complete outbound sales pipeline: from GitHub discovery and lead enrichment, through email personalization and sending, to CRM synchronization and issue tracking.

## 📚 Documentation

- **[Complete Specification](../README.md)** - Full system architecture and design
- **[Execution Model](execution_model_README.md)** - Detailed implementation guide
- **[API Reference](execution_model_README.md#api-reference)** - Tool contracts and schemas
- **[Single‑Node LangGraph](agents/README_SINGLE_NODE_LANGGRAPH.md)** - Minimal graph, loop logic, and extension points

## 🏗️ Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Chat UI   │───▶│ LangGraph   │───▶│   Tools     │
│             │    │  Agent      │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
                        │
                        ▼
               ┌─────────────────┐
               │   RunState      │
               │  (Persistent)   │
               └─────────────────┘
```

## 🚀 Quick Start

### 1. Installation

```bash
cd cmo_agent
pip install -r requirements.txt
```

### 2. Configuration

Copy and modify the configuration:

```bash
cp config/default.yaml config/my_campaign.yaml
# Edit my_campaign.yaml with your settings
```

### 3. Set Environment Variables

```bash
export GITHUB_TOKEN=your_github_token
export INSTANTLY_API_KEY=your_instantly_key
export ATTIO_API_KEY=your_attio_key
export LINEAR_API_KEY=your_linear_key
export OPENAI_API_KEY=your_openai_key
```

### 4. Run a Campaign

```bash
# Simple campaign
python scripts/run_agent.py "Find 2k Py maintainers active 90d, queue Instantly seq=123"

# With custom config
python scripts/run_agent.py --config config/my_campaign.yaml "Find ML engineers, send personalized emails"

# Dry run (no actual sending)
python scripts/run_agent.py --dry-run "Same as above but don't send emails"
```

## 📋 Pipeline Overview

The CMO Agent executes a complete outbound campaign pipeline:

1. **Discovery**: Search GitHub for relevant repositories
2. **Extraction**: Identify top contributors and maintainers
3. **Enrichment**: Get detailed profiles and activity data
4. **Validation**: Check email deliverability with MX records
5. **Scoring**: Apply ICP filters and qualification criteria
6. **Personalization**: Generate customized email content
7. **Sending**: Dispatch via Instantly API with proper pacing
8. **Sync**: Update CRM with campaign data and signals
9. **Tracking**: Create Linear issues for follow-up and errors

## 🔧 Tool Belt

### GitHub Tools

- `search_github_repos`: Find repositories matching ICP criteria
- `extract_people`: Identify top contributors from repos
- `enrich_github_user`: Get detailed user profiles
- `find_commit_emails`: Extract email addresses from commits

### Hygiene Tools

- `mx_check`: Validate email domains via MX records
- `score_icp`: Apply deterministic scoring against ICP criteria

### Personalization Tools

- `render_copy`: Generate personalized email content
- `send_instantly`: Dispatch emails via Instantly API

### CRM Tools

- `sync_attio`: Update Attio with lead and campaign data
- `sync_linear`: Create issues for tracking and follow-up

### Utility Tools

- `export_csv`: Export data to CSV format
- `done`: Signal campaign completion

## ⚙️ Configuration

The agent is highly configurable via YAML files:

```yaml
# Job limits
max_steps: 40
max_repos: 600
max_people: 3000

# ICP criteria
default_icp:
  languages: ["python"]
  topics: ["ci", "testing", "pytest"]
  stars_range: "100..2000"

# Rate limits
rate_limits:
  github_per_hour: 5000
  instantly_per_second: 10
```

## 📊 RunState

The agent maintains a comprehensive state throughout execution:

```python
class RunState(TypedDict):
    # Job metadata
    job_id: str
    goal: str

    # Discovery data
    repos: List[Dict]
    candidates: List[Dict]

    # Enrichment data
    leads: List[Dict]

    # Campaign data
    to_send: List[Dict]
    reports: Dict

    # Monitoring
    counters: Dict
    errors: List[Dict]
```

## 🔄 Async Execution

The agent supports:

- **Background processing** for long-running campaigns
- **Resume/pause** capabilities
- **Streaming progress** updates
- **Error recovery** with automatic retries
- **Rate limiting** across all API calls

## 🛠️ Development

### Project Structure

```
cmo_agent/
├── core/           # Core state and utilities
├── tools/          # Tool implementations
├── agents/         # LangGraph orchestration
├── config/         # Configuration files
├── scripts/        # Execution scripts
└── data/           # Runtime data storage
```

### Adding New Tools

1. Create tool class inheriting from `BaseTool`
2. Implement `execute()` method with proper error handling
3. Add to `CMOAgent._initialize_tools()`
4. Update system prompt and routing logic

### Testing

```bash
# Unit tests for individual tools
python -m pytest tests/test_tools/

# Integration tests for full pipeline
python -m pytest tests/test_integration/

# End-to-end campaign tests
python -m pytest tests/test_e2e/
```

## 📈 Monitoring & Observability

- **Structured logging** for all operations
- **Metrics collection** for performance monitoring
- **Error tracking** with detailed context
- **Progress checkpoints** for resumability

## 🚀 Production Deployment

The agent is designed for production use with:

- **Docker containerization**
- **Environment-based configuration**
- **Database persistence** (SQLite/PostgreSQL)
- **Background job processing**
- **Health checks and monitoring**

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.
