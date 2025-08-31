"use client";
import { useState } from "react";

export function ChatComposer({
  onSend,
}: {
  onSend: (text: string, options?: any) => void;
}) {
  const [text, setText] = useState("");
  const [autopilot, setAutopilot] = useState(0);
  const [budget, setBudget] = useState<number | undefined>(undefined);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 flex-wrap">
        <label className="text-xs text-gray-600">Autopilot:</label>
        {[
          { level: 0, label: "L0", tooltip: "Manual: Review and approve all actions" },
          { level: 1, label: "L1", tooltip: "Stage-gated: Approve at key stages" },
          { level: 2, label: "L2", tooltip: "Budgeted: Run within hard caps" },
          { level: 3, label: "L3", tooltip: "Self-tuning: Adjust within policy" },
          { level: 4, label: "L4", tooltip: "Fully autonomous with reports" },
        ].map(({ level, label, tooltip }) => (
          <button
            key={level}
            onClick={() => setAutopilot(level)}
            title={tooltip}
            aria-pressed={autopilot === level}
            aria-label={`${label}: ${tooltip}`}
            className={`text-xs px-2 py-1 rounded border transition-colors ${
              autopilot === level
                ? "bg-black text-white border-black"
                : "bg-white text-gray-700 hover:bg-gray-50 border-gray-300"
            }`}
          >
            {label}
          </button>
        ))}
        <label htmlFor="budget-input" className="text-xs ml-3 text-gray-600">Budget ($/day):</label>
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
          {["Brief", "Preflight", "Outbox", "Errors"].map((t) => (
            <button
              key={t}
              onClick={() =>
                setText((prev) => (prev ? prev + " " : "") + t.toLowerCase())
              }
              className="text-xs px-2 py-1 border border-gray-300 rounded hover:bg-gray-50"
            >
              {t}
            </button>
          ))}
          <button
            onClick={() =>
              setText("demo all cards")
            }
            className="text-xs px-2 py-1 bg-blue-100 text-blue-700 border border-blue-300 rounded hover:bg-blue-200"
          >
            Demo
          </button>
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
              if (e.key === "Enter" && !e.shiftKey && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                if (text.trim()) {
                  onSend(text, { autopilot, budget });
                  setText("");
                }
              } else if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
                // Allow Enter for new line, but provide hint about Cmd+Enter
                // Don't prevent default - let user add new lines normally
              }
            }}
            aria-describedby="message-help"
          />
        </div>
        <button
          className="px-4 py-2 rounded bg-black text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          onClick={() => {
            if (text.trim()) {
              onSend(text, { autopilot, budget });
              setText("");
            }
          }}
          disabled={!text.trim()}
          aria-label="Send message"
        >
          Send
        </button>
      </div>
      <div id="message-help" className="text-xs text-gray-500">
        <span>💡 Press Cmd/Ctrl + Enter to send</span>
        <span className="mx-2">•</span>
        <span>Shift + Enter for new line</span>
      </div>
    </div>
  );
}
