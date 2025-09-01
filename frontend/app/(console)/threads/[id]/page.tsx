"use client";
import { useEffect, useRef, useCallback, useState } from "react";
import { ChatMessage, SSEEvent } from "@/types";
import { ChatComposer } from "@/components/ChatComposer";
import { MessageBubble } from "@/components/MessageBubble";
import { useSSE } from "@/lib/useSSE";
import { useJobStream } from "@/app/hooks/useJobStream";
import { autonomyToAutopilot, type AutonomyLevel } from "@/lib/autonomy";
import { getThread, createThread, updateThread } from "@/lib/threadStorage";
import { useJobState } from "@/lib/jobContext";

export default function ThreadPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'connecting' | 'connected' | 'disconnected' | 'error'>('idle');
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const { jobState, updateJobState, setActiveThread } = useJobState();
  const bottomRef = useRef<HTMLDivElement | null>(null);
  // Keep latest jobState in a ref to avoid changing handler identity
  const jobStateRef = useRef(jobState);
  useEffect(() => { jobStateRef.current = jobState; }, [jobState]);

  // Stage label mapping and pretty printer
  const STAGE_LABEL: Record<string, string> = {
    initialization: "Initializing",
    discovery: "Searching repositories",
    enrichment: "Enriching people",
    outreach: "Preparing outreach",
    completed: "Completed",
    failed: "Failed",
  };
  const prettyStage = (s: string) => STAGE_LABEL[s] ?? s;

  // Keep last seen progress and tool event to dedupe consecutive repeats
  const lastProgressRef = useRef<{ stage: string; current_item: string }>({ stage: "", current_item: "" });
  const lastToolEventRef = useRef<any>(null);

  // Set active thread for job context and check for thread mismatches
  useEffect(() => {
    setActiveThread(id);

    // Check if there's an active job on a different thread and redirect if needed
    // Only check once per thread to avoid excessive API calls
    const checkForActiveJobs = async () => {
      try {
        // Use proxy route to fetch jobs instead of direct backend access
        const jobsResp = await fetch('/api/jobs');
        if (jobsResp.ok) {
          const jobs = await jobsResp.json();

          // Find any running job
          const activeJob = jobs.find((job: any) =>
            job.status === 'running' || job.status === 'pending'
          );

          if (activeJob && activeJob.metadata?.threadId && activeJob.metadata.threadId !== id) {
            console.log(`Found active job on different thread: ${activeJob.metadata.threadId}, mapping to current thread: ${id}`);
            // Map the active job to the current thread for seamless UX
            const { storeThreadJobMapping } = await import("@/lib/threadJobMapping");
            const jobId = activeJob.job_id || activeJob.id;
            storeThreadJobMapping(id, jobId);
            setCurrentJobId(jobId);

            // Update job state to reflect the active job
            updateJobState({
              status: 'running',
              currentNode: activeJob.current_node || 'active_job',
              progress: `Mapped to active job: ${jobId}`,
              autonomyLevel: activeJob.metadata?.autonomy_level || 'L0',
              budget: { used: 0, total: activeJob.metadata?.budget_per_day || 50 },
              currentJobId: jobId
            });
            return;
          }
        }
      } catch (error) {
        console.warn('Could not check for active jobs:', error);
      }
    };

    // Only run once per thread navigation to avoid spamming
    const hasCheckedForThread = sessionStorage.getItem(`checked_active_jobs_${id}`);
    if (!hasCheckedForThread) {
      checkForActiveJobs();
      sessionStorage.setItem(`checked_active_jobs_${id}`, 'true');
    }
  }, [id]); // Only depend on thread ID, not the functions

  // Load initial thread history
  useEffect(() => {
    // Ensure thread exists in storage when navigating to it
    let thread = getThread(id);
    if (!thread) {
      thread = createThread(id, `Thread ${id}`);
      console.log(`Created thread on navigation: ${id}`);
    }

    const loadThreadHistory = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/threads/${id}/messages`);

        if (response.ok) {
          const existingMessages = await response.json();
          setMessages(existingMessages);
        } else {
          // If no history exists or API not implemented, start with welcome message
          setMessages([{
            id: "welcome",
            threadId: id,
            role: "system",
            createdAt: new Date().toISOString(),
            text: "👋 **Welcome to the CMO Agent Console!**\n\nI'm your AI assistant for outbound campaigns. You can:\n\n**💬 Chat naturally**: *\"Hey, what's going on?\"* or *\"What can you help me with?\"*\n\n**🚀 Start campaigns**: *\"Find 50 Python maintainers active 90 days\"*\n\n**🧪 Test the system**: Click the **Self‑Test** button\n\nWhat would you like to do? 😊"
          }]);
        }
      } catch (error) {
        console.warn("Failed to load thread history:", error);
        // Fallback to welcome message
        setMessages([{
          id: "welcome",
          threadId: id,
          role: "system",
          createdAt: new Date().toISOString(),
          text: "👋 **Welcome to the CMO Agent Console!**\n\nI'm your AI assistant for outbound campaigns. You can:\n\n**💬 Chat naturally**: *\"Hey, what's going on?\"* or *\"What can you help me with?\"*\n\n**🚀 Start campaigns**: *\"Find 50 Python maintainers active 90 days\"*\n\n**🧪 Test the system**: Click the **Self‑Test** button\n\nWhat would you like to do? 😊"
        }]);
      } finally {
        setLoading(false);
      }
    };

    loadThreadHistory();
  }, [id]);

  // Handle SSE events without duplication
  const handleSSEEvent = useCallback((evt: SSEEvent) => {
    if (evt.kind === "message") {
      setMessages((prev) => [...prev, evt.message as ChatMessage]);
    } else if (evt.kind === "event" && evt.event) {
      const prev = jobStateRef.current;
      const e = evt.event;
      const derivedStatus = e.status === 'error' ? 'failed' :
                           (e.node === 'completion' || e.msg === 'job_finalized') ? 'completed' : 'running';

      // De-duplicate identical consecutive events for cleaner UI (compare stable fields)
      const prevEvents = prev.events;
      const last = prevEvents[prevEvents.length - 1];
      const isRepeat = !!last && last.node === e.node && last.status === e.status && (last.msg || "") === (e.msg || "");
      const nextEvents = isRepeat ? prevEvents : [...prevEvents, e];

      updateJobState({
        status: derivedStatus,
        currentNode: e.node || (e.msg === 'job_finalized' ? 'completion' : prev.currentNode),
        progress: e.msg || prev.progress,
        metrics: {
          ...prev.metrics,
          nodesCompleted: prev.metrics.nodesCompleted + (e.status === 'ok' ? 1 : 0),
          totalCost: (prev.metrics.totalCost || 0) + (e.costUSD || 0),
          avgLatency: e.latencyMs ?? prev.metrics.avgLatency
        },
        events: nextEvents.slice(-50)
      });

      // Stop streaming once job completes or fails
      if (derivedStatus === 'completed' || derivedStatus === 'failed') {
        setCurrentJobId(null);
      }

      // Also attach event to messages for chat display (dedup consecutive tool events)
      const lastTool = lastToolEventRef.current;
      const isSameToolEvent = lastTool && lastTool.node === e.node && lastTool.status === e.status && (lastTool.msg || "") === (e.msg || "");
      if (!isSameToolEvent) {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            threadId: id,
            role: "tool",
            createdAt: new Date().toISOString(),
            event: evt.event,
          } as any,
        ]);
        lastToolEventRef.current = e;
      }
    }
    // Auto-scroll to bottom on new events
    setTimeout(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
  }, [id, updateJobState]);

  // Only establish SSE connection when there's an active job (proxy to job events)
  const sseUrl = currentJobId ? `/api/jobs/${currentJobId}/events` : null;

  // Reflect "idle" when there is no active job (avoid showing "Connecting...")
  useEffect(() => {
    if (!currentJobId) {
      setConnectionStatus('idle');
    }
  }, [currentJobId]);

  const { connectionStatus: sseStatus } = useSSE<SSEEvent>(sseUrl, {
    onEvent: handleSSEEvent,
    onConnectionChange: setConnectionStatus,
  });

  // Also subscribe directly to job events to catch terminal event and final sync
  useJobStream(currentJobId, {
    onProgress: (evt) => {
      try {
        const data: any = (evt && (evt.data || evt)) || {};
        const rawStage = data.stage || data.node || data.event || "working";
        const stage = prettyStage(String(rawStage));
        const item = data.current_item || data.message || data.msg || "";

        // Deduplicate identical consecutive progress updates
        const last = lastProgressRef.current;
        if (last.stage === stage && (last.current_item || "") === (item || "")) {
          return;
        }
        lastProgressRef.current = { stage, current_item: item || "" };

        // Append a compact progress line into chat for visibility
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            threadId: id,
            role: "tool",
            createdAt: new Date().toISOString(),
            text: `🟢 ${stage}${item ? ": " + item : ""}`,
          } as any,
        ]);
      } catch {}
    },
    onFinalized: (status, summary, artifacts) => {
      // Update job state and surface a capsule message
      updateJobState({
        status: status as any,
        progress: `Run ${status}`,
        events: jobStateRef.current.events,
      });
      if (summary) {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            threadId: id,
            role: "assistant",
            createdAt: new Date().toISOString(),
            text: `✅ ${summary.leads_with_emails} emails • ${summary.repos} repos • ${summary.candidates} candidates • ${Math.round(summary.duration_ms/1000)}s`,
          },
        ]);
      }
      // Stop thread SSE
      setCurrentJobId(null);
    },
    onStreamEnd: () => {
      // Nothing extra; finalSync in hook handles snapshot
    },
  });

  // Log thread-scoped SSE diagnostics
  useEffect(() => {
    console.log('[ThreadPage] SSE URL changed', { threadId: id, sseUrl });
  }, [id, sseUrl]);

  useEffect(() => {
    console.log('[ThreadPage] SSE status', { threadId: id, status: connectionStatus, currentJobId });
  }, [id, connectionStatus, currentJobId]);

  const onSend = async (
    text: string,
    options?: { autonomy?: AutonomyLevel; budget?: number }
  ) => {
    // Add user message immediately
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      threadId: id,
      role: "user",
      createdAt: new Date().toISOString(),
      text,
    };
    setMessages((prev) => [...prev, userMessage]);

    // No special-casing: always go through chat API
    try {
      const res = await fetch(`/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threadId: id, text, options }),
      });

      const result = await res.json();

      if (res.ok && result.success) {
        if (result.type === "conversation") {
          // Handle conversational response (no job created)
          setMessages((prev) => [...prev, {
            id: crypto.randomUUID(),
            threadId: id,
            role: "assistant",
            createdAt: new Date().toISOString(),
            text: result.message,
          }]);
        } else {
          // Handle job creation response
          setCurrentJobId(result.jobId);

          // Add success message showing job was created
          setMessages((prev) => [...prev, {
            id: crypto.randomUUID(),
            threadId: id,
            role: "assistant",
            createdAt: new Date().toISOString(),
            text: `🚀 **Job Started**: ${result.jobId}\n\n**Goal**: ${result.goal || text}\n\n${result.message}\n\n**Autonomy Level**: ${options?.autonomy || 'L0'} ${options?.autonomy === 'L0' ? '(Dry Run)' : '(Live)'}  \n**Daily Cap**: $${options?.budget || 50}`,
          }]);
        }
      } else {
        // Add error message
        setMessages((prev) => [...prev, {
          id: crypto.randomUUID(),
          threadId: id,
          role: "system",
          createdAt: new Date().toISOString(),
          text: `⚠️ Error: ${result.error || 'Failed to create job'}`,
        }]);
      }
    } catch (error) {
      console.error("Network error:", error);
      setMessages((prev) => [...prev, {
        id: crypto.randomUUID(),
        threadId: id,
        role: "system",
        createdAt: new Date().toISOString(),
        text: `🔌 Connection Error: Unable to reach CMO Agent backend. Make sure it's running on port 8000.`,
      }]);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Top Bar */}
      <div className="border-b border-gray-200 bg-white">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <h1 className="text-xl font-semibold text-gray-900">Thread: {id}</h1>

              <div className="flex items-center gap-3 text-sm">
                <select className="border border-gray-300 rounded-md px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option>Campaign: Default</option>
                </select>
                <select className="border border-gray-300 rounded-md px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option>Run: Latest</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-4" />
          </div>
        </div>

        {/* Status Bar */}
        <div className="px-6 py-3 bg-gray-50 border-t border-gray-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6 text-sm">
              {/* Connection Status */}
              <div className="flex items-center gap-2">
                <div
                  className={`w-2 h-2 rounded-full ${
                    connectionStatus === 'connected'
                      ? 'bg-green-500'
                      : connectionStatus === 'connecting'
                      ? 'bg-yellow-500 animate-pulse'
                      : connectionStatus === 'error'
                      ? 'bg-red-500'
                      : 'bg-gray-300'
                  }`}
                />
                <span className="text-gray-600 font-medium">
                  {connectionStatus === 'connected' && 'Live'}
                  {connectionStatus === 'connecting' && 'Connecting...'}
                  {connectionStatus === 'error' && 'Reconnecting...'}
                  {connectionStatus === 'disconnected' && 'Disconnected'}
                  {connectionStatus === 'idle' && 'Idle'}
                </span>
              </div>

              {/* Budget Status */}
              <span className="text-gray-600">
                <span className="font-medium">Daily Cap:</span> $50
              </span>
            </div>

            <div className="flex items-center gap-3">
              {/* Current Autonomy Level */}
              <span className="text-xs px-3 py-1.5 bg-gray-100 text-gray-700 border border-gray-300 rounded-full font-medium">
                🤝 Co‑pilot
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {loading ? (
          <div className="flex justify-center items-center h-32">
            <div className="flex items-center gap-2 text-gray-500">
              <div className="w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
              <span>Loading thread history...</span>
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Chat Input */}
      <div className="border-t border-gray-200 p-3 bg-white">
        <ChatComposer onSend={onSend} />
      </div>
    </div>
  );
}
