"use client";
import { useEffect, useRef, useState } from "react";
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
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      threadId: id,
      role: "system",
      createdAt: new Date().toISOString(),
      text: "Welcome to the CMO Agent Console! Type a goal to get started, like: 'Find 2k Python maintainers active in the last 90 days, sequence 123. Preflight then run with $50/day cap.'"
    }
  ]);
  const events = useSSE<SSEEvent>(`/api/threads/${id}/events`);
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
        console.error("Chat API error:", errorText);
        // Add error message
        setMessages((prev) => [...prev, {
          id: crypto.randomUUID(),
          threadId: id,
          role: "assistant",
          createdAt: new Date().toISOString(),
          text: `Error: ${errorText}`,
        }]);
      }
    } catch (error) {
      console.error("Network error:", error);
      setMessages((prev) => [...prev, {
        id: crypto.randomUUID(),
        threadId: id,
        role: "assistant",
        createdAt: new Date().toISOString(),
        text: `Network error: ${error}`,
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
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Budget: $50/day</span>
            <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded">
              Autopilot L0
            </span>
          </div>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Chat Input */}
      <div className="border-t border-gray-200 p-3 bg-white">
        <ChatComposer onSend={onSend} />
      </div>
    </div>
  );
}
