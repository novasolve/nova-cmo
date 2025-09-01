"use client";
import { PolicyDiffCard } from "@/types";
import { ActionButton } from "./ActionButton";

export function PolicyDiffCardView({ card }: { card: PolicyDiffCard }) {
  return (
    <div className="border border-orange-200 rounded-lg p-4 bg-orange-50">
      <h3 className="font-semibold text-orange-900 mb-3">
        Policy Changes ({card.changes.length} modifications)
      </h3>

      <div className="space-y-3 mb-4">
        {card.changes.map((change, idx) => (
          <div key={idx} className="bg-white rounded-lg p-3 border border-orange-100">
            <div className="text-sm font-medium text-gray-700 mb-2">
              {change.field}
            </div>

            <div className="grid grid-cols-2 gap-3 mb-2">
              <div>
                <div className="text-xs text-gray-500 mb-1">Before:</div>
                <div className="text-sm bg-red-50 border border-red-200 rounded p-2 font-mono">
                  {change.oldValue}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">After:</div>
                <div className="text-sm bg-green-50 border border-green-200 rounded p-2 font-mono">
                  {change.newValue}
                </div>
              </div>
            </div>

            <div className="text-xs text-orange-700 bg-orange-100 rounded p-2">
              <strong>Impact:</strong> {change.impact}
            </div>
          </div>
        ))}
      </div>

      {card.actions.length > 0 && (
        <div className="flex gap-2 pt-3 border-t border-orange-200">
          {card.actions.map((action) => (
            <ActionButton key={action.id} action={action} threadId="current" />
          ))}
        </div>
      )}
    </div>
  );
}
