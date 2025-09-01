#!/usr/bin/env python3
"""
Minimal web UI for CMO Agent (FastAPI + HTML form)
"""
import os
import sys
import logging
from pathlib import Path
from typing import Optional, AsyncIterator, Dict, Any
from datetime import datetime

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# Ensure project root on sys.path for absolute imports
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging as _logging
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _lg = _logging.getLogger(_name)
    _lg.propagate = True
    _lg.handlers.clear()
_logging.basicConfig(level=_logging.INFO)
logger = logging.getLogger(__name__)


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            logger.info("http.request", extra={"structured": {"event": "http.request", "method": request.method, "path": request.url.path}})
        except Exception:
            pass
        response = await call_next(request)
        try:
            logger.info("http.response", extra={"structured": {"event": "http.response", "status": response.status_code, "path": request.url.path}})
        except Exception:
            pass
        return response

# Load /Users/seb/leads/cmo_agent/.env or nearest .env upward from CWD
load_dotenv(find_dotenv(usecwd=True))

from cmo_agent.scripts.run_agent import run_campaign  # reuse async entrypoint
from cmo_agent.scripts.run_execution import ExecutionEngine

app = FastAPI(title="CMO Agent - Minimal UI")
app.add_middleware(RequestLogMiddleware)

# Enable CORS for local Next.js dev UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Expose config files (e.g., smoke_prompt.yaml) by ensuring a config symlink/copy exists in static
try:
    cfg_src = Path(__file__).resolve().parents[1] / "config" / "smoke_prompt.yaml"
    cfg_dst_dir = static_dir / "config"
    cfg_dst_dir.mkdir(parents=True, exist_ok=True)
    cfg_dst = cfg_dst_dir / "smoke_prompt.yaml"
    if cfg_src.exists():
        # Copy on startup to avoid FS permission issues with symlinks in some envs
        import shutil
        try:
            shutil.copyfile(str(cfg_src), str(cfg_dst))
        except Exception:
            pass
except Exception:
    pass

# -----------------------
# Self-test API (smoke test)
# -----------------------
from fastapi import APIRouter

selftest_router = APIRouter(prefix="/api/self-test")

@selftest_router.post("/start")
async def api_selftest_start(mode: str = "mock"):
    eng = _require_engine()
    # Start a constrained smoke job via normal job submission path
    job_id = await eng.submit_job(
        goal="🧪 Self‑Test: vertical slice",
        metadata={
            "threadId": "default",
            "test_type": "smoke_test" if mode != "live-lite" else "smoke_test_real",
            "mode": mode,
            "created_by": "self_test",
        },
    )
    return {"jobId": job_id, "mode": mode}

@selftest_router.get("/status/{job_id}")
async def api_selftest_status(job_id: str):
    # Reuse summary snapshot
    return await api_get_job_summary(job_id)

app.include_router(selftest_router)


INDEX_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>CMO Agent</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 24px; background:#f6f7fb; }
      .container { max-width: 720px; margin: 0 auto; background:#fff; padding: 24px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); }
      h1 { margin: 0 0 12px; }
      form { display: grid; gap: 12px; }
      input[type=text] { padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
      .row { display: flex; gap: 12px; align-items: center; }
      .row label { display: flex; gap: 6px; align-items: center; font-size: 14px; color: #333; }
      button { background:#0070f3; color:#fff; border:0; padding: 10px 14px; border-radius: 6px; cursor:pointer; font-weight:600; }
      .card { background:#fafafa; padding: 12px 14px; border-radius: 6px; border: 1px solid #eee; }
      .muted { color: #666; }
      .stats { display:flex; gap: 12px; margin-top: 12px; }
      .stat { background:#f8fafc; border:1px solid #e7eef6; border-radius:6px; padding:8px 10px; font-size:13px; }
      .footer { margin-top: 18px; font-size: 12px; color:#888; }
    </style>
  </head>
  <body>
    <div class="container">
      <h1>CMO Agent</h1>
      <p class="muted">Enter a goal and run a campaign in dry-run mode. No sending will occur.</p>
      <form method="post" action="/run">
        <input type="text" name="goal" placeholder="e.g., Find 20 Python maintainers active 30d, export CSV only" required />
        <div class="row">
          <label><input type="checkbox" name="dry_run" checked /> Dry run</label>
          <label><input type="checkbox" name="no_emoji" checked /> No emoji</label>
        </div>
        <div class="row">
          <input type="text" name="config" placeholder="Optional config path (e.g., cmo_agent/config/smoke.yaml)" style="flex:1"/>
          <button type="submit">Run</button>
        </div>
      </form>

      {RESULT}

      <div class="footer">Tip: Configure API keys in <code>cmo_agent/.env</code> and source it before starting the server.</div>
    </div>
  </body>
</html>
"""


def render_index(result_html: str = "") -> HTMLResponse:
    html = INDEX_HTML.replace("{RESULT}", result_html)
    return HTMLResponse(html)


# -----------------------
# Background engine wiring
# -----------------------
engine: Optional[ExecutionEngine] = None


@app.on_event("startup")
async def on_startup():
    global engine
    try:
        engine = ExecutionEngine()
        ok = await engine.initialize()
        if not ok:
            raise RuntimeError("Failed to initialize execution engine")
        import asyncio
        asyncio.create_task(engine.start())
    except Exception as e:
        # If engine fails, API endpoints will raise 503s
        print(f"[startup] ExecutionEngine error: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    global engine
    try:
        if engine and engine.worker_pool:
            await engine.worker_pool.stop()
        if engine and engine.metrics_logger:
            engine.metrics_logger.stop_logging()
    except Exception:
        pass


# -----------------------
# Minimal HTML UI routes
# -----------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    return render_index()


@app.post("/run", response_class=HTMLResponse)
async def run(request: Request, goal: str = Form(...), dry_run: Optional[bool] = Form(False), no_emoji: Optional[bool] = Form(False), config: Optional[str] = Form(None)):
    try:
        # Execute campaign via shared runner
        result = await run_campaign(goal, config_path=config if config else None, dry_run=bool(dry_run), no_emoji=bool(no_emoji), interactive=False)

        success = bool(result.get("success"))
        final_state = result.get("final_state") or {}
        report = result.get("report") or {}
        summary = report.get("summary") or {}

        # Build simple result card
        stats = {
            "success": success,
            "steps": summary.get("steps_completed") or (final_state.get("counters", {}) or {}).get("steps", 0),
            "api_calls": summary.get("api_calls_made") or (final_state.get("counters", {}) or {}).get("api_calls", 0),
            "leads": summary.get("leads_processed") or len((final_state.get("leads") or [])),
            "emails_prepared": summary.get("emails_prepared") or len((final_state.get("to_send") or [])),
        }

        result_html = f"""
        <div class=card>
          <div><strong>Result:</strong> {'✅ Success' if success else '❌ Failed'}</div>
          <div class=stats>
            <div class=stat>Steps: {stats['steps']}</div>
            <div class=stat>API calls: {stats['api_calls']}</div>
            <div class=stat>Leads: {stats['leads']}</div>
            <div class=stat>Emails prepared: {stats['emails_prepared']}</div>
          </div>
        </div>
        """
        return render_index(result_html)
    except Exception as e:
        result_html = f"<div class=card><strong>Result:</strong> ❌ Error: {e}</div>"
        return render_index(result_html)


# -----------------------
# JSON API for Chat UI
# -----------------------

def _require_engine() -> ExecutionEngine:
    if not engine or not engine.is_running:
        raise HTTPException(status_code=503, detail="Execution engine not running")
    return engine


@app.post("/api/jobs")
async def api_create_job(payload: Dict[str, Any]):
    eng = _require_engine()
    goal = (payload or {}).get("goal")
    if not goal or not isinstance(goal, str):
        raise HTTPException(status_code=400, detail="Missing 'goal'")

    # Extract metadata from payload
    metadata = (payload or {}).get("metadata", {})
    config_path = (payload or {}).get("config_path")

    # Optional dryRun flag affects agent config globally for now
    dry_run = bool((payload or {}).get("dryRun", True))
    try:
        eng.agent.config = eng.agent.config or {}
        features = eng.agent.config.get("features", {}) if isinstance(eng.agent.config.get("features"), dict) else {}
        features["dry_run"] = dry_run
        eng.agent.config["features"] = features
    except Exception:
        pass

    # Submit job with metadata and config
    job_id = await eng.submit_job(goal, metadata=metadata, config_path=config_path)
    status = await eng.get_job_status(job_id)
    if not status:
        return JSONResponse(status_code=201, content={"id": job_id, "status": "queued", "goal": goal, "created_at": None})
    return {
        "id": status["job_id"],
        "status": status["status"],
        "goal": status["goal"],
        "created_at": status["created_at"],
        "metadata": status.get("metadata", {}),
    }


@app.get("/api/jobs")
async def api_list_jobs():
    """List all jobs"""
    eng = _require_engine()
    jobs = await eng.list_jobs()
    return jobs


@app.get("/api/jobs/{job_id}")
async def api_get_job(job_id: str):
    eng = _require_engine()
    status = await eng.get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": status["job_id"],
        "status": status["status"],
        "goal": status["goal"],
        "created_at": status["created_at"],
        "metadata": status.get("metadata", {}),
    }


@app.get("/api/jobs/{job_id}/summary")
async def api_get_job_summary(job_id: str):
    """Return a final snapshot for a job: status, summary, artifacts.
    Safe for late calls after SSE closes.
    """
    eng = _require_engine()
    status = await eng.get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    # Build summary from progress metrics if available
    summary = None
    try:
        prog = status.get("progress") or {}
        metrics = (prog.get("metrics") or {}) if isinstance(prog, dict) else {}
        summary = {
            "duration_ms": int(metrics.get("duration_ms") or 0),
            "repos": int(metrics.get("repos") or 0),
            "candidates": int(metrics.get("candidates") or 0),
            "leads_with_emails": int(metrics.get("leads_with_emails") or 0),
        }
    except Exception:
        summary = None

    return {
        "status": status.get("status"),
        "summary": summary,
        "artifacts": status.get("artifacts") or [],
    }


@app.post("/api/jobs/{job_id}/pause")
async def api_pause_job(job_id: str):
    eng = _require_engine()
    ok = await eng.pause_job(job_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Cannot pause job")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/resume")
async def api_resume_job(job_id: str):
    eng = _require_engine()
    ok = await eng.resume_job(job_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Cannot resume job")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/cancel")
async def api_cancel_job(job_id: str):
    eng = _require_engine()
    ok = await eng.cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Cannot cancel job")
    return {"ok": True}


@app.get("/api/jobs/{job_id}/events")
async def api_job_events(request: Request, job_id: str):
    # Register active listener for accurate stats
    try:
        if engine and engine.queue and hasattr(engine.queue, "register_progress_listener"):
            engine.queue.register_progress_listener(job_id)
    except Exception:
        pass

    async def event_stream() -> AsyncIterator[str]:
        try:
            client = f"{request.client.host}:{request.client.port}" if request.client else "unknown"
            logger.info("sse_open", extra={"structured": {"evt": "sse_open", "jobId": job_id, "client": client}})
        except Exception:
            pass
        import asyncio, json as _json
        from datetime import datetime

        # Always start with retry instruction
        yield "retry: 1500\n\n"

        # Check if engine is available
        if not engine or not engine.is_running:
            # Engine not available - send status message and keep connection alive
            status_msg = {
                "job_id": job_id,
                "timestamp": datetime.now().isoformat(),
                "event": "job.engine_unavailable",
                "data": {"message": "Execution engine not running - job may be queued"},
            }
            yield "event: status\n"
            yield f"data: {_json.dumps(status_msg)}\n\n"

            # Keep connection alive with periodic status checks
            while True:
                if await request.is_disconnected():
                    break

                # Send keep-alive
                yield ": keep-alive\n\n"
                await asyncio.sleep(10)

                # Check if engine came online
                if engine and engine.is_running:
                    online_msg = {
                        "job_id": job_id,
                        "timestamp": datetime.now().isoformat(),
                        "event": "job.engine_online",
                        "data": {"message": "Execution engine is now running"},
                    }
                    yield "event: status\n"
                    yield f"data: {_json.dumps(online_msg)}\n\n"
                    break

            # If engine is still not available after waiting, continue with keep-alives
            if not engine or not engine.is_running:
                while True:
                    if await request.is_disconnected():
                        break
                    yield ": keep-alive\n\n"
                    await asyncio.sleep(15)
                return

        # Engine is available - proceed with normal streaming
        try:
            # Send an initial status snapshot if available
            try:
                status = await engine.get_job_status(job_id)
                if status:
                    # If job already terminal, send terminal frame and exit (late connect)
                    if status["status"] in ["completed", "failed", "cancelled"]:
                        # Replay a terminal event with summary/artifacts and close
                        yield "retry: 30000\n\n"
                        # Try to build summary/artifacts snapshot from status/progress
                        summary = None
                        artifacts = status.get("artifacts") or []
                        try:
                            prog = status.get("progress") or {}
                            metrics = (prog.get("metrics") or {}) if isinstance(prog, dict) else {}
                            summary = {
                                "duration_ms": int(metrics.get("duration_ms") or 0),
                                "repos": int(metrics.get("repos") or 0),
                                "candidates": int(metrics.get("candidates") or 0),
                                "leads_with_emails": int(metrics.get("leads_with_emails") or 0),
                            }
                        except Exception:
                            summary = None
                        final_evt = {
                            "evt": "job_finalized",
                            "status": status["status"],
                            "summary": summary,
                            "artifacts": artifacts,
                        }
                        yield "event: job_finalized\n"
                        yield f"data: {_json.dumps(final_evt)}\n\n"
                        return
                    initial = {
                        "job_id": status["job_id"],
                        "timestamp": datetime.now().isoformat(),
                        "event": f"job.{status['status']}",
                        "data": {"progress": status.get("progress")},
                    }
                    yield "event: status\n"
                    yield f"data: {_json.dumps(initial)}\n\n"
            except Exception as e:
                # Send error but continue streaming
                error_msg = {
                    "job_id": job_id,
                    "timestamp": datetime.now().isoformat(),
                    "event": "job.status_error",
                    "data": {"error": str(e)},
                }
                yield "event: status\n"
                yield f"data: {_json.dumps(error_msg)}\n\n"

            # Try to get progress stream
            try:
                queue = await engine.queue.get_progress_stream(job_id)

                # Check if this is a dummy queue (returns None immediately)
                # This happens when the job doesn't have an active progress stream
                try:
                    # Peek at the queue with a very short timeout
                    first_item = await asyncio.wait_for(queue.get(), timeout=0.1)
                    if first_item is None:
                        # This is a completed/inactive job, fall back to status polling
                        raise Exception("No active progress stream for job")
                    else:
                        # Put the item back for normal processing
                        await queue.put(first_item)
                except asyncio.TimeoutError:
                    # Queue is empty but valid - proceed with normal streaming
                    pass

            except Exception as e:
                # If progress stream fails, fall back to polling
                logger.info(f"No active progress stream for job {job_id}, using polling mode: {e}")

                # Send initial status
                try:
                    status = await engine.get_job_status(job_id)
                    if status:
                        initial_msg = {
                            "job_id": job_id,
                            "timestamp": datetime.now().isoformat(),
                            "event": f"job.status.{status['status']}",
                            "data": {
                                "status": status["status"],
                                "progress": status.get("progress"),
                                "message": "Using polling mode - job may be completed or inactive"
                            },
                        }
                        yield "event: status\n"
                        yield f"data: {_json.dumps(initial_msg)}\n\n"

                        # If job is already done, close the stream gracefully
                        if status["status"] in ["completed", "failed", "cancelled"]:
                            final_msg = {
                                "job_id": job_id,
                                "timestamp": datetime.now().isoformat(),
                                "event": "job.stream_end",
                                "data": {"reason": f"Job already {status['status']}"},
                            }
                            yield "event: done\n"
                            yield f"data: {_json.dumps(final_msg)}\n\n"
                            return
                except Exception:
                    pass

                # Poll for status updates
                poll_count = 0
                while poll_count < 60:  # Limit polling to 5 minutes (60 * 5s)
                    if await request.is_disconnected():
                        break

                    try:
                        status = await engine.get_job_status(job_id)
                        if status:
                            poll_msg = {
                                "job_id": job_id,
                                "timestamp": datetime.now().isoformat(),
                                "event": "job.poll_status",
                                "data": {"status": status["status"], "progress": status.get("progress")},
                            }
                            yield "event: status\n"
                            yield f"data: {_json.dumps(poll_msg)}\n\n"

                            # Exit if job is done
                            if status["status"] in ["completed", "failed", "cancelled"]:
                                break
                    except Exception:
                        pass

                    await asyncio.sleep(5)
                    poll_count += 1

                # Send final message before closing
                close_msg = {
                    "job_id": job_id,
                    "timestamp": datetime.now().isoformat(),
                    "event": "job.stream_end",
                    "data": {"reason": "Polling timeout reached"},
                }
                yield "event: done\n"
                yield f"data: {_json.dumps(close_msg)}\n\n"
                return

            # Normal progress streaming
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # keep-alive comment to prevent proxies from closing connection
                    yield ": keep-alive\n\n"
                    continue

                if item is None:
                    # Stream end signal: emit a terminal job_finalized event if possible
                    try:
                        status = await engine.get_job_status(job_id)
                    except Exception:
                        status = None
                    summary = None
                    artifacts = []
                    state_status = "completed"
                    try:
                        if status:
                            state_status = status.get("status") or state_status
                            artifacts = status.get("artifacts") or []
                            prog = status.get("progress") or {}
                            metrics = (prog.get("metrics") or {}) if isinstance(prog, dict) else {}
                            summary = {
                                "duration_ms": int(metrics.get("duration_ms") or 0),
                                "repos": int(metrics.get("repos") or 0),
                                "candidates": int(metrics.get("candidates") or 0),
                                "leads_with_emails": int(metrics.get("leads_with_emails") or 0),
                            }
                    except Exception:
                        pass
                    final_evt = {
                        "evt": "job_finalized",
                        "status": state_status,
                        "summary": summary,
                        "artifacts": artifacts,
                    }
                    yield "event: job_finalized\n"
                    yield f"data: {_json.dumps(final_evt)}\n\n"
                    return

                try:
                    # Support named events when a dict with 'evt' is pushed to the stream
                    if isinstance(item, dict) and item.get("evt"):
                        yield f"event: {item.get('evt')}\n"
                        yield f"data: {_json.dumps(item)}\n\n"
                    else:
                        payload = {
                            "job_id": job_id,
                            "timestamp": datetime.now().isoformat(),
                            "event": "job.progress",
                            "data": item.to_dict() if hasattr(item, "to_dict") else item,
                        }
                        yield "event: progress\n"
                        yield f"data: {_json.dumps(payload)}\n\n"
                except Exception:
                    # Skip malformed event
                    continue

        except Exception as e:
            # Send error and continue with keep-alives
            error_msg = {
                "job_id": job_id,
                "timestamp": datetime.now().isoformat(),
                "event": "job.stream_error",
                "data": {"error": str(e)},
            }
            yield f"data: {_json.dumps(error_msg)}\n\n"

            # Keep connection alive even on errors
            while True:
                if await request.is_disconnected():
                    break
                yield ": keep-alive\n\n"
                await asyncio.sleep(15)
        finally:
            try:
                reason = "client_abort" if await request.is_disconnected() else "completed"
                logger.info("sse_close", extra={"structured": {"evt": "sse_close", "jobId": job_id, "reason": reason}})
            except Exception:
                pass

    async def on_close():
        try:
            if engine and engine.queue and hasattr(engine.queue, "unregister_progress_listener"):
                engine.queue.unregister_progress_listener(job_id)
        except Exception:
            pass

    response = StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })

    # Best-effort cleanup on disconnect
    try:
        # FastAPI doesn't provide a direct on_close for StreamingResponse.
        # We poll the request for disconnect and cleanup in background.
        import asyncio

        async def _wait_and_cleanup():
            while True:
                try:
                    if await request.is_disconnected():
                        await on_close()
                        break
                    await asyncio.sleep(5)
                except Exception:
                    break

        asyncio.create_task(_wait_and_cleanup())
    except Exception:
        pass

    return response


def main():
    import uvicorn
    port = int(os.getenv("CMO_WEB_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
