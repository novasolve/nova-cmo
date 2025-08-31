"use client";
import { useState } from "react";
import { AUTONOMY, AUTONOMY_ICONS, AUTONOMY_COLORS } from "@/lib/autonomy";

export function Inspector() {
  const [activeTab, setActiveTab] = useState<"runstate" | "graph" | "metrics" | "events">("runstate");

  const mockRunState = {
    currentNode: "enrich_github_user",
    progress: "Processing lead 147/2100",
    autonomyLevel: "L1" as const,
    budget: { used: 23.45, limit: 50, currency: "USD" },
    status: "running"
  };

  const mockEvents = [
    { id: "1", timestamp: "14:32:15", node: "enrich_github_user", status: "ok", latency: 234, cost: 0.0023 },
    { id: "2", timestamp: "14:32:12", node: "validate_email", status: "ok", latency: 45, cost: 0.0001 },
    { id: "3", timestamp: "14:32:10", node: "fetch_profile", status: "retry", latency: 1205, cost: 0.0045 },
    { id: "4", timestamp: "14:32:05", node: "parse_repo_data", status: "ok", latency: 156, cost: 0.0012 },
  ];

  const mockMetrics = {
    totalNodes: 12,
    completedNodes: 8,
    avgLatency: 342,
    totalCost: 1.23,
    errorRate: 0.02
  };

  return (
    <div className="h-full flex flex-col">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Run Monitor</h2>
        
        <div className="grid grid-cols-2 gap-1 bg-gray-100 rounded-lg p-1 text-xs">
          <button
            onClick={() => setActiveTab("runstate")}
            className={`px-2 py-1.5 rounded ${
              activeTab === "runstate"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            RunState
          </button>
          <button
            onClick={() => setActiveTab("graph")}
            className={`px-2 py-1.5 rounded ${
              activeTab === "graph"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            Graph
          </button>
          <button
            onClick={() => setActiveTab("metrics")}
            className={`px-2 py-1.5 rounded ${
              activeTab === "metrics"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            Metrics
          </button>
          <button
            onClick={() => setActiveTab("events")}
            className={`px-2 py-1.5 rounded ${
              activeTab === "events"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            Events
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {activeTab === "runstate" && (
          <div className="space-y-4">
            <div className="bg-white rounded-lg border p-3">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Current Status</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Node:</span>
                  <code className="text-xs bg-gray-100 px-1 rounded">{mockRunState.currentNode}</code>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Progress:</span>
                  <span className="text-gray-900">{mockRunState.progress}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Autonomy:</span>
                  <span className={`text-xs px-2 py-1 rounded ${AUTONOMY_COLORS[mockRunState.autonomyLevel]}`}>
                    {AUTONOMY_ICONS[mockRunState.autonomyLevel]} {AUTONOMY[mockRunState.autonomyLevel].chip}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Status:</span>
                  <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded">
                    {mockRunState.status}
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg border p-3">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Daily Cap</h4>
              <div className="space-y-2">
                <div className="text-sm text-gray-900 font-medium">
                  Used ${mockRunState.budget.used} of ${mockRunState.budget.limit} ({((mockRunState.budget.used / mockRunState.budget.limit) * 100).toFixed(0)}%)
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${(mockRunState.budget.used / mockRunState.budget.limit) * 100}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "graph" && (
          <div className="bg-white rounded-lg border p-3">
            <div className="text-center text-gray-500 py-8">
              <div className="text-sm mb-2">Graph View</div>
              <div className="text-xs">Interactive LangGraph visualization would appear here</div>
              <div className="mt-4 text-xs bg-gray-100 rounded p-2">
                React Flow component integration needed
              </div>
            </div>
          </div>
        )}

        {activeTab === "metrics" && (
          <div className="space-y-3">
            <div className="bg-white rounded-lg border p-3">
              <h4 className="text-sm font-medium text-gray-700 mb-3">Performance</h4>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <div className="text-gray-500">Nodes</div>
                  <div className="font-semibold">{mockMetrics.completedNodes}/{mockMetrics.totalNodes}</div>
                </div>
                <div>
                  <div className="text-gray-500">Avg Latency</div>
                  <div className="font-semibold">{mockMetrics.avgLatency}ms</div>
                </div>
                <div>
                  <div className="text-gray-500">Total Cost</div>
                  <div className="font-semibold">${mockMetrics.totalCost}</div>
                </div>
                <div>
                  <div className="text-gray-500">Error Rate</div>
                  <div className="font-semibold">{(mockMetrics.errorRate * 100).toFixed(1)}%</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "events" && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700">Live Events</h4>
            {mockEvents.map((event) => (
              <div key={event.id} className="bg-white rounded border p-2 text-xs">
                <div className="flex items-center justify-between mb-1">
                  <code className="text-gray-600">{event.node}</code>
                  <span className="text-gray-400">{event.timestamp}</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        event.status === "ok"
                          ? "bg-green-500"
                          : event.status === "retry"
                          ? "bg-yellow-500"
                          : "bg-red-500"
                      }`}
                    />
                    <span className="text-gray-600">{event.status}</span>
                  </div>
                  <div className="text-gray-500">
                    {event.latency}ms • ${event.cost.toFixed(4)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
