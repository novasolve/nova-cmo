#!/usr/bin/env python3
"""
FastAPI entry point for CMO Agent
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

# Ensure project root on sys.path for absolute imports
project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment from cmo_agent/.env or nearest .env upward from CWD
load_dotenv(find_dotenv(usecwd=True))

# Import the existing FastAPI app from run_web.py
from cmo_agent.scripts.run_web import app

# The app is already configured in run_web.py with:
# - CORS for localhost:3000
# - All the API routes (/api/jobs, /api/threads, etc.)
# - Environment loading
# - Static file serving

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("CMO_WEB_PORT", "8000"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
