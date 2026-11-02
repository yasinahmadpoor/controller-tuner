import { useEffect, useState } from "react";

import { jobEventsUrl } from "../api/client";

export function useJobEvents(jobId: string | undefined, enabled = true) {
  const [progress, setProgress] = useState<Record<string, unknown> | null>(null);
  const [fallback, setFallback] = useState(false);
  const [terminal, setTerminal] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId || !enabled) {
      return;
    }
    if (typeof EventSource === "undefined") {
      setFallback(true);
      return;
    }
    const source = new EventSource(jobEventsUrl(jobId));
    const onProgress = (event: MessageEvent<string>) => {
      try {
        setProgress(JSON.parse(event.data) as Record<string, unknown>);
      } catch {
        // Ignore malformed events; polling remains authoritative.
      }
    };
    const onDone = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as { status?: string };
        setTerminal(payload.status ?? "done");
      } catch {
        setTerminal("done");
      }
      source.close();
    };
    source.addEventListener("progress", onProgress as EventListener);
    source.addEventListener("done", onDone as EventListener);
    source.onerror = () => {
      setFallback(true);
      source.close();
    };
    return () => {
      source.removeEventListener("progress", onProgress as EventListener);
      source.removeEventListener("done", onDone as EventListener);
      source.close();
    };
  }, [enabled, jobId]);

  return { progress, fallback, terminal };
}
