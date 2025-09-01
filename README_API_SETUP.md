# API Setup Instructions

## Environment Loading (Option A - Recommended)

Your setup correctly uses two separate env files:

- `cmo_agent/.env` - Backend secrets (OPENAI_API_KEY, GITHUB_TOKEN, etc.)
- `frontend/.env.local` - Frontend config (API_URL=http://localhost:8000)

## Running the Services

### Terminal 1 (Backend API)

```bash
cd api && uvicorn api.main:app --reload --port 8000
```

**Alternative (direct method):**

```bash
python cmo_agent/scripts/run_web.py
```

### Terminal 2 (Frontend)

```bash
cd frontend && npm install && npm run dev
```

## Verification

- **API:** http://localhost:8000/ (should show CMO Agent web UI)
- **Frontend:** http://localhost:3000/ (Next.js console)
- **API Docs:** http://localhost:8000/docs (FastAPI auto-generated docs)

## Environment Loading Details

- Backend uses `load_dotenv(find_dotenv(usecwd=True))` to walk up and find `cmo_agent/.env`
- Frontend automatically reads `frontend/.env.local`
- CORS enabled for localhost:3000 in FastAPI
- No secrets exposed to browser (only server-side env vars)

## Known Issues

- **Graph View:** Shows placeholder - React Flow integration not implemented yet (expected)
- **Port conflicts:** Kill existing processes with `pkill -f uvicorn` if needed
