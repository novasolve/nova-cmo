"use client";
import { useState } from "react";
import { AUTONOMY, AUTONOMY_ICONS, AUTONOMY_COLORS } from "@/lib/autonomy";
import { useJobState } from "@/lib/jobContext";

export function Inspector() {
  const [activeTab, setActiveTab] = useState<"runstate" | "graph" | "metrics" | "events">("runstate");
  const { jobState } = useJobState();



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
                  <code className="text-xs bg-gray-100 px-1 rounded">{jobState.currentNode}</code>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Progress:</span>
                  <span className="text-gray-900">{jobState.progress}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Autonomy:</span>
                  <span className={`text-xs px-2 py-1 rounded ${AUTONOMY_COLORS[jobState.autonomyLevel]}`}>
                    {AUTONOMY_ICONS[jobState.autonomyLevel]} {AUTONOMY[jobState.autonomyLevel].chip}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Status:</span>
                  <span className={`text-xs px-2 py-1 rounded ${
                    jobState.status === 'running' ? 'bg-blue-100 text-blue-800' :
                    jobState.status === 'completed' ? 'bg-green-100 text-green-800' :
                    jobState.status === 'failed' ? 'bg-red-100 text-red-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {jobState.status}
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg border p-3">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Daily Cap</h4>
              <div className="space-y-2">
                <div className="text-sm text-gray-900 font-medium">
                  Used ${jobState.budget.used.toFixed(2)} of ${jobState.budget.total.toFixed(2)} ({((jobState.budget.used / jobState.budget.total) * 100).toFixed(1)}%)
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${Math.min((jobState.budget.used / jobState.budget.total) * 100, 100)}%` }}
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
                  <div className="font-semibold">{jobState.metrics.nodesCompleted}/{jobState.metrics.totalNodes || jobState.metrics.nodesCompleted}</div>
                </div>
                <div>
                  <div className="text-gray-500">Avg Latency</div>
                  <div className="font-semibold">{jobState.metrics.avgLatency > 0 ? `${jobState.metrics.avgLatency.toFixed(0)}ms` : '-'}</div>
                </div>
                <div>
                  <div className="text-gray-500">Total Cost</div>
                  <div className="font-semibold">${jobState.metrics.totalCost.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-gray-500">Error Rate</div>
                  <div className="font-semibold">{jobState.metrics.errorRate.toFixed(1)}%</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "events" && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700">Live Events</h4>
            {jobState.events.length === 0 ? (
              <div className="bg-white rounded border p-3 text-xs text-center text-gray-500">
                No events yet. Start a job to see live updates.
              </div>
            ) : (
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {jobState.events.slice(-10).map((event, idx) => (
                  <div key={idx} className="bg-white rounded border p-2 text-xs">
                    <div className="flex justify-between items-start mb-1">
                      <span className="font-medium text-gray-700">{event.node}</span>
                      <span className={`px-1.5 py-0.5 rounded text-xs ${
                        event.status === 'ok' ? 'bg-green-100 text-green-700' :
                        event.status === 'error' ? 'bg-red-100 text-red-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {event.status}
                      </span>
                    </div>
                    {event.msg && (
                      <div className="text-gray-600 text-xs">{event.msg}</div>
                    )}
                    {(event.latencyMs || event.costUSD) && (
                      <div className="flex gap-2 mt-1 text-xs text-gray-500">
                        {event.latencyMs && <span>{event.latencyMs}ms</span>}
                        {event.costUSD && <span>${event.costUSD.toFixed(3)}</span>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
