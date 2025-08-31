#!/usr/bin/env python3
"""
Minimal web UI for CMO Agent (FastAPI + HTML form)
"""
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# Ensure project root on sys.path for absolute imports
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

load_dotenv()

from cmo_agent.scripts.run_agent import run_campaign  # reuse async entrypoint

app = FastAPI(title="CMO Agent - Minimal UI")

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


def main():
    import uvicorn
    port = int(os.getenv("CMO_WEB_PORT", "8000"))
    uvicorn.run("cmo_agent.scripts.run_web:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()


