# Interactive ICP Wizard

A conversational AI-powered wizard for discovering and refining Ideal Customer Profiles (ICPs) using LangGraph for intelligent conversation flow.

## Features

- 🤖 **Conversational Discovery**: Interactive chat-based ICP exploration
- 🎯 **Intelligent Matching**: AI-powered ICP recommendations based on your needs
- 🔄 **Refinement Loop**: Iterative ICP refinement through natural conversation
- 💾 **Configuration Generation**: Automatic ICP configuration for the intelligence pipeline
- 📊 **Integration Ready**: Seamless integration with the Lead Intelligence System

## Quick Start

### Prerequisites

1. **OpenAI API Key**: Required for the conversational AI

   ```bash
   export OPENAI_API_KEY=your_openai_api_key_here
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r icp_wizard/requirements.txt
   ```

### Basic Usage

#### Using Make Commands (Recommended)

```bash
# Start the interactive ICP wizard
make wizard

# List all available ICPs
make icp-list

# Get details about a specific ICP
make icp-details ICP=icp01_pypi_maintainers
```

#### Using Python Directly

```bash
# Start the wizard
python icp_wizard_cli.py

# List available ICPs
python icp_wizard_cli.py --list

# Show ICP details
python icp_wizard_cli.py --details icp01_pypi_maintainers

# Custom output file
python icp_wizard_cli.py --output my_icp_config.json
```

#### Integration with Intelligence System

```bash
# Run wizard and automatically integrate
python run_intelligence.py wizard

# Use ICP config from wizard
python run_intelligence.py --icp-config lead_intelligence/data/icp_wizard_config.json
```

## How It Works

The ICP Wizard uses **LangGraph** to create an intelligent conversation flow:

1. **Greeting & Discovery**: Initial conversation to understand your needs
2. **ICP Analysis**: AI analyzes your requirements and suggests relevant ICPs
3. **Refinement**: Interactive refinement based on your feedback
4. **Confirmation**: Final ICP selection and configuration generation
5. **Integration**: Automatic integration with the intelligence pipeline

### Conversation Flow

```
User Input → LangGraph State → AI Analysis → ICP Suggestions → User Feedback → Refinement → Final Config
```

## Available ICPs

The wizard currently supports these ICP categories:

- **PyPI Maintainers**: Python library maintainers and core developers
- **ML/Data Science**: Machine learning and data science ecosystem maintainers
- **SaaS Companies**: Seed/Series A Python SaaS companies
- **API/SDK Tools**: API and SDK development teams
- **Academic Labs**: University research labs maintaining Python packages
- **Django/Flask**: Web framework product teams
- **Fintech**: Regulated fintech startups with Python backends
- **Agencies**: Consulting agencies with client repositories
- **Testing Tools**: PyTest and CI plugin authors
- **Flaky Signals**: Repositories with explicit flaky test signals

## Configuration Output

The wizard generates a comprehensive ICP configuration including:

- **ICP Metadata**: ID, name, description
- **Technographics**: Programming languages, frameworks, tools
- **Firmographics**: Company size, geography, industry
- **Triggers**: Specific signals that identify this ICP
- **GitHub Queries**: Optimized search queries for the ICP
- **Disqualifiers**: Signals that rule out this ICP

### Example Output

```json
{
  "icp_id": "icp01_pypi_maintainers",
  "icp_name": "PyPI Maintainers – Fast‑Moving Python Libraries",
  "technographics": {
    "language": ["Python"],
    "frameworks": ["pytest", "tox"]
  },
  "github_queries": [
    "language:Python stars:50..2000 pushed:>={today_minus_days:60} in:readme pytest -archived:true -is:fork"
  ],
  "generated_at": "2024-01-15T10:30:00Z",
  "source": "interactive_wizard"
}
```

## Advanced Usage

### Custom API Keys

```bash
# Use custom OpenAI API key
python icp_wizard_cli.py --api-key sk-your-custom-key-here

# Or set environment variable
export OPENAI_API_KEY=sk-your-key-here
python icp_wizard_cli.py
```

### Integration with Intelligence Pipeline

```bash
# 1. Run the wizard
make wizard

# 2. Use the generated config
python run_intelligence.py --icp-config lead_intelligence/data/icp_wizard_config.json --max-repos 100

# 3. Or use the simple interface
python run_intelligence.py wizard  # This runs wizard and pipeline together
```

### Batch Processing

```bash
# Generate multiple ICP configs
python icp_wizard_cli.py --output icp1_config.json
python icp_wizard_cli.py --output icp2_config.json

# Compare configurations
python run_intelligence.py --icp-config icp1_config.json --dry-run
python run_intelligence.py --icp-config icp2_config.json --dry-run
```

## Troubleshooting

### Common Issues

**"OpenAI API key required"**

```bash
# Set the environment variable
export OPENAI_API_KEY=your_actual_openai_key

# Or pass it directly
python icp_wizard_cli.py --api-key your_actual_openai_key
```

**"Could not import ICP wizard"**

```bash
# Install dependencies
pip install -r icp_wizard/requirements.txt

# Make sure you're in the project root directory
cd /path/to/leads
python icp_wizard_cli.py
```

**"No ICP options available"**

- Check that `configs/icp/options.yaml` exists and contains ICP definitions
- Ensure the YAML file is properly formatted

### Debug Mode

```bash
# Enable verbose logging
python icp_wizard_cli.py --verbose

# Or with environment variable
export LOG_LEVEL=DEBUG
python icp_wizard_cli.py
```

## Architecture

### Core Components

- **`ICPWizard`**: Main wizard class with LangGraph integration
- **`ICPWizardState`**: TypedDict for conversation state management
- **`icp_wizard_cli.py`**: Command-line interface
- **`run_intelligence.py`**: Integration with intelligence system

### LangGraph Flow

The conversation follows this state graph:

```
greeting → understand_needs → refine_icp → confirm_icp → finalize_icp → END
    ↑           ↓                    ↓           ↓
    └───── fallback/understanding ───┴───── user_feedback ───┘
```

### Dependencies

- **langchain-openai**: OpenAI integration for conversational AI
- **langgraph**: Graph-based conversation flow management
- **python-dotenv**: Environment variable management
- **pyyaml**: Configuration file parsing

## Contributing

### Adding New ICPs

1. Add ICP definition to `configs/icp/options.yaml`
2. Test with: `python icp_wizard_cli.py --details your_new_icp_id`
3. Update conversation prompts if needed

### Improving Conversation Flow

1. Modify state transitions in `ICPWizard._create_conversation_graph()`
2. Update prompt templates for better AI responses
3. Test conversation flows thoroughly

## License

This module is part of the Lead Intelligence System and follows the same licensing terms.
