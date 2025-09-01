# Beautiful Logging System for CMO Agent

The CMO Agent now features a comprehensive, beautiful logging system that provides rich console output, structured file logging, and stage-aware progress tracking. This system transforms the agent's observability from basic text logs to a colorful, informative, and easy-to-follow experience.

## 🌟 Key Features

### ✨ Beautiful Console Output

- **Colorful, emoji-rich formatting** with stage-specific icons
- **Real-time progress bars** for long-running operations
- **Stage transition announcements** (🚀 Discovery → ⚡ Extraction → 💎 Enrichment)
- **Clear error highlighting** with context and component information
- **Metrics snapshots** with key performance indicators

### 📁 Job-Specific Log Files

- **Separate log file per campaign** (`job-20250831-174356.log`)
- **JSON Lines format** for machine parsing and analysis
- **Structured data** with correlation IDs for easy tracing
- **Configurable log retention** and rotation

### 🔄 Stage-Aware Logging

- **Automatic stage detection** and transition logging
- **Progress tracking** within each pipeline stage
- **Stage completion summaries** with statistics
- **Error context** showing which stage and component failed

### 📊 Enhanced Metrics & Alerts

- **Periodic metrics snapshots** with business and technical metrics
- **Alert system** with configurable thresholds
- **Beautiful alert formatting** in console and logs
- **Prometheus export** support (optional)

## 🚀 Quick Start

### Basic Usage

```python
from cmo_agent.obs.beautiful_logging import setup_beautiful_logging
from cmo_agent.core.state import DEFAULT_CONFIG

# Setup beautiful logging for a job
job_id = "my-campaign-20250831-123456"
beautiful_logger = setup_beautiful_logging(DEFAULT_CONFIG, job_id)

# Log stage transitions
beautiful_logger.start_stage("discovery", "Searching for Python repositories")
beautiful_logger.log_progress("Found repositories", current=25, total=100)
beautiful_logger.end_stage("Discovery completed", found=46)

# Log errors with context
try:
    # Some operation
    pass
except Exception as e:
    beautiful_logger.log_error(e, "github_api")
```

### CMO Agent Integration

The beautiful logging is automatically integrated into the CMO Agent. When you run a campaign:

```bash
python scripts/run_agent.py --goal "Find Python maintainers"
```

You'll see output like:

```
[12:34:56] 🚀 Phase: Discovery – Searching for OSS Python repositories [job-abc123]
[12:35:02] ⚙️  PROGRESS [job-abc123] Found repositories [████████████░░░░░░░░] 25/46 (54.3%)
[12:35:15] 🏁 Completed: Discovery – Found 46 repositories (repos=46, scanned=150) [job-abc123]
[12:35:16] ⚡ Phase: Extraction – Extracting contributors from repositories [job-abc123]
```

## 📖 Configuration

### Enhanced Logging Configuration

The logging configuration has been expanded with new options:

```yaml
logging:
  level: "INFO"
  console: true # Enable console output
  file: true # Enable file logging
  json_file: true # Use JSON format for files
  job_specific_files: true # Create separate files per job
  beautiful_console: true # Use beautiful console formatter
  stage_logging: true # Enable stage transition logging
  progress_logging: true # Enable progress bars
  correlation_ids: true # Ensure all logs have correlation IDs
  metrics_snapshots: true # Log periodic metrics
  alert_logging: true # Log alerts as they trigger
  filename: "cmo_agent.jsonl" # General log file (when not job-specific)
```

### Stage Icons and Colors

The system uses intuitive icons for different stages and events:

- 🔍 **Discovery** - Finding repositories
- ⚡ **Extraction** - Getting contributors
- 💎 **Enrichment** - Profile and email enrichment
- 🎯 **Personalization** - Creating personalized content
- 📧 **Sending** - Email delivery
- ✅ **Validation** - Data validation
- 📤 **Export** - Results export
- 🔄 **Sync** - CRM synchronization
- 🏁 **Completed** - Campaign completion
- 💥 **Failed** - Errors and failures

### Log Levels and Colors

- 🔍 **DEBUG** - Detailed diagnostic information (dim gray)
- ✅ **INFO** - General information (green)
- ⚠️ **WARNING** - Warning messages (yellow)
- ❌ **ERROR** - Error conditions (red)
- 💥 **CRITICAL** - Critical failures (bright red, bold)

## 🧪 Testing and Demo

### Run the Demo

Experience the beautiful logging system:

```bash
python scripts/demo_beautiful_logging.py
```

This will simulate a complete campaign with all stages, showing:

- Stage transitions with progress bars
- Error handling and reporting
- Metrics collection and alerts
- Job-specific log file creation

### Run the Test Suite

Test all logging components:

```bash
python scripts/test_beautiful_logging.py
```

This tests:

- Console formatting
- Error logging
- Metrics logging
- Job-specific file creation

## 📁 Log File Structure

### Console Output Example

```
[12:34:56] 🚀 Phase: Discovery – Searching for OSS Python repositories [job-abc123]
[12:35:02] ⚙️  PROGRESS [job-abc123] Scanning repositories [████████░░] 25/46 (54.3%)
[12:35:15] 🏁 Completed: Discovery – Found 46 repositories (found=46) [job-abc123]
[12:35:16] ❌ ERROR (github_api) [job-abc123] [RateLimitError] GitHub API rate limit exceeded
[12:36:00] 📊 METRICS Metrics snapshot collected (jobs:1, api:150, errors:0.7%)
[12:36:01] ⚠️  ALERT High API usage: 95% of rate limit consumed
```

### JSON Log File Example

```json
{
  "timestamp": "2025-08-31T12:34:56.784Z",
  "level": "INFO",
  "event": "phase_start",
  "phase": "discovery",
  "job_id": "cmo-20250831-123456",
  "message": "Searching for OSS Python repositories"
}
{
  "timestamp": "2025-08-31T12:35:15.234Z",
  "level": "INFO",
  "event": "phase_end",
  "phase": "discovery",
  "job_id": "cmo-20250831-123456",
  "duration_seconds": 19.45,
  "found": 46,
  "message": "Discovery completed"
}
```

## 🔧 Advanced Usage

### Custom Stage Logging

```python
# Create a stage-aware logger
beautiful_logger = setup_beautiful_logging(config, job_id)

# Start a custom stage
beautiful_logger.start_stage("custom_processing", "Processing special data")

# Log progress within the stage
beautiful_logger.log_progress("Processing items", current=50, total=100)

# Log stage-specific events
beautiful_logger.log_stage_event("validation", "Data validation passed")

# End the stage with summary
beautiful_logger.end_stage("Processing completed", processed=100, valid=95)
```

### Error Handling

```python
try:
    # Some operation that might fail
    result = api_call()
except ConnectionError as e:
    # Log with component context
    beautiful_logger.log_error(e, "github_api")
except ValueError as e:
    # Log with additional context
    beautiful_logger.log_error(e, "data_validation", record_id="user123")
```

### Metrics Integration

```python
from cmo_agent.core.monitoring import get_global_collector, MetricsLogger

# Get the global metrics collector
collector = get_global_collector()

# Record business metrics
collector.record_business_metrics(
    leads_processed=99,
    leads_enriched=75,
    repos_discovered=46,
    emails_sent=25
)

# Start metrics logging with beautiful output
metrics_logger = MetricsLogger(collector, log_interval=60)
await metrics_logger.start_logging()
```

## 🎯 Benefits

### For Developers

- **Faster debugging** with clear error context and correlation IDs
- **Real-time progress** visibility during development
- **Beautiful console output** that's easy to scan and understand
- **Structured logs** that can be easily parsed and analyzed

### For Operators

- **Campaign monitoring** with stage-by-stage progress tracking
- **Alert system** for proactive issue detection
- **Job-specific logs** for easy troubleshooting
- **Metrics snapshots** for performance monitoring

### For Analysis

- **Structured JSON logs** for machine parsing
- **Correlation IDs** for tracing requests across components
- **Business metrics** tracking for ROI analysis
- **Performance metrics** for optimization opportunities

## 📈 Monitoring Integration

The beautiful logging system integrates seamlessly with monitoring tools:

- **Prometheus metrics** export (optional)
- **ELK Stack** compatible JSON logs
- **Splunk** ready structured logging
- **Custom dashboards** using the structured data

## 🛠️ Customization

### Adding Custom Stages

```python
# Add custom stage icons
STAGE_ICONS['custom_stage'] = '🔧'

# Use in logging
beautiful_logger.start_stage("custom_stage", "Running custom processing")
```

### Custom Formatters

```python
class CustomConsoleFormatter(BeautifulConsoleFormatter):
    def format(self, record):
        # Add custom formatting logic
        return super().format(record)
```

## 🚀 Migration Guide

### From Old Logging

Replace old logging calls:

```python
# Old way
logger.info("Starting repository search")
logger.info(f"Found {len(repos)} repositories")

# New beautiful way
beautiful_logger.start_stage("discovery", "Starting repository search")
beautiful_logger.end_stage("Repository search completed", found=len(repos))
```

### Configuration Updates

Update your config files:

```yaml
# Add to existing logging section
logging:
  beautiful_console: true
  job_specific_files: true
  stage_logging: true
  progress_logging: true
```

## 📚 API Reference

### StageAwareLogger

- `start_stage(stage, message, **kwargs)` - Start a new pipeline stage
- `end_stage(message, **kwargs)` - End the current stage
- `log_progress(message, current, total, **kwargs)` - Log progress within stage
- `log_stage_event(event, message, **kwargs)` - Log a general stage event
- `log_error(error, component, **kwargs)` - Log an error with context

### BeautifulConsoleFormatter

- Automatic color and emoji formatting
- Stage-aware message formatting
- Progress bar rendering
- Error highlighting

### JobSpecificFileHandler

- Creates separate log files per job
- Automatic log directory creation
- JSON Lines format output
- Configurable file naming

---

🎉 **The beautiful logging system is ready to transform your CMO Agent campaigns with enhanced observability, better debugging, and a delightful development experience!**
