"use client";
import { ChatMessage } from "@/types";
import { SimulationCardView } from "./cards/SimulationCardView";
import { BriefCardView } from "./cards/BriefCardView";
import { OutboxCardView } from "./cards/OutboxCardView";
import { RunSummaryCardView } from "./cards/RunSummaryCardView";
import { ErrorGroupCardView } from "./cards/ErrorGroupCardView";
import { PolicyDiffCardView } from "./cards/PolicyDiffCardView";

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
    return (
      <div className="flex justify-center">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800 max-w-2xl">
          {message.text}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[720px] rounded-lg border p-3 ${
          isUser ? "bg-gray-50 border-gray-200" : "bg-white border-gray-200"
        }`}
      >
        {!message.card && message.text && (
          <div className="prose prose-sm max-w-none">
            <div className="whitespace-pre-wrap">{message.text}</div>
          </div>
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
        {message.card?.type === "run_summary" && (
          <RunSummaryCardView card={message.card} />
        )}
        {message.card?.type === "error_group" && (
          <ErrorGroupCardView card={message.card} />
        )}
        {message.card?.type === "policy_diff" && (
          <PolicyDiffCardView card={message.card} />
        )}
        
        <div className="mt-2 text-xs text-gray-400">
          {new Date(message.createdAt).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
