"use client";
import { useState } from "react";
import { AUTONOMY, QUICK_ACTIONS, AUTONOMY_ICONS, AUTONOMY_COLORS, autonomyToAutopilot, type AutonomyLevel } from "@/lib/autonomy";

export function ChatComposer({
  onSend,
  onSmokeTest,
}: {
  onSend: (text: string, options?: any) => void;
  onSmokeTest?: () => void;
}) {
  const [text, setText] = useState("");
  const [autonomy, setAutonomy] = useState<AutonomyLevel>("L0");
  const [budget, setBudget] = useState<number | undefined>(undefined);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 flex-wrap">
        <label className="text-xs text-gray-600">Autonomy:</label>
        {(Object.keys(AUTONOMY) as AutonomyLevel[]).map((level) => (
          <button
            key={level}
            onClick={() => setAutonomy(level)}
            title={AUTONOMY[level].tooltip}
            aria-pressed={autonomy === level}
            aria-label={`${AUTONOMY[level].chip}: ${AUTONOMY[level].tooltip}`}
            className={`text-xs px-2 py-1 rounded border transition-colors ${
              autonomy === level
                ? AUTONOMY_COLORS[level]
                : "bg-white text-gray-700 hover:bg-gray-50 border-gray-300"
            }`}
          >
{AUTONOMY_ICONS[level]} {AUTONOMY[level].chip}
          </button>
        ))}
        <label htmlFor="budget-input" className="text-xs ml-3 text-gray-600">Daily Cap ($):</label>
        <input
          id="budget-input"
          type="number"
          min="0"
          max="10000"
          className="w-24 text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          placeholder="50"
          title="Daily budget limit in USD"
          value={budget ?? ""}
          onChange={(e) =>
            setBudget(e.target.value ? Number(e.target.value) : undefined)
          }
        />
        <div className="ml-auto flex gap-1">
          {Object.values(QUICK_ACTIONS).map((action) => (
            <button
              key={action.id}
              onClick={() => {
                if (action.id === "smoke_test") {
                  if (onSmokeTest) {
                    onSmokeTest();
                  } else {
                    const smokeTestGoal = "python developers with activity in the last 90 days";
                    onSend(smokeTestGoal, { autonomy: "L0", budget: 1 });
                  }
                } else if (action.id === "plan" || action.id === "simulate" || action.id === "drafts" || action.id === "alerts") {
                  setText((prev) => (prev ? prev + " " : "") + action.label.toLowerCase());
                } else {
                  // Handle guide and other actions
                  setText((prev) => (prev ? prev + " " : "") + action.label.toLowerCase());
                }
              }}
              className={`text-xs px-2 py-1 border rounded hover:bg-gray-50 transition-colors ${
                action.id === "smoke_test"
                  ? "bg-green-100 text-green-700 border-green-300 hover:bg-green-200"
                  : "border-gray-300"
              }`}
              title={action.tooltip}
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2">
        <div className="flex-1">
          <label htmlFor="message-input" className="sr-only">
            Message input
          </label>
          <textarea
            id="message-input"
            className="w-full border border-gray-300 rounded p-2 text-sm resize-none h-24 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder='e.g., "Find 2k Py maintainers active 90d, seq=123. Preflight then run."'
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                if (e.shiftKey) {
                  // Shift+Enter: Allow new line (default behavior)
                  return;
                } else {
                  // Enter: Send message
                  e.preventDefault();
                  if (text.trim()) {
                    onSend(text, { autonomy, budget });
                    setText("");
                  }
                }
              }
            }}
            aria-describedby="message-help"
          />
        </div>
        <button
          className="px-4 py-2 rounded bg-black text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
          onClick={() => {
            if (text.trim()) {
              onSend(text, { autonomy, budget });
              setText("");
            }
          }}
          disabled={!text.trim()}
          aria-label="Run job with specified goal and settings"
        >
          Run Job
        </button>
      </div>
      <div id="message-help" className="text-xs text-gray-500">
        <span>💡 Press Enter to send</span>
        <span className="mx-2">•</span>
        <span>Shift + Enter for new line</span>
      </div>
    </div>
  );
}
