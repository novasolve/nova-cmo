#!/usr/bin/env python3
"""
Minimal web UI for CMO Agent (FastAPI + HTML form)
"""
import os
import sys
from pathlib import Path
from typing import Optional, AsyncIterator, Dict, Any

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure project root on sys.path for absolute imports
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load /Users/seb/leads/cmo_agent/.env or nearest .env upward from CWD
load_dotenv(find_dotenv(usecwd=True))

from cmo_agent.scripts.run_agent import run_campaign  # reuse async entrypoint
from cmo_agent.scripts.run_execution import ExecutionEngine

app = FastAPI(title="CMO Agent - Minimal UI")

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
    eng = _require_engine()

    async def event_stream() -> AsyncIterator[str]:
        import asyncio, json as _json
        # Send an initial status snapshot if available
        try:
            status = await eng.get_job_status(job_id)
            if status:
                initial = {
                    "job_id": status["job_id"],
                    "timestamp": datetime.now().isoformat(),
                    "event": f"job.{status['status']}",
                    "data": {"progress": status.get("progress")},
                }
                yield f"data: {_json.dumps(initial)}\n\n"
        except Exception:
            pass

        queue = await eng.queue.get_progress_stream(job_id)  # asyncio.Queue of ProgressInfo or None
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
                # Stream end signal
                done = {
                    "job_id": job_id,
                    "timestamp": datetime.now().isoformat(),
                    "event": "job.stream_end",
                    "data": None,
                }
                yield f"data: {_json.dumps(done)}\n\n"
                break

            try:
                payload = {
                    "job_id": job_id,
                    "timestamp": datetime.now().isoformat(),
                    "event": "job.progress",
                    "data": item.to_dict() if hasattr(item, "to_dict") else item,
                }
                yield f"data: {_json.dumps(payload)}\n\n"
            except Exception:
                # Skip malformed event
                continue

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def main():
    import uvicorn
    port = int(os.getenv("CMO_WEB_PORT", "8000"))
    uvicorn.run("cmo_agent.scripts.run_web:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()


