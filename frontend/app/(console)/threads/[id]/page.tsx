"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { ChatMessage, SSEEvent } from "@/types";
import { ChatComposer } from "@/components/ChatComposer";
import { MessageBubble } from "@/components/MessageBubble";
import { useSSE } from "@/lib/useSSE";
import { AUTONOMY, AUTONOMY_ICONS, AUTONOMY_COLORS, autonomyToAutopilot, autopilotToAutonomy, type AutonomyLevel } from "@/lib/autonomy";
import { getThread, createThread, updateThread } from "@/lib/threadStorage";


import { useSmokeTestEvaluator } from "@/lib/useSmokeTestEvaluator";

export default function ThreadPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

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
            text: "Welcome to the CMO Agent Console! Type a goal to get started, like: 'Find 2k Python maintainers active in the last 90 days, sequence 123. Preflight then run with $50/day cap.'"
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
          text: "Welcome to the CMO Agent Console! Type a goal to get started, like: 'Find 2k Python maintainers active in the last 90 days, sequence 123. Preflight then run with $50/day cap.'"
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
    // Auto-scroll to bottom on new events
    setTimeout(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
  }, [id]);

  // Set up SSE connection with job ID if available
  const [sseUrl, setSseUrl] = useState(`/api/threads/${id}/events`);
  
  // Update SSE URL when job ID changes
  useEffect(() => {
    const newUrl = currentJobId 
      ? `/api/threads/${id}/events?jobId=${currentJobId}`
      : `/api/threads/${id}/events`;
    setSseUrl(newUrl);
  }, [currentJobId, id]);
    
  const { connectionStatus: sseStatus } = useSSE<SSEEvent>(sseUrl, {
    onEvent: handleSSEEvent,
    onConnectionChange: setConnectionStatus,
  });

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

    // Handle smoke test command locally  
    if (text.toLowerCase().includes("smoke test")) {
      // Start smoke test
      try {
        const smokeRes = await fetch(`/api/smoke-test`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ threadId: id }),
        });
        
        const smokeResult = await smokeRes.json();
        
        if (smokeRes.ok && smokeResult.success) {
          // Set the current job ID for SSE streaming
          setCurrentJobId(smokeResult.jobId);
          
          setMessages((prev) => [...prev, {
            id: crypto.randomUUID(),
            threadId: id,
            role: "assistant", 
            createdAt: new Date().toISOString(),
            text: `🧪 **Real Smoke Test Started**: ${smokeResult.jobId}\n\nRunning live campaign validation with real GitHub data...\n\n**Mode**: 🤝 Co‑pilot (Real Run)\n**Daily Cap**: $10\n**Target**: 5 Python maintainers\n**Scope**: Last 30 days\n\n*This will make real GitHub API calls and show live progress in the Inspector →*`,
          }]);
        } else {
          setMessages((prev) => [...prev, {
            id: crypto.randomUUID(),
            threadId: id,
            role: "system",
            createdAt: new Date().toISOString(),
            text: `⚠️ Smoke Test Failed to Start: ${smokeResult.error}`,
          }]);
        }
      } catch (error) {
        setMessages((prev) => [...prev, {
          id: crypto.randomUUID(),
          threadId: id,
          role: "system",
          createdAt: new Date().toISOString(),
          text: `🔌 Smoke Test Error: Unable to reach backend for smoke test`,
        }]);
      }
      return;
    }



    try {
      const res = await fetch(`/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threadId: id, text, options }),
      });

      const result = await res.json();

      if (res.ok && result.success) {
        // Set the current job ID for SSE streaming
        setCurrentJobId(result.jobId);
        
        // Add success message showing job was created
        setMessages((prev) => [...prev, {
          id: crypto.randomUUID(),
          threadId: id,
          role: "assistant",
          createdAt: new Date().toISOString(),
          text: `🚀 **Job Started**: ${result.jobId}\n\n${result.message}\n\n**Autonomy Level**: ${options?.autonomy || 'L0'} ${options?.autonomy === 'L0' ? '(Dry Run)' : '(Live)'}  \n**Daily Cap**: $${options?.budget || 50}`,
        }]);
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
            
            <div className="flex items-center gap-4">
              <button
                onClick={() => {
                  const smokeTestGoal = "🧪 smoke test";
                  onSend(smokeTestGoal, { autonomy: "L0", budget: 1 });
                }}
                className="text-sm px-4 py-2 bg-green-50 text-green-700 border border-green-200 rounded-md hover:bg-green-100 transition-colors font-medium"
                title="Run 1-minute vertical slice test with stub data. No sends. No spend."
              >
                Smoke Test
              </button>
            </div>
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
                      : 'bg-gray-400'
                  }`}
                />
                <span className="text-gray-600 font-medium">
                  {connectionStatus === 'connected' && 'Live'}
                  {connectionStatus === 'connecting' && 'Connecting...'}
                  {connectionStatus === 'error' && 'Reconnecting...'}
                  {connectionStatus === 'disconnected' && 'Disconnected'}
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
