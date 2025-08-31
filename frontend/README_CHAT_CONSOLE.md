## CMO Agent Chat Console

Interface to your CMO Agent. It fuses free‑form chat with structured controls, simulations, approvals, and deep introspection—so you can run entire campaigns from one screen.

### TL;DR

- **Product**: A Chat Console (Next.js) that talks to your FastAPI + LangGraph backplane.
- **UX**: Chat messages + AI Cards (Brief, Sim Pack, Outbox, Run Summary, Errors, Policies) + a right‑side Inspector (RunState + Graph + Metrics).
- **Autonomy**: Autopilot Ladder (L0–L4), budgets, guardrails—toggled inline in chat.
- **Streaming**: End‑to‑end SSE for token‑level model output and node events.
- **MVP in 2 sprints**: Chat, Sim Pack, Approvals, Errors, Budgets, Why‑explanations.

### What the Chat Console looks like

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Top Bar:  Campaign switcher  |  Run picker  |  Budget cap  |  Autopilot L0  │
├──────────────────────────────────────────────────────────────────────────────┤
│  Left (Chat)                                                        │Right    │
│  ────────────────────────────────────────────────────────────────   │Inspector│
│  You: "Find 2k Py maintainers active 90d, seq=123. Preflight then   │• RunState│
│       run with $50/day cap."                                        │• Graph   │
│                                                                     │• Metrics │
│  Agent Card: **Campaign Brief** (goal, ICP, limits, risks)          │• Events  │
│  Buttons: [Simulate] [Edit YAML] [Run L1] [Set Budget]              │          │
│                                                                     │          │
│  Agent Card: **Sim Pack** (deliverability, reply forecast, cost)    │          │
│  Buttons: [Run L1] [Open Outbox] [Explain Forecast]                 │          │
│                                                                     │          │
│  Agent Card: **Outbox (5 samples)** with Evidence chips             │          │
│  Buttons per row: [Approve] [Edit] [Skip] [Lock sentence]           │          │
│  Bulk: [Approve ≥ score 80] [Rule…]                                  │          │
│                                                                     │          │
│  Composer: [message…]  Chips: [Brief] [Preflight] [Outbox] [Errors] │          │
└──────────────────────────────────────────────────────────────────────────────┘
```

Everything is driven from chat. The right‑side Inspector is a debugger: live RunState, graph, latency/cost heat, and event log.

### Core AI interactions (all from chat)

- **“Brief this into a campaign.”** → Agent returns a Brief Card + YAML you can accept or edit.
- **“Preflight/simulate.”** → Sim Pack Card with forecasts (reply rate, deliverability, cost bands) and risks + mitigations.
- **“Run at L1 with $50/day, score floor 75.”** → Agent starts, streams steps; you approve as needed.
- **“Show outbox samples & approve rule.”** → Outbox Card with bulk approval rules.
- **“Why did open rates dip?”** → Explain Card pinpoints root cause, proposes fix; [Apply].
- **“Patch policy to forbid unevidenced claims.”** → Policy Card (diff) + enforcement status.

### Autopilot Ladder (inline controls)

- **L0 Manual**: review + approve all.
- **L1 Stage‑gated**: discovery/personalization/send require per‑stage approval.
- **L2 Budgeted**: runs within hard caps (daily sends/$, bounce threshold). Escalates exceptions.
- **L3 Self‑tuning**: adjusts pacing/variants/filters within policy.
- **L4 Fully autonomous** per campaign; generates daily/weekly brief.

Switch level via chat (“Set Autopilot L2 for this run with $100/day”) or top‑bar chip.

### Front‑end stack

- **Next.js (App Router)** + TypeScript
- **Tailwind + shadcn/ui** (fast, consistent UI)
- **TanStack Query** (data fetching, cache)
- **React Flow** (graph inspector)
- **Monaco** (YAML editor for config/policies)
- **SSE** for streaming chat + LangGraph events (simple, robust)

### Backplane (fits your repo)

- **FastAPI endpoints**: `/chat` (send), `/threads/:id/events` (SSE), `/runs/:id/events` (SSE), REST for campaigns/leads/outbox/policies.
- **Redis pub/sub** for run events.
- **Postgres** for threads/messages/runs/leads.
- **Pydantic schemas** shared via OpenAPI → typed client in Next.js.

### Data & types (strongly typed messages)

Message envelope

```ts
export type Role = "user" | "assistant" | "tool" | "system";

export interface ChatMessage {
  id: string;
  threadId: string;
  role: Role;
  createdAt: string; // ISO
  text?: string; // markdown
  card?: UICard; // rich card payloads below
  event?: LanggraphEvent; // streamed node events
}

export type UICard =
  | CampaignBriefCard
  | SimulationCard
  | OutboxCard
  | RunSummaryCard
  | ErrorGroupCard
  | PolicyDiffCard;

export interface CampaignBriefCard {
  type: "campaign_brief";
  goal: string;
  icp: Record<string, any>;
  limits: { maxSteps: number; maxRepos: number; maxPeople: number };
  risks: string[];
  yaml: string; // canonical config
  actions: ActionButton[]; // e.g., Run L1, Edit YAML
}

export interface SimulationCard {
  type: "simulation";
  forecast: {
    replyRate: { mean: number; low: number; high: number };
    deliverability: { mean: number; low: number; high: number };
    dailyCostUSD: number;
  };
  assumptions: string[];
  warnings: string[];
  actions: ActionButton[];
}

export interface OutboxCard {
  type: "outbox";
  runId: string;
  samples: Array<{
    leadId: string;
    score: number;
    email: string;
    subject: string;
    body: string;
    evidence: Array<{ label: string; url: string }>;
    policy: Array<{
      rule: string;
      status: "ok" | "warn" | "block";
      note?: string;
    }>;
  }>;
  bulkActions: ActionButton[];
}

export interface ActionButton {
  id: string; // e.g., "run-l1", "approve-all>=80"
  label: string;
  style?: "primary" | "secondary" | "danger";
  payload?: Record<string, any>;
}
```

LangGraph event (for Inspector + inline chips)

```ts
export interface LanggraphEvent {
  ts: string;
  node: string; // e.g., "enrich_github_user"
  status: "start" | "ok" | "retry" | "error";
  latencyMs?: number;
  costUSD?: number;
  msg?: string;
}
```

### Next.js: layout & components

App layout (sidebar + chat + inspector)

```tsx
// app/(console)/layout.tsx
import "./globals.css";
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen w-screen grid grid-cols-[280px_1fr_360px]">
      <aside className="border-r p-4 overflow-y-auto">
        {/* Campaign/Run switcher */}
      </aside>
      <main className="flex flex-col">{children}</main>
      <aside className="border-l p-4 overflow-y-auto">{/* Inspector */}</aside>
    </div>
  );
}
```

Chat page

```tsx
// app/(console)/threads/[id]/page.tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { ChatMessage, UICard } from "@/types";
import { ChatComposer } from "@/components/ChatComposer";
import { MessageBubble } from "@/components/MessageBubble";
import { useSSE } from "@/lib/useSSE";

export default function ThreadPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const events = useSSE(`/api/threads/${id}/events`); // proxied SSE
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // Append streamed events as assistant/tool messages or event chips
  useEffect(() => {
    for (const evt of events) {
      // evt is already JSON; normalize to ChatMessage or event patch
      if (evt.kind === "message") {
        setMessages((prev) => [...prev, evt.message as ChatMessage]);
      } else if (evt.kind === "event") {
        // attach event to a synthetic tool line
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            threadId: id,
            role: "tool",
            createdAt: new Date().toISOString(),
            event: evt.event,
          },
        ]);
      }
    }
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events, id]);

  const onSend = async (
    text: string,
    options?: { autopilot?: number; budget?: number }
  ) => {
    const res = await fetch(`/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ threadId: id, text, options }),
    });
    if (!res.ok) console.error(await res.text());
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="border-t p-3">
        <ChatComposer onSend={onSend} />
      </div>
    </div>
  );
}
```

SSE hook (robust with backoff)

```ts
// lib/useSSE.ts
import { useEffect, useRef, useState } from "react";

export function useSSE<T = any>(url: string) {
  const [events, setEvents] = useState<T[]>([]);
  const retryRef = useRef(1000);

  useEffect(() => {
    let cancelled = false;
    let es: EventSource | null = null;

    const connect = () => {
      es = new EventSource(url, { withCredentials: true });
      es.onmessage = (e) => {
        if (cancelled) return;
        try {
          setEvents((prev) => [...prev, JSON.parse(e.data)]);
        } catch {}
      };
      es.onerror = () => {
        es?.close();
        if (cancelled) return;
        setTimeout(connect, Math.min(retryRef.current, 15000));
        retryRef.current *= 2;
      };
    };
    connect();
    return () => {
      cancelled = true;
      es?.close();
    };
  }, [url]);

  return events;
}
```

Chat composer with AI chips

```tsx
// components/ChatComposer.tsx
"use client";
import { useState } from "react";

export function ChatComposer({
  onSend,
}: {
  onSend: (text: string, options?: any) => void;
}) {
  const [text, setText] = useState("");
  const [autopilot, setAutopilot] = useState(0);
  const [budget, setBudget] = useState<number | undefined>(undefined);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 flex-wrap">
        <label className="text-xs">Autopilot:</label>
        {[0, 1, 2, 3, 4].map((l) => (
          <button
            key={l}
            onClick={() => setAutopilot(l)}
            className={`text-xs px-2 py-1 rounded border ${
              autopilot === l ? "bg-black text-white" : "bg-white"
            }`}
          >
            L{l}
          </button>
        ))}
        <label className="text-xs ml-3">Budget ($/day):</label>
        <input
          type="number"
          className="w-24 text-sm border rounded px-2 py-1"
          placeholder="50"
          value={budget ?? ""}
          onChange={(e) =>
            setBudget(e.target.value ? Number(e.target.value) : undefined)
          }
        />
        <div className="ml-auto flex gap-1">
          {["Brief", "Preflight", "Outbox", "Errors"].map((t) => (
            <button
              key={t}
              onClick={() =>
                setText((prev) => (prev ? prev + " " : "") + t.toLowerCase())
              }
              className="text-xs px-2 py-1 border rounded"
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2">
        <textarea
          className="flex-1 border rounded p-2 text-sm resize-none h-24"
          placeholder='e.g., "Find 2k Py maintainers active 90d, seq=123. Preflight then run."'
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button
          className="px-4 py-2 rounded bg-black text-white"
          onClick={() => {
            if (text.trim()) {
              onSend(text, { autopilot, budget });
              setText("");
            }
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
```

Message bubble + Card renderer

```tsx
// components/MessageBubble.tsx
"use client";
import { ChatMessage } from "@/types";
import { SimulationCardView } from "./cards/SimulationCardView";
import { BriefCardView } from "./cards/BriefCardView";
import { OutboxCardView } from "./cards/OutboxCardView";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[720px] rounded-lg border p-3 ${
          isUser ? "bg-gray-50" : "bg-white"
        }`}
      >
        {!message.card && message.text && (
          <div className="prose prose-sm">{message.text}</div>
        )}
        {message.card?.type === "simulation" && (
          <SimulationCardView card={message.card} />
        )}
        {message.card?.type === "campaign_brief" && (
          <BriefCardView card={message.card} />
        )}
        {message.card?.type === "outbox" && (
          <OutboxCardView card={message.card} />
        )}
        {message.event && (
          <div className="mt-2 text-xs text-gray-500">
            <code>{message.event.node}</code> · {message.event.status}
            {message.event.latencyMs ? ` · ${message.event.latencyMs}ms` : ""}
            {message.event.costUSD
              ? ` · $${message.event.costUSD.toFixed(4)}`
              : ""}
          </div>
        )}
      </div>
    </div>
  );
}
```

Action button wiring (card → chat command)

```tsx
// components/cards/ActionButton.tsx
"use client";
export function ActionButton({
  action,
  threadId,
}: {
  action: { id: string; label: string; payload?: any };
  threadId: string;
}) {
  const click = async () => {
    await fetch("/api/actions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        threadId,
        actionId: action.id,
        payload: action.payload,
      }),
    });
  };
  return (
    <button onClick={click} className="text-xs px-2 py-1 border rounded">
      {action.label}
    </button>
  );
}
```

### Next.js API proxy (to avoid CORS & keep cookies)

SSE proxy

```ts
// app/api/threads/[id]/events/route.ts
export const runtime = "nodejs";
export async function GET(_: Request, { params }: { params: { id: string } }) {
  const upstream = await fetch(
    `${process.env.API_URL}/threads/${params.id}/events`,
    {
      headers: { Accept: "text/event-stream" },
    }
  );
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
    },
  });
}
```

Chat POST proxy

```ts
// app/api/chat/route.ts
export const runtime = "nodejs";
export async function POST(req: Request) {
  const body = await req.json();
  const resp = await fetch(`${process.env.API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return new Response(await resp.text(), { status: resp.status });
}
```

Action POST

```ts
// app/api/actions/route.ts
export const runtime = "nodejs";
export async function POST(req: Request) {
  const body = await req.json();
  const r = await fetch(`${process.env.API_URL}/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return new Response(await r.text(), { status: r.status });
}
```

### FastAPI endpoints (sketch)

```python
# api/routes/chat.py
from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import asyncio, json

router = APIRouter()

class ChatReq(BaseModel):
  threadId: str
  text: str
  options: dict | None = None

@router.post("/chat")
async def chat(req: ChatReq):
  # enqueue LLM+LangGraph plan/act; link to threadId
  run_id = await start_or_continue_thread(req.threadId, req.text, req.options)
  return {"run_id": run_id}

@router.get("/threads/{thread_id}/events")
async def stream_thread(thread_id: str):
  async def gen():
    yield "retry: 1500\n\n"
    q = subscribe_thread(thread_id)  # Redis Pub/Sub or queue
    try:
      async for evt in q:            # evt: {"kind":"message","message":{...}} or {"kind":"event","event":{...}}
        yield f"data: {json.dumps(evt)}\n\n"
    finally:
      await q.aclose()
  return StreamingResponse(gen(), media_type="text/event-stream")
```

### Policies, safety, and budgets (UI + enforcement)

- **Policy Diff Card**: when you change tone/legal/style, the agent shows diff + implications; violations appear on Outbox rows.
- **Budgets**: set per‑campaign/run in the top bar or message (“Budget $75/day”). Auto‑pause and an Escalation Card appears if thresholds breach (bounces, complaints, MX spikes).
- **Explainability**: “Why not?” always available in message actions; the agent answers in one line + links to evidence.

### DB sketch (Postgres)

```
threads(id, title, created_at, created_by)

messages(id, thread_id, role, text, card_json, created_at)

runs(id, thread_id, campaign_id, status, created_at, updated_at, budget_usd, autopilot_level)

events(id, run_id, ts, node, status, latency_ms, cost_usd, payload_json)

policies(id, version, yaml, created_at)

outbox(id, run_id, lead_id, score, subject, body, evidence_json, policy_status, status)
```

### Ship this in two sprints

**Sprint A (Chat + Preflight + Outbox)**

- Chat thread page (SSE stream).
- `/chat` + `/threads/:id/events` wired to LangGraph runner.
- Cards: Campaign Brief, Sim Pack, Outbox (samples).
- Approvals (single + bulk rules), evidence chips, policy guard v1.
- Inspector: RunState tree + events list.

**Sprint B (Autonomy + Forensics)**

- Autopilot L0–L2 with budget caps + auto‑pause and escalation.
- Errors view + grouped retries + “fix” suggestions.
- “Why” explanations and Run Summary card.
- YAML policy editor + live enforcement.
- Graph view (React Flow) with node heat.

### Why this beats Slack for v1

- **Zero external dependency** and full control over cards and inspector.
- **Faster iteration** on structured AI Cards (Sim, Outbox, Policy, Errors).
- **A single URL demo** shows the whole story: plan → simulate → execute → explain → learn.

If you want, I can expand this into a copy‑paste file map (components, routes, types) tailored to your repo structure so you can scaffold the console immediately.
