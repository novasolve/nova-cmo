"use client";
import { ErrorGroupCard } from "@/types";
import { ActionButton } from "./ActionButton";

export function ErrorGroupCardView({ card }: { card: ErrorGroupCard }) {
  return (
    <div className="border border-red-200 rounded-lg p-4 bg-red-50">
      <h3 className="font-semibold text-red-900 mb-3">
        Error Group ({card.errors.length} types)
      </h3>

      <div className="space-y-3 mb-4">
        {card.errors.map((error) => (
          <div key={error.id} className="bg-white rounded-lg p-3 border border-red-100">
            <div className="flex items-start justify-between mb-2">
              <div className="flex-1">
                <div className="text-sm font-medium text-red-900 mb-1">
                  {error.message}
                </div>
                <div className="text-xs text-gray-500">
                  Node: <code className="bg-gray-100 px-1 rounded">{error.node}</code>
                </div>
              </div>
              <div className="flex flex-col items-end text-xs text-gray-500">
                <span className="bg-red-100 text-red-700 px-2 py-1 rounded">
                  {error.count}x
                </span>
                <span className="mt-1">
                  {new Date(error.lastSeen).toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {card.actions.length > 0 && (
        <div className="flex gap-2 pt-3 border-t border-red-200">
          {card.actions.map((action) => (
            <ActionButton key={action.id} action={action} threadId="current" />
          ))}
        </div>
      )}
    </div>
  );
}
