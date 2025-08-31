import { useEffect, useRef, useState } from "react";

export interface SSEHookOptions<T> {
  onEvent?: (event: T) => void;
  onConnectionChange?: (status: 'connecting' | 'connected' | 'disconnected' | 'error') => void;
}

export function useSSE<T = any>(url: string | null, options?: SSEHookOptions<T>) {
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');
  // Start with a slightly higher initial backoff to avoid hammering
  const retryRef = useRef(2000);
  const retryCountRef = useRef(0);
  const maxRetries = 10;
  const { onEvent, onConnectionChange } = options || {};
  const onEventRef = useRef<typeof onEvent>(onEvent);
  const onConnectionChangeRef = useRef<typeof onConnectionChange>(onConnectionChange);

  // Keep latest callbacks without forcing reconnection
  useEffect(() => { onEventRef.current = onEvent; }, [onEvent]);
  useEffect(() => { onConnectionChangeRef.current = onConnectionChange; }, [onConnectionChange]);

  const updateConnectionStatus = (status: typeof connectionStatus) => {
    setConnectionStatus(status);
    onConnectionChangeRef.current?.(status);
  };

  useEffect(() => {
    // Don't connect if no URL provided
    if (!url) {
      updateConnectionStatus('disconnected');
      return;
    }

    let cancelled = false;
    let es: EventSource | null = null;
    let isIntentionalClose = false;

    // Reset retry state when URL changes
    retryCountRef.current = 0;
    retryRef.current = 2000;

    const connect = () => {
      if (cancelled || !url) return;

      console.log(`[SSE] connecting`, { url });
      updateConnectionStatus('connecting');
      es = new EventSource(url, { withCredentials: true });

      es.onopen = () => {
        if (cancelled) return;
        console.log(`[SSE] connected`, { url });
        updateConnectionStatus('connected');
        // Reset retry delay and count on successful connection
        retryRef.current = 1000;
        retryCountRef.current = 0;
      };

      es.onmessage = (e) => {
        if (cancelled) return;
        try {
          const event = JSON.parse(e.data) as T;
          onEventRef.current?.(event);
        } catch (error) {
          const snippet = typeof e.data === 'string' ? e.data.slice(0, 200) : '';
          console.warn('[SSE] failed to parse event', { url, error, snippet });
        }
      };

      es.onerror = (e: Event) => {
        const eventSource = e.target as EventSource;
        const readyState = (eventSource && typeof eventSource.readyState === 'number') ? eventSource.readyState : undefined;
        const targetUrl = (eventSource as any)?.url || url;
        console.warn('[SSE] error', { url: targetUrl, readyState, retryCount: retryCountRef.current });

        // Check if this was a 404 (no job found) - don't retry in this case
        if (eventSource.readyState === EventSource.CLOSED && targetUrl && String(targetUrl).includes('/events')) {
          if (retryCountRef.current === 0) {
            console.log('[SSE] connection closed immediately - likely no active job for this thread');
            isIntentionalClose = true;
          }
        }

        es?.close();
        if (cancelled || isIntentionalClose) return;

        retryCountRef.current += 1;

        if (retryCountRef.current >= maxRetries) {
          console.warn('[SSE] max retries reached, stopping', { url: targetUrl, maxRetries });
          updateConnectionStatus('error');
          return;
        }

        // Add jitter to avoid thundering herd on multiple tabs
        const baseDelay = Math.min(retryRef.current, 30000); // Cap at 30 seconds
        const jitter = Math.floor(Math.random() * 400); // 0-400ms jitter
        const retryDelay = baseDelay + jitter;
        console.log('[SSE] will retry', { attempt: retryCountRef.current, of: maxRetries, inMs: retryDelay });
        updateConnectionStatus('error');

        setTimeout(() => {
          if (!cancelled && !isIntentionalClose) {
            connect();
          }
        }, retryDelay);
        retryRef.current = Math.min(retryRef.current * 2, 30000);
      };
    };

    connect();

    return () => {
      cancelled = true;
      isIntentionalClose = true;
      es?.close();
      updateConnectionStatus('disconnected');
    };
  }, [url]);

  return { connectionStatus };
}
