"use client";
import { ChatMessage } from "@/types";
import { SimulationCardView } from "./cards/SimulationCardView";
import { BriefCardView } from "./cards/BriefCardView";
import { OutboxCardView } from "./cards/OutboxCardView";
import { RunSummaryCardView } from "./cards/RunSummaryCardView";
import { ErrorGroupCardView } from "./cards/ErrorGroupCardView";
import { PolicyDiffCardView } from "./cards/PolicyDiffCardView";
// Optional card; import lazily where used to avoid build-time resolution if absent
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const isTool = message.role === "tool";

  if (isTool && message.event) {
    return (
      <div className="flex justify-center">
        <div className="bg-gray-100 border rounded-lg px-3 py-2 text-xs text-gray-600 max-w-md">
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                message.event.status === "ok"
                  ? "bg-green-500"
                  : message.event.status === "error"
                  ? "bg-red-500"
                  : message.event.status === "retry"
                  ? "bg-yellow-500"
                  : "bg-blue-500"
              }`}
            />
            <code className="font-mono">{message.event.node}</code>
            <span>·</span>
            <span>{message.event.status}</span>
            {message.event.latencyMs && (
              <>
                <span>·</span>
                <span>{message.event.latencyMs}ms</span>
              </>
            )}
            {message.event.costUSD && (
              <>
                <span>·</span>
                <span>${message.event.costUSD.toFixed(4)}</span>
              </>
            )}
          </div>
          {message.event.msg && (
            <div className="mt-1 text-gray-500">{message.event.msg}</div>
          )}
        </div>
      </div>
    );
  }

  if (isSystem) {
    const isError = message.text?.includes('Error') || message.text?.includes('⚠️');
    const isConnection = message.text?.includes('Connection') || message.text?.includes('🔌');

    return (
      <div className="flex justify-center">
        <div className={`border rounded-lg p-3 text-sm max-w-2xl ${
          isError
            ? 'bg-red-50 border-red-200 text-red-800'
            : isConnection
            ? 'bg-orange-50 border-orange-200 text-orange-800'
            : 'bg-blue-50 border-blue-200 text-blue-800'
        }`}>
          <div className="whitespace-pre-wrap">{message.text}</div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} message-bubble`}>
      <div
        className={`max-w-[720px] rounded-lg border p-3 ${
          isUser ? "bg-gray-50 border-gray-200" : "bg-white border-gray-200"
        } ${message.card ? "card-container" : ""}`}
      >
        {!message.card && message.text && (
          <div className="text-sm leading-relaxed">
            {isUser ? (
              // User messages as plain text
              <div className="whitespace-pre-wrap streaming-text">{message.text}</div>
            ) : (
              // Assistant/system messages with markdown rendering
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                className="prose prose-sm prose-gray max-w-none streaming-text"
                components={{
                  // Custom components for better styling
                  p: ({ children }) => <div className="mb-2 last:mb-0">{children}</div>,
                  strong: ({ children }) => <span className="font-semibold text-gray-900">{children}</span>,
                  em: ({ children }) => <span className="italic text-gray-700">{children}</span>,
                  code: ({ children }) => <code className="bg-gray-100 px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                  ul: ({ children }) => <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>,
                  li: ({ children }) => <li className="text-sm">{children}</li>,
                }}
              >
                {message.text}
              </ReactMarkdown>
            )}
          </div>
        )}
        {message.card?.type === "simulation" && (
          <SimulationCardView simulation={message.card as any} />
        )}
        {message.card?.type === "campaign_brief" && (
          <BriefCardView brief={message.card as any} />
        )}
        {message.card?.type === "outbox" && (
          <OutboxCardView outbox={message.card as any} />
        )}
        {message.card?.type === "run_summary" && (
          <RunSummaryCardView summary={message.card as any} />
        )}
        {message.card?.type === "error_group" && (
          <ErrorGroupCardView errors={message.card as any} />
        )}
                {message.card?.type === "policy_diff" && (
          <PolicyDiffCardView card={message.card as any} />
        )}
        {/* smoke_test_results card removed */}

        <div className="mt-2 text-xs text-gray-400">
          {new Date(message.createdAt).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
