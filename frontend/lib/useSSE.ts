import { useEffect, useRef, useState, useCallback } from "react";

export interface SSEHookOptions<T> {
  onEvent?: (event: T) => void;
  onConnectionChange?: (status: 'connecting' | 'connected' | 'disconnected' | 'error') => void;
}

export function useSSE<T = any>(url: string, options?: SSEHookOptions<T>) {
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');
  const retryRef = useRef(1000);
  const { onEvent, onConnectionChange } = options || {};

  const updateConnectionStatus = useCallback((status: typeof connectionStatus) => {
    setConnectionStatus(status);
    onConnectionChange?.(status);
  }, [onConnectionChange]);

  useEffect(() => {
    let cancelled = false;
    let es: EventSource | null = null;

    const connect = () => {
      if (cancelled) return;
      
      console.log(`SSE connecting to: ${url}`);
      updateConnectionStatus('connecting');
      es = new EventSource(url, { withCredentials: true });
      
      es.onopen = () => {
        if (cancelled) return;
        updateConnectionStatus('connected');
        // Reset retry delay on successful connection
        retryRef.current = 1000;
      };
      
      es.onmessage = (e) => {
        if (cancelled) return;
        try {
          const event = JSON.parse(e.data) as T;
          onEvent?.(event);
        } catch (error) {
          console.warn('Failed to parse SSE event:', error);
        }
      };
      
      es.onerror = () => {
        es?.close();
        if (cancelled) return;
        
        updateConnectionStatus('error');
        setTimeout(() => {
          if (!cancelled) {
            connect();
          }
        }, Math.min(retryRef.current, 15000));
        retryRef.current *= 2;
      };
    };
    
    connect();
    
    return () => {
      cancelled = true;
      es?.close();
      updateConnectionStatus('disconnected');
    };
  }, [url, onEvent, updateConnectionStatus]);

  return { connectionStatus };
}
