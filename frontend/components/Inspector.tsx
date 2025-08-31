"use client";
import { useState } from "react";
import { AUTONOMY, AUTONOMY_ICONS, AUTONOMY_COLORS } from "@/lib/autonomy";

export function Inspector() {
  const [activeTab, setActiveTab] = useState<"runstate" | "graph" | "metrics" | "events">("runstate");



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
                  <code className="text-xs bg-gray-100 px-1 rounded">No active job</code>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Progress:</span>
                  <span className="text-gray-900">Waiting for job</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Autonomy:</span>
                  <span className="text-xs px-2 py-1 bg-gray-100 text-gray-800 rounded">
                    🤝 Co-pilot
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Status:</span>
                  <span className="text-xs px-2 py-1 bg-gray-100 text-gray-800 rounded">
                    idle
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg border p-3">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Daily Cap</h4>
              <div className="space-y-2">
                <div className="text-sm text-gray-900 font-medium">
                  Used $0.00 of $50.00 (0%)
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `0%` }}
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
                  <div className="font-semibold">0/0</div>
                </div>
                <div>
                  <div className="text-gray-500">Avg Latency</div>
                  <div className="font-semibold">-</div>
                </div>
                <div>
                  <div className="text-gray-500">Total Cost</div>
                  <div className="font-semibold">$0.00</div>
                </div>
                <div>
                  <div className="text-gray-500">Error Rate</div>
                  <div className="font-semibold">0.0%</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "events" && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700">Live Events</h4>
            <div className="bg-white rounded border p-3 text-xs text-center text-gray-500">
              No events yet. Start a job to see live updates.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
