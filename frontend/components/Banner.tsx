"use client";
import React from "react";

export function Banner(props: { repos: number; candidates: number; emails: number; elapsed_sec?: number }) {
  const { repos, candidates, emails, elapsed_sec } = props;
  return (
    <div className="w-full rounded-2xl border p-4 flex items-center justify-between text-sm">
      <span><b>{emails}</b> emails</span>
      <span><b>{candidates}</b> candidates</span>
      <span><b>{repos}</b> repos</span>
      {typeof elapsed_sec === "number" && <span>⏱ {elapsed_sec}s</span>}
    </div>
  );
}


