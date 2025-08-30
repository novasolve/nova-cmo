# CMO Agent Execution Model

## Overview

The CMO Agent execution model is designed for **async-first, long-running campaigns** that can process thousands of leads over hours or days. It implements a **job-queue-worker pattern** with persistent state, resumability, and streaming progress.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Chat UI   │────▶│ Job Queue   │────▶│  Workers   │────▶│  LangGraph  │
│             │     │             │     │             │     │   Agent     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                     │                   │
       ▼                   ▼                     ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Job State  │     │  RunState   │     │   Results   │     │  Artifacts  │
│   (DB)      │     │  (Memory)   │     │   (DB)      │     │   (S3/FS)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

## Core Components

### 1. Job Management

**Job Structure:**

```python
class Job:
    id: str                    # UUID for the job
    goal: str                  # User's natural language request
    status: JobStatus          # queued, running, paused, completed, failed
    config: Dict[str, Any]     # Job-specific configuration overrides
    metadata: Dict[str, Any]   # created_at, created_by, priority, etc.
    run_state: RunState        # Current execution state
    artifacts: List[str]       # Paths to generated files
    progress: ProgressInfo     # Current progress metrics
```

**Job Status Flow:**

```
queued → running → [paused ↔ running] → completed|failed
```

### 2. Queue System

**Queue Interface:**

```python
class JobQueue:
    async def enqueue_job(self, job: Job) -> str:
        """Add job to queue, return job_id"""

    async def dequeue_job(self) -> Optional[Job]:
        """Get next job to process"""

    async def update_job_status(self, job_id: str, status: JobStatus) -> None:
        """Update job status"""

    async def get_job_progress(self, job_id: str) -> ProgressInfo:
        """Get real-time progress info"""
```

**Queue Implementation Options:**

- **Redis Queue**: For distributed workers
- **PostgreSQL**: For ACID compliance
- **SQLite**: For single-machine simplicity
- **In-memory**: For development/testing

### 3. Worker Pool

**Worker Architecture:**

```python
class JobWorker:
    def __init__(self, queue: JobQueue, agent: CMOAgent):
        self.queue = queue
        self.agent = agent
        self.running_jobs = {}  # job_id -> Task

    async def run_worker_loop(self):
        """Main worker loop"""
        while True:
            try:
                # Get next job
                job = await self.queue.dequeue_job()
                if not job:
                    await asyncio.sleep(1)  # No jobs available
                    continue

                # Process job
                await self._process_job(job)

            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(5)  # Backoff on errors

    async def _process_job(self, job: Job):
        """Process a single job"""
        try:
            # Update status to running
            await self.queue.update_job_status(job.id, JobStatus.RUNNING)

            # Run the CMO Agent
            result = await self.agent.run_job(job.goal, job.metadata.get('created_by'))

            # Update final status
            status = JobStatus.COMPLETED if result.get('success') else JobStatus.FAILED
            await self.queue.update_job_status(job.id, status)

            # Store results
            await self._store_job_results(job, result)

        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            await self.queue.update_job_status(job.id, JobStatus.FAILED)
```

### 4. Async Execution Engine

**Execution Flow:**

```python
async def run_job(self, goal: str, created_by: str = "user") -> Dict[str, Any]:
    """Execute a complete job end-to-end"""

    # 1. Initialize job state
    job_meta = JobMetadata(goal, created_by)
    initial_state = self._create_initial_state(job_meta)

    # 2. Run LangGraph workflow
    try:
        async for step_result in self.graph.astream(initial_state):
            # Stream progress updates
            await self._emit_progress(job_meta.job_id, step_result)

            # Checkpoint state periodically
            if self._should_checkpoint(step_result):
                await self._checkpoint_state(job_meta.job_id, step_result)

            # Check for pause/resume signals
            if await self._should_pause(job_meta.job_id):
                await self._pause_execution(job_meta.job_id, step_result)
                break

        # 3. Finalize results
        final_result = await self._finalize_job(job_meta.job_id)

        return {
            "success": True,
            "job_id": job_meta.job_id,
            "final_state": final_result,
            "artifacts": await self._collect_artifacts(job_meta.job_id)
        }

    except Exception as e:
        logger.error(f"Job execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "job_id": job_meta.job_id
        }
```

### 5. Progress Streaming

**Progress Interface:**

```python
class ProgressEmitter:
    async def emit_progress(self, job_id: str, progress: ProgressInfo):
        """Emit progress update to listeners"""

    async def get_progress_stream(self, job_id: str):
        """Get async stream of progress updates"""
```

**Progress Info Structure:**

```python
@dataclass
class ProgressInfo:
    job_id: str
    stage: str                    # "discovery", "extraction", "enrichment", etc.
    step: int                     # Current step number
    total_steps: Optional[int]    # Estimated total steps
    current_item: str             # What we're currently processing
    items_processed: int          # How many items done
    items_total: Optional[int]    # Total items to process
    metrics: Dict[str, Any]       # API calls, rate limits, etc.
    artifacts: List[str]          # Generated files
    errors: List[str]             # Recent errors
    estimated_completion: Optional[datetime]  # ETA
```

### 6. State Persistence & Checkpoints

**Persistence Layer:**

```python
class StateStore:
    async def save_job_state(self, job_id: str, state: RunState):
        """Persist job state to storage"""

    async def load_job_state(self, job_id: str) -> RunState:
        """Load job state from storage"""

    async def save_artifact(self, job_id: str, name: str, data: bytes) -> str:
        """Save artifact and return path"""

    async def list_artifacts(self, job_id: str) -> List[str]:
        """List all artifacts for job"""
```

**Checkpoint Strategy:**

- **Time-based**: Checkpoint every N minutes
- **Step-based**: Checkpoint every N steps
- **Volume-based**: Checkpoint every N leads processed
- **Error-based**: Checkpoint before risky operations

### 7. Pause/Resume System

**Pause Interface:**

```python
class JobController:
    async def pause_job(self, job_id: str):
        """Signal job to pause at next safe point"""

    async def resume_job(self, job_id: str):
        """Resume paused job"""

    async def cancel_job(self, job_id: str):
        """Cancel job execution"""

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get current job status"""
```

**Safe Pause Points:**

- After tool execution completes
- Before expensive operations
- At step boundaries
- When rate limits are hit

## Implementation Roadmap

### Phase 1: Core Execution (Current)

- [x] Job structure and metadata
- [x] Basic queue interface
- [x] Worker loop skeleton
- [x] State persistence
- [x] Progress tracking

### Phase 2: Async Features

- [ ] Full async execution with streaming
- [ ] Background worker pool
- [ ] Real-time progress updates
- [ ] Checkpoint and resume
- [ ] Pause/resume controls

### Phase 3: Production Features

- [ ] Distributed worker support
- [ ] Fault tolerance and recovery
- [ ] Performance monitoring
- [ ] Scaling and load balancing
- [ ] Advanced queue features

## Usage Examples

### 1. Simple Job Execution

```python
# Create and run a job
job_id = await queue.enqueue_job({
    "goal": "Find 2k Python maintainers active in last 90 days",
    "config": {"max_repos": 500, "activity_days": 90}
})

# Monitor progress
async for progress in queue.get_progress_stream(job_id):
    print(f"Stage: {progress.stage}, Progress: {progress.items_processed}/{progress.items_total}")

# Get final results
result = await queue.get_job_result(job_id)
print(f"Generated {len(result.artifacts)} files")
```

### 2. Worker Pool Management

```python
# Start worker pool
workers = []
for i in range(5):  # 5 concurrent workers
    worker = JobWorker(queue, cmo_agent)
    workers.append(asyncio.create_task(worker.run_worker_loop()))

# Workers run indefinitely, processing jobs as they arrive
await asyncio.gather(*workers)
```

### 3. Long-Running Campaign

```python
# Submit large campaign
job_id = await queue.enqueue_job({
    "goal": "Find 10k developers across ML ecosystem, personalize and send via Instantly",
    "priority": "high",
    "estimated_duration": "8 hours"
})

# Monitor with automatic checkpoints
progress_stream = queue.get_progress_stream(job_id)
async for progress in progress_stream:
    if progress.stage == "discovery":
        print(f"Found {progress.items_processed} repos")
    elif progress.stage == "sending":
        print(f"Sent {progress.items_processed} emails")

    # Automatic checkpoints every 1000 leads
    if progress.items_processed % 1000 == 0:
        print(f"Checkpoint: {progress.items_processed} leads processed")
```

## Configuration

### Worker Configuration

```yaml
workers:
  pool_size: 5 # Number of concurrent workers
  max_jobs_per_worker: 10 # Jobs before worker restart
  heartbeat_interval: 30 # Heartbeat frequency (seconds)
  graceful_shutdown: 60 # Shutdown timeout (seconds)

queue:
  type: redis # redis, postgres, sqlite
  max_retries: 3
  retry_delay: 5 # seconds
  priority_levels: 3

persistence:
  type: postgres # postgres, sqlite, redis
  checkpoint_interval: 300 # seconds
  max_checkpoints: 50
  compression: true
```

### Job Configuration

```python
job_config = {
    "timeouts": {
        "job_timeout": 3600,     # 1 hour max per job
        "step_timeout": 300,     # 5 minutes max per step
        "api_timeout": 30,       # 30 seconds max per API call
    },
    "limits": {
        "max_concurrent_jobs": 10,
        "max_queue_size": 1000,
        "rate_limit_buffer": 0.8,  # Use 80% of rate limits
    },
    "checkpoints": {
        "time_interval": 300,    # Every 5 minutes
        "step_interval": 50,     # Every 50 steps
        "volume_interval": 1000, # Every 1000 leads
    }
}
```

## Error Handling & Recovery

### Error Types

- **Transient Errors**: Network timeouts, rate limits → Auto-retry
- **Permanent Errors**: Invalid API keys, bad data → Fail job
- **Worker Errors**: Worker crashes → Restart worker, requeue job
- **System Errors**: Database failures → Graceful degradation

### Recovery Strategies

- **Checkpoint-based**: Resume from last good state
- **Idempotent operations**: Safe to retry failed operations
- **Partial results**: Save successful operations, retry failed ones
- **Circuit breakers**: Temporarily disable failing components

## Monitoring & Observability

### Metrics to Track

- Job throughput (jobs/hour)
- Worker utilization (%)
- Queue depth and wait times
- Error rates by component
- API call success rates
- Memory and CPU usage

### Logging Structure

```
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "job_id": "cmo-12345",
  "worker_id": "worker-01",
  "stage": "enrichment",
  "step": 42,
  "message": "Enriched user profile",
  "metrics": {
    "api_calls": 150,
    "leads_processed": 89,
    "rate_limit_remaining": 4500
  }
}
```

## Testing Strategy

### Unit Tests

- Job lifecycle management
- Worker state transitions
- Queue operations
- Persistence layer

### Integration Tests

- Full job execution pipeline
- Worker pool coordination
- Progress streaming
- Error recovery scenarios

### Load Tests

- Multiple concurrent jobs
- Large-scale campaigns (10k+ leads)
- High-throughput scenarios
- Failure injection testing

## Open Questions

1. **Queue Technology**: Redis vs PostgreSQL vs custom implementation?
2. **State Serialization**: JSON vs Pickle vs custom format?
3. **Worker Scaling**: Horizontal pod scaling vs process pools?
4. **Checkpoint Strategy**: Time-based vs event-based vs hybrid?
5. **Progress Streaming**: WebSocket vs Server-Sent Events vs polling?

---

**Next Steps:** Implement the core job management and worker system with async execution and progress streaming.
