# CMO Agent Frontend — Chat UI (Fast Setup)

A minimal Next.js app with a single ChatGPT-style pane to control and monitor CMO Agent jobs.

## Quickstart

```bash
# From repository root
cd frontend
npm install

# Configure backend URL
echo 'NEXT_PUBLIC_API_BASE=http://localhost:8000' > .env.local

# Run
npm run dev
# open http://localhost:3000
```

## Commands

- `<goal text>` — create a new job (dry run by default)
- `/start <goal>` — same as above (backwards compatible)
- `/pause <jobId>` — pause job
- `/resume <jobId>` — resume job and resume streaming
- `/cancel <jobId>` — cancel job
- `/status <jobId>` — show status

## Expected Backend Endpoints

- `POST /api/jobs` { goal, dryRun? }
- `GET /api/jobs/:id`
- `POST /api/jobs/:id/pause|resume|cancel`
- `GET /api/jobs/:id/events` — SSE event stream

## Customize

- Edit `app/page.tsx` for UI/commands.
- Style by adding Tailwind or shadcn later.
- Add auth when exposing publicly.
