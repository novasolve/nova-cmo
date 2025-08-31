"use client";

import { useEffect, useRef, useState } from "react";

type Job = { id: string; status: string; goal: string; created_at: string };
type JobEvent = { job_id: string; timestamp: string; event: string; data?: Record<string, unknown> };

const BASE = process.env.NEXT_PUBLIC_API_BASE as string | undefined;

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  if (!BASE) throw new Error("NEXT_PUBLIC_API_BASE not set");
  const res = await fetch(`${BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function createJobOrFallback(goal: string, dryRun = true) {
  try {
    return await http<Job>("/api/jobs", { method: "POST", body: JSON.stringify({ goal, dryRun }) });
  } catch (e) {
    // Fallback to legacy web endpoint `/run` (form post) if REST API is not available
    if (!BASE) throw e;
    const form = new URLSearchParams();
    form.set("goal", goal);
    form.set("dry_run", String(dryRun));
    await fetch(`${BASE}/run`, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: form });
    // No job id available from legacy endpoint; return a shim
    const shim: Job = { id: "legacy-run", status: "running", goal, created_at: new Date().toISOString() };
    return shim;
  }
}
async function getJob(id: string) { return http<Job>(`/api/jobs/${id}`); }
async function pause(id: string) { return http<void>(`/api/jobs/${id}/pause`, { method: "POST" }); }
async function resume(id: string) { return http<void>(`/api/jobs/${id}/resume`, { method: "POST" }); }
async function cancel(id: string) { return http<void>(`/api/jobs/${id}/cancel`, { method: "POST" }); }

export default function ChatPage() {
  const [messages, setMessages] = useState<{ id: string; role: "user" | "assistant" | "system"; text: string }[]>([
    { id: "m0", role: "system", text: "Type a goal to create a job. Commands: /pause <id>, /resume <id>, /cancel <id>, /status <id>" },
  ]);
  const [input, setInput] = useState("");
  const streams = useRef<Record<string, EventSource>>({});

  useEffect(() => () => { Object.values(streams.current).forEach(es => es.close()); }, []);

  function push(role: "user" | "assistant" | "system", text: string) {
    setMessages(prev => [{ id: `${Date.now()}-${Math.random()}`, role, text }, ...prev]);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    push("user", text);
    setInput("");
    const [cmd, ...rest] = text.split(" ");
    try {
      if (!text.startsWith("/")) {
        const goal = text;
        const job = await createJobOrFallback(goal, true);
        if (job.id === "legacy-run") {
          push("assistant", `Submitted via /run (legacy endpoint). Live stream not available; check backend logs.`);
        } else {
          push("assistant", `Job ${job.id} created (${job.status}). Streaming…`);
          stream(job.id);
        }
      } else if (cmd === "/start") {
        // Backwards compatibility: allow /start <goal>
        const goal = rest.join(" ").trim();
        if (!goal) return push("assistant", "Usage: /start <goal>");
        const job = await createJob(goal, true);
        push("assistant", `Job ${job.id} created (${job.status}). Streaming…`);
        stream(job.id);
      } else if (cmd === "/pause") {
        const id = rest[0]; if (!id) return push("assistant", "Usage: /pause <jobId>");
        await pause(id); push("assistant", `Paused ${id}`);
      } else if (cmd === "/resume") {
        const id = rest[0]; if (!id) return push("assistant", "Usage: /resume <jobId>");
        await resume(id); push("assistant", `Resumed ${id}`); stream(id);
      } else if (cmd === "/cancel") {
        const id = rest[0]; if (!id) return push("assistant", "Usage: /cancel <jobId>");
        await cancel(id); push("assistant", `Cancelled ${id}`); stop(id);
      } else if (cmd === "/status") {
        const id = rest[0]; if (!id) return push("assistant", "Usage: /status <jobId>");
        const job = await getJob(id); push("assistant", `Status ${job.id}: ${job.status} — ${job.goal}`);
      } else {
        push("assistant", "Type a goal to start a job. Commands: /pause <id>, /resume <id>, /cancel <id>, /status <id>");
      }
    } catch (e: any) {
      push("assistant", `Error: ${e?.message || String(e)}`);
    }
  }

  function stream(jobId: string) {
    if (!BASE) return push("assistant", "NEXT_PUBLIC_API_BASE not set");
    if (streams.current[jobId]) return;
    const es = new EventSource(`${BASE}/api/jobs/${jobId}/events`);
    es.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data) as JobEvent;
        const brief = data.data ? JSON.stringify(data.data).slice(0, 200) : "";
        push("assistant", `[${jobId}] ${data.timestamp} • ${data.event}${brief ? " " + brief + (brief.length === 200 ? "…" : "") : ""}`);
        if (["job.completed", "job.failed", "job.cancelled"].includes(data.event)) stop(jobId);
      } catch { push("assistant", `[${jobId}] ${msg.data}`); }
    };
    es.onerror = () => { push("assistant", `[${jobId}] stream error`); stop(jobId); };
    streams.current[jobId] = es;
  }

  function stop(jobId: string) { streams.current[jobId]?.close(); delete streams.current[jobId]; }

  return (
    <main style={{ padding: 16, maxWidth: 900, margin: "0 auto" }}>
      <h1>CMO Agent — Chat</h1>
      <form onSubmit={onSubmit} style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <input value={input} onChange={e => setInput(e.target.value)} placeholder="Find 50 Py repos active 90d" style={{ flex: 1, padding: 8 }} />
        <button type="submit">Send</button>
      </form>
      <ul style={{ listStyle: "none", padding: 0, marginTop: 16 }}>
        {messages.map(m => (
          <li key={m.id} style={{ marginBottom: 12 }}>
            <strong>{m.role}:</strong> {m.text}
          </li>
        ))}
      </ul>
    </main>
  );
}


