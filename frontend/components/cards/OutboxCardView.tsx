"use client";
import { OutboxCard } from "@/types";
import { ActionButton } from "./ActionButton";

export function OutboxCardView({ card }: { card: OutboxCard }) {
  return (
    <div className="border border-purple-200 rounded-lg p-4 bg-purple-50">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-purple-900">
          Outbox ({card.samples.length} samples)
        </h3>
        <span className="text-xs text-purple-600">Run: {card.runId}</span>
      </div>

      <div className="space-y-3 mb-4">
        {card.samples.map((sample, idx) => (
          <div key={sample.leadId} className="bg-white rounded-lg p-3 border border-purple-100">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{sample.email}</span>
                <span className="text-xs px-2 py-1 bg-gray-100 rounded">
                  Score: {sample.score}
                </span>
              </div>
              <div className="flex gap-1">
                <button className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200">
                  Approve
                </button>
                <button className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200">
                  Edit
                </button>
                <button className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200">
                  Skip
                </button>
              </div>
            </div>

            <div className="text-sm mb-2">
              <div className="font-medium text-gray-700">Subject:</div>
              <div className="text-gray-600">{sample.subject}</div>
            </div>

            <div className="text-sm mb-2">
              <div className="font-medium text-gray-700">Body:</div>
              <div className="text-gray-600 text-xs bg-gray-50 p-2 rounded max-h-20 overflow-y-auto">
                {sample.body}
              </div>
            </div>

            {sample.evidence.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-2">
                {sample.evidence.map((evidence, evidenceIdx) => (
                  <a
                    key={evidenceIdx}
                    href={evidence.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                  >
                    {evidence.label}
                  </a>
                ))}
              </div>
            )}

            {sample.policy.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {sample.policy.map((policy, policyIdx) => (
                  <span
                    key={policyIdx}
                    className={`text-xs px-2 py-1 rounded flex items-center gap-1 ${
                      policy.status === "ok"
                        ? "bg-green-100 text-green-700 border border-green-200"
                        : policy.status === "warn"
                        ? "bg-yellow-100 text-yellow-700 border border-yellow-200"
                        : "bg-red-100 text-red-700 border border-red-200"
                    }`}
                    title={policy.note || policy.rule}
                  >
                    <span className="text-xs">
                      {policy.status === "ok" ? "✓" : policy.status === "warn" ? "⚠️" : "✗"}
                    </span>
                    <span>{policy.rule}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {card.bulkActions.length > 0 && (
        <div className="flex gap-2 pt-3 border-t border-purple-200">
          {card.bulkActions.map((action) => (
            <ActionButton key={action.id} action={action} threadId="current" />
          ))}
        </div>
      )}
    </div>
  );
}
