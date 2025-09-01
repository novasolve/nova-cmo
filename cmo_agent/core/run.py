from __future__ import annotations
import asyncio
import os
import logging
from typing import Callable, Dict, Any, Optional

logger = logging.getLogger("cmo_agent.run")

# Import your engine; adjust the import to your codebase:
try:
    from cmo_agent.scripts.run_execution import ExecutionEngine
except Exception:
    # Fallback if the engine lives elsewhere
    try:
        from .execution import ExecutionEngine  # type: ignore
    except:
        from ..scripts.run_execution import ExecutionEngine  # type: ignore

def _build_payload(goal: str, config_path: Optional[str], metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "goal": goal,
        "dryRun": metadata.get("dryRun", False),
        "config_path": config_path,
        "metadata": metadata,
    }

def run_job_sync(goal: str,
                 config_path: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 on_progress: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
    """
    Submit a job to the same engine the web uses and block until done.
    Set CMO_RUN_MODE=inline to run the agent inline (no queue) if you need to.
    """
    metadata = dict(metadata or {})
    # Ensure CLI looks like a regular job to the backend
    metadata.setdefault("created_by", "cli")
    metadata.setdefault("test_type", "regular")  # NOT smoke_test_real to avoid fast-path
    metadata.setdefault("autopilot_level", 2)    # L2 for real execution
    metadata.setdefault("autonomy_level", "L2")
    metadata.setdefault("budget_per_day", 50)

    payload = _build_payload(goal, config_path, metadata)
    run_mode = os.getenv("CMO_RUN_MODE", "queue").lower()

    if run_mode == "inline":
        # Inline path for quick local dev; calls the Agent directly.
        try:
            from cmo_agent.agents.cmo_agent import CMOAgent
            agent = CMOAgent()
            if on_progress:
                # Wire progress callback if agent supports it
                pass  # agent.on_progress = on_progress  # if supported
            return asyncio.run(agent.run_job(goal, metadata.get("created_by", "cli"), on_progress))
        except Exception as e:
            logger.error(f"Inline execution failed: {e}")
            return {"success": False, "error": str(e)}

    # Queue-based: submit and wait, streaming progress to console
    async def _runner() -> Dict[str, Any]:
        try:
            engine = ExecutionEngine()
            await engine.initialize()
            
            job_id = await engine.submit_job(goal, metadata.get("created_by", "cli"), metadata=metadata, config_path=config_path)
            logger.info("Submitted job %s", job_id, extra={"event":"job_submit","job_id":job_id})
            
            # Wait for completion by polling
            while True:
                status = await engine.get_job_status(job_id)
                if not status:
                    break
                    
                if status.get("status") in ["completed", "failed", "cancelled"]:
                    break
                    
                # Emit progress if callback provided
                if on_progress and status.get("progress"):
                    on_progress(status["progress"])
                
                await asyncio.sleep(1)  # Poll every second
            
            logger.info("Job %s completed", job_id, extra={"event":"job_complete","job_id":job_id})
            
            # Return final status
            final_status = await engine.get_job_status(job_id)
            return {
                "success": final_status.get("status") == "completed",
                "job_id": job_id,
                "final_state": final_status
            }
            
        except Exception as e:
            logger.error(f"Queue execution failed: {e}")
            return {"success": False, "error": str(e)}

    return asyncio.run(_runner())

