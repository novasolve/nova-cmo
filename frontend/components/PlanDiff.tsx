"use client";
import React from "react";

export function PlanDiff({ requested, applied, drift }: { requested: any; applied: any; drift?: any }) {
  const keys = Array.from(new Set([...(Object.keys(requested||{})), ...(Object.keys(applied||{}))])).sort();
  return (
    <div className="rounded-2xl border p-4">
      <h3 className="font-semibold mb-2">Plan</h3>
      <table className="w-full text-sm">
        <thead><tr><th className="text-left">Param</th><th>Requested</th><th>Applied</th><th>Status</th></tr></thead>
        <tbody>
          {keys.map(k => {
            const r = requested?.[k]; const a = applied?.[k];
            const changed = JSON.stringify(r) !== JSON.stringify(a);
            const status = drift?.[k] ? "overridden (default)" : (changed ? "normalized" : "ok");
            return (
              <tr key={k} className={changed ? "text-amber-600" : ""}>
                <td className="py-1">{k}</td>
                <td className="py-1">{format(r)}</td>
                <td className="py-1">{format(a)}</td>
                <td className="py-1">{status}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function format(v: any) {
  if (v === undefined) return <span className="opacity-50">—</span>;
  if (typeof v === "object") return <code className="text-xs">{JSON.stringify(v)}</code>;
  return <code className="text-xs">{String(v)}</code>;
}


