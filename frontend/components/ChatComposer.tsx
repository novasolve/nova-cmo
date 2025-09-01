"use client";
import { useState } from "react";
import { AUTONOMY, AUTONOMY_ICONS, AUTONOMY_COLORS, type AutonomyLevel } from "@/lib/autonomy";

export function ChatComposer({
  onSend,
  onSmokeTest,
}: {
  onSend: (text: string, options?: any) => void;
  onSmokeTest?: () => void;
}) {
  const [text, setText] = useState("");
  const [autonomy, setAutonomy] = useState<AutonomyLevel>("L2");
  const [budget, setBudget] = useState<number | undefined>(undefined);

  // YAML-driven smoke test config (mirrors cmo_agent/config/smoke_prompt.yaml)
  const SMOKE_YAML = `## YAML-driven smoke test config (no typed GOAL required)
##
## How to run:
## - From repo root:
##     make run-config CONFIG=cmo_agent/config/smoke_prompt.yaml
##     make dry-run    CONFIG=cmo_agent/config/smoke_prompt.yaml
## - Inline overrides (no file edits needed):
##     make run-config CONFIG=cmo_agent/config/smoke_prompt.yaml SET="language=Go target_leads=50"
##     make dry-run    CONFIG=cmo_agent/config/smoke_prompt.yaml SET="stars_range=500..5000 activity_days=60"
##
## Notes:
## - pushed_since auto-computes to today - activity_days when null
## - No goal string is required. If goal_template is omitted, a friendly
##   display-only line is synthesized from params for logs/UI.

version: 1

# Parameters used to render the smoke-test prompt and display plan
params:
  language: "Python"
  stars_range: "300..2000"
  activity_days: 90
  target_leads: 20
  budget_per_day: 10

# If provided, overrides computed pushed_since; otherwise computed as today - activity_days
pushed_since: null # e.g., "2025-06-01"

## Optional: You may still provide a goal_template to control the display line
## goal_template: |
##   Find maintainers of {{language}} repos stars:{{stars_range}} pushed:>={{pushed_since}}; prioritize active {{activity_days}} days; export CSV.`;

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
        <button
          className="text-xs px-3 py-1.5 rounded border bg-white text-gray-700 hover:bg-gray-50 border-gray-300"
          onClick={() => {
            // Prefer callback if provided; otherwise reuse onSend to go through the same /api/chat path
            if (onSmokeTest) {
              onSmokeTest();
            } else {
              onSend(SMOKE_YAML, { autonomy, budget });
            }
          }}
          aria-label="Run built-in self-test using smoke YAML"
          title="Run built-in self-test using smoke YAML"
        >
          🧪 Self‑Test
        </button>
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
