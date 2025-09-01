"use client";
import React, { useEffect, useMemo, useState } from "react";

export function CopyEmails({ emailsPlaceholderLink, emails }: { emailsPlaceholderLink?: string; emails?: string[] }) {
  const [copied, setCopied] = useState(false);
  const [list, setList] = useState<string[]>(emails || []);

  useEffect(() => {
    if (!emailsPlaceholderLink || list.length > 0) return;
    (async () => {
      try {
        const r = await fetch(emailsPlaceholderLink, { cache: "no-store" });
        if (!r.ok) return;
        const text = await r.text();
        const rows = text.split(/\r?\n/).filter(Boolean);
        const values = rows.map(line => line.split(",")[0]).filter(Boolean);
        setList(Array.from(new Set(values)));
      } catch {}
    })();
  }, [emailsPlaceholderLink]);

  const text = useMemo(() => (list || []).join(", "), [list]);

  return (
    <div className="rounded-2xl border p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold">Copy-paste emails</h3>
        <button
          className="px-3 py-1 rounded-xl border"
          onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(()=>setCopied(false), 1500); }}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <textarea className="w-full h-24 bg-transparent border rounded-xl p-2 text-sm" value={text} readOnly />
    </div>
  );
}


