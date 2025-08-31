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
        {[0, 1, 2, 3, 4].map((l) => (
          <button
            key={l}
            onClick={() => setAutopilot(l)}
            className={`text-xs px-2 py-1 rounded border ${
              autopilot === l ? "bg-black text-white" : "bg-white hover:bg-gray-50"
            }`}
          >
            L{l}
          </button>
        ))}
        <label className="text-xs ml-3 text-gray-600">Budget ($/day):</label>
        <input
          type="number"
          className="w-24 text-sm border border-gray-300 rounded px-2 py-1"
          placeholder="50"
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
        <textarea
          className="flex-1 border border-gray-300 rounded p-2 text-sm resize-none h-24 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          placeholder='e.g., "Find 2k Py maintainers active 90d, seq=123. Preflight then run."'
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              if (text.trim()) {
                onSend(text, { autopilot, budget });
                setText("");
              }
            }
          }}
        />
        <button
          className="px-4 py-2 rounded bg-black text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={() => {
            if (text.trim()) {
              onSend(text, { autopilot, budget });
              setText("");
            }
          }}
          disabled={!text.trim()}
        >
          Send
        </button>
      </div>
      <div className="text-xs text-gray-500">
        Tip: Press Cmd/Ctrl + Enter to send
      </div>
    </div>
  );
}
