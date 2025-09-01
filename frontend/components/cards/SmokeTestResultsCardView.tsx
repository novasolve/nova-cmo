"use client";
import { ActionButton } from "../ActionButton";
import { ActionButton as ActionButtonType } from "@/types";

export interface SmokeTestResultsCard {
  type: "smoke_test_results";
  status: "passed" | "failed" | "running";
  duration?: number;
  checks: Array<{
    id: string;
    name: string;
    required: boolean;
    passed: boolean;
    details?: string;
  }>;
  metrics: {
    eventsStreamed: number;
    cardsRendered: number;
    draftsCount: number;
    budgetUsed: number;
  };
  actions: ActionButtonType[];
}

export function SmokeTestResultsCardView({ card }: { card: SmokeTestResultsCard }) {
  const getStatusIcon = () => {
    switch (card.status) {
      case "passed":
        return "✅";
      case "failed":
        return "❌";
      case "running":
        return "🔄";
      default:
        return "⏳";
    }
  };

  const getStatusColor = () => {
    switch (card.status) {
      case "passed":
        return "border-green-200 bg-green-50";
      case "failed":
        return "border-red-200 bg-red-50";
      case "running":
        return "border-blue-200 bg-blue-50";
      default:
        return "border-gray-200 bg-gray-50";
    }
  };

  const passedChecks = card.checks.filter(c => c.passed).length;
  const requiredChecks = card.checks.filter(c => c.required).length;
  const passedRequired = card.checks.filter(c => c.required && c.passed).length;

  return (
    <div className={`border rounded-lg p-4 ${getStatusColor()}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          {getStatusIcon()}
          <span>Smoke Test Results</span>
        </h3>
        <div className="text-sm text-gray-600">
          {card.duration ? `${(card.duration / 1000).toFixed(1)}s` : "Running..."}
        </div>
      </div>

      {/* Status Summary */}
      <div className="mb-4 p-3 bg-white rounded border">
        <div className="text-sm font-medium mb-2">
          Status: <span className={`${
            card.status === "passed" ? "text-green-700" :
            card.status === "failed" ? "text-red-700" : "text-blue-700"
          }`}>
            {card.status.charAt(0).toUpperCase() + card.status.slice(1)}
          </span>
        </div>
        <div className="text-sm text-gray-600">
          Checks: {passedRequired}/{requiredChecks} required • {passedChecks}/{card.checks.length} total
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="bg-white rounded p-2 border text-center">
          <div className="text-lg font-semibold">{card.metrics.eventsStreamed}</div>
          <div className="text-xs text-gray-500">Events</div>
        </div>
        <div className="bg-white rounded p-2 border text-center">
          <div className="text-lg font-semibold">{card.metrics.cardsRendered}</div>
          <div className="text-xs text-gray-500">Cards</div>
        </div>
        <div className="bg-white rounded p-2 border text-center">
          <div className="text-lg font-semibold">{card.metrics.draftsCount}</div>
          <div className="text-xs text-gray-500">Drafts</div>
        </div>
        <div className="bg-white rounded p-2 border text-center">
          <div className="text-lg font-semibold">${card.metrics.budgetUsed.toFixed(2)}</div>
          <div className="text-xs text-gray-500">Budget</div>
        </div>
      </div>

      {/* Detailed Checks */}
      <div className="space-y-2 mb-4">
        <h4 className="text-sm font-medium text-gray-700">Detailed Checks:</h4>
        {card.checks.map((check) => (
          <div key={check.id} className="flex items-start gap-3 p-2 bg-white rounded border">
            <div className="flex-shrink-0 mt-0.5">
              {check.passed ? (
                <div className="w-4 h-4 bg-green-500 rounded-full flex items-center justify-center">
                  <div className="w-2 h-2 bg-white rounded-full" />
                </div>
              ) : (
                <div className={`w-4 h-4 rounded-full border-2 ${
                  check.required ? "border-red-500" : "border-gray-300"
                }`} />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{check.name}</span>
                {check.required && (
                  <span className="text-xs px-1.5 py-0.5 bg-orange-100 text-orange-700 rounded">
                    Required
                  </span>
                )}
              </div>
              {check.details && (
                <div className="text-xs text-gray-500 mt-1">{check.details}</div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Actions */}
      {card.actions.length > 0 && (
        <div className="flex gap-2 pt-3 border-t">
          {card.actions.map((action) => (
            <ActionButton key={action.id} action={action} threadId="current" />
          ))}
        </div>
      )}
    </div>
  );
}
