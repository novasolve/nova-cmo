"use client";
import React from "react";

export function RerunCTA({ defaults, onRerun }: { defaults?: Record<string, any>, onRerun: (overrides: Record<string,any>) => void }) {
  const preset = { ...(defaults||{}), fork: false, archived: false, per_page: 100, shards: "on" };
  return (
    <button
      className="mt-2 px-4 py-2 rounded-2xl border"
      onClick={() => onRerun(preset)}
      title="Rerun with safe, deterministic settings"
    >
      Rerun (fork:false, archived:false, per_page=100, shards:on)
    </button>
  );
}


