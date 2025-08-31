"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { ChatMessage, SSEEvent } from "@/types";
import { ChatComposer } from "@/components/ChatComposer";
import { MessageBubble } from "@/components/MessageBubble";
import { useSSE } from "@/lib/useSSE";
import {
  demoBriefCard,
  demoSimCard,
  demoOutboxCard,
  demoRunSummaryCard,
  demoErrorCard,
  demoPolicyCard
} from "@/components/DemoCards";

export default function ThreadPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // Load initial thread history
  useEffect(() => {
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

  // Set up SSE connection
  const { connectionStatus: sseStatus } = useSSE<SSEEvent>(`/api/threads/${id}/events`, {
    onEvent: handleSSEEvent,
    onConnectionChange: setConnectionStatus,
  });

  const onSend = async (
    text: string,
    options?: { autopilot?: number; budget?: number }
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

    // Handle demo command locally
    if (text.toLowerCase().includes("demo all cards")) {
      const demoCards = [
        { card: demoBriefCard, delay: 500 },
        { card: demoSimCard, delay: 1000 },
        { card: demoOutboxCard, delay: 1500 },
        { card: demoRunSummaryCard, delay: 2000 },
        { card: demoErrorCard, delay: 2500 },
        { card: demoPolicyCard, delay: 3000 },
      ];

      demoCards.forEach(({ card, delay }) => {
        setTimeout(() => {
          setMessages((prev) => [...prev, {
            id: crypto.randomUUID(),
            threadId: id,
            role: "assistant",
            createdAt: new Date().toISOString(),
            card,
          }]);
        }, delay);
      });

      // Add completion message
      setTimeout(() => {
        setMessages((prev) => [...prev, {
          id: crypto.randomUUID(),
          threadId: id,
          role: "assistant",
          createdAt: new Date().toISOString(),
          text: "Demo complete! All card types are now displayed. Try the action buttons to see how they work.",
        }]);
      }, 3500);

      return;
    }

    try {
      const res = await fetch(`/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threadId: id, text, options }),
      });

      if (!res.ok) {
        const errorText = await res.text();
        console.error("Chat API error:", res.status, errorText);

        // Add user-friendly error message
        setMessages((prev) => [...prev, {
          id: crypto.randomUUID(),
          threadId: id,
          role: "system",
          createdAt: new Date().toISOString(),
          text: `⚠️ **Error**: ${res.status === 500 ? 'Server error - please try again' : errorText || 'Unable to process request'}`,
        }]);
      }
    } catch (error) {
      console.error("Network error:", error);

      // Add network error message
      setMessages((prev) => [...prev, {
        id: crypto.randomUUID(),
        threadId: id,
        role: "system",
        createdAt: new Date().toISOString(),
        text: `🔌 **Connection Error**: Unable to reach server. Please check your connection and try again.`,
      }]);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Top Bar */}
      <div className="border-b border-gray-200 p-4 bg-gray-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-semibold">Thread: {id}</h1>
            <select className="text-sm border border-gray-300 rounded px-2 py-1">
              <option>Campaign: Default</option>
            </select>
            <select className="text-sm border border-gray-300 rounded px-2 py-1">
              <option>Run: Latest</option>
            </select>
          </div>
          <div className="flex items-center gap-3">
            {/* Connection Status Indicator */}
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
              <span className="text-xs text-gray-600">
                {connectionStatus === 'connected' && 'Live'}
                {connectionStatus === 'connecting' && 'Connecting...'}
                {connectionStatus === 'error' && 'Reconnecting...'}
                {connectionStatus === 'disconnected' && 'Disconnected'}
              </span>
            </div>

            <div className="h-4 w-px bg-gray-300" />

            <span className="text-sm text-gray-600">Budget: $50/day</span>
            <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded">
              Autopilot L0
            </span>
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
