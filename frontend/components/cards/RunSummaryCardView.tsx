"use client";
import { RunSummaryCard } from "@/types";
import { ActionButton } from "./ActionButton";

export function RunSummaryCardView({ card }: { card: RunSummaryCard }) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800";
      case "running":
        return "bg-blue-100 text-blue-800";
      case "failed":
        return "bg-red-100 text-red-800";
      case "paused":
        return "bg-yellow-100 text-yellow-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900">Run Summary</h3>
        <div className="flex items-center gap-2">
          <span className={`text-xs px-2 py-1 rounded ${getStatusColor(card.status)}`}>
            {card.status}
          </span>
          <span className="text-xs text-gray-500">ID: {card.runId}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="bg-white rounded p-3 border">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Total Leads</div>
          <div className="text-xl font-semibold text-gray-900">
            {card.metrics.totalLeads.toLocaleString()}
          </div>
        </div>

        <div className="bg-white rounded p-3 border">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Emails Sent</div>
          <div className="text-xl font-semibold text-gray-900">
            {card.metrics.emailsSent.toLocaleString()}
          </div>
        </div>

        <div className="bg-white rounded p-3 border">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Replies</div>
          <div className="text-xl font-semibold text-gray-900">
            {card.metrics.replies.toLocaleString()}
          </div>
          {card.metrics.emailsSent > 0 && (
            <div className="text-xs text-gray-500">
              {((card.metrics.replies / card.metrics.emailsSent) * 100).toFixed(1)}% rate
            </div>
          )}
        </div>

        <div className="bg-white rounded p-3 border">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Total Cost</div>
          <div className="text-xl font-semibold text-gray-900">
            ${card.metrics.costUSD.toFixed(2)}
          </div>
        </div>
      </div>

      {card.actions.length > 0 && (
        <div className="flex gap-2 pt-3 border-t border-gray-200">
          {card.actions.map((action) => (
            <ActionButton key={action.id} action={action} threadId="current" />
          ))}
        </div>
      )}
    </div>
  );
}
