import { useEffect } from "react";

type Summary = {
  duration_ms: number;
  repos: number;
  candidates: number;
  leads_with_emails: number;
};
type Artifact = { kind: string; filename: string; bytes: number; url: string };

export function useJobStream(
  jobId: string | null,
  handlers: {
    onProgress?: (evt: any) => void;
    onFinalized?: (status: string, summary: Summary | null, artifacts: Artifact[]) => void;
    onStreamEnd?: () => void;
  }
) {
  useEffect(() => {
    if (!jobId) return;
    const es = new EventSource(`/api/jobs/${jobId}/events`);

    const finalSync = async () => {
      try {
        const r = await fetch(`/api/jobs/${jobId}/summary`, { cache: "no-store" });
        if (r.ok) {
          const { status, summary, artifacts } = await r.json();
          handlers.onFinalized?.(status, summary, artifacts);
        }
      } catch {}
    };

    const handleFinalized = (e: MessageEvent) => {
      try {
        const evt = JSON.parse(e.data);
        handlers.onFinalized?.(evt.status, evt.summary ?? null, evt.artifacts ?? []);
      } finally {
        // Also sync snapshot to defeat ordering races
        finalSync();
      }
    };

    const handleProgress = (e: MessageEvent) => {
      try {
        const evt = JSON.parse(e.data);
        handlers.onProgress?.(evt);
      } catch {}
    };

    es.addEventListener("progress", handleProgress as EventListener);
    es.addEventListener("job_finalized", handleFinalized as EventListener);
    es.addEventListener("job_failed", handleFinalized as EventListener);
    es.addEventListener("job_cancelled", handleFinalized as EventListener);

    // Detect close via error callback
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        handlers.onStreamEnd?.();
        finalSync();
      }
    };

    return () => {
      try { es.close(); } catch {}
    };
  }, [jobId]);
}
