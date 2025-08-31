import { useEffect, useRef, useState, useCallback } from "react";

export interface SSEHookOptions<T> {
  onEvent?: (event: T) => void;
  onConnectionChange?: (status: 'connecting' | 'connected' | 'disconnected' | 'error') => void;
}

export function useSSE<T = any>(url: string | null, options?: SSEHookOptions<T>) {
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting');
  const retryRef = useRef(1000);
  const retryCountRef = useRef(0);
  const maxRetries = 10;
  const { onEvent, onConnectionChange } = options || {};

  const updateConnectionStatus = useCallback((status: typeof connectionStatus) => {
    setConnectionStatus(status);
    onConnectionChange?.(status);
  }, [onConnectionChange]);

  useEffect(() => {
    // Don't connect if no URL provided
    if (!url) {
      updateConnectionStatus('disconnected');
      return;
    }

    let cancelled = false;
    let es: EventSource | null = null;
    
    // Reset retry state when URL changes
    retryCountRef.current = 0;
    retryRef.current = 1000;

    const connect = () => {
      if (cancelled || !url) return;
      
      console.log(`SSE connecting to: ${url}`);
      updateConnectionStatus('connecting');
      es = new EventSource(url, { withCredentials: true });
      
      es.onopen = () => {
        if (cancelled) return;
        console.log(`SSE connected to: ${url}`);
        updateConnectionStatus('connected');
        // Reset retry delay and count on successful connection
        retryRef.current = 1000;
        retryCountRef.current = 0;
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
        
        retryCountRef.current += 1;
        
        if (retryCountRef.current >= maxRetries) {
          console.warn(`SSE max retries (${maxRetries}) reached for ${url}. Stopping reconnection attempts.`);
          updateConnectionStatus('error');
          return;
        }
        
        const retryDelay = Math.min(retryRef.current, 30000); // Cap at 30 seconds
        console.log(`SSE connection failed. Retry ${retryCountRef.current}/${maxRetries} in ${retryDelay}ms`);
        updateConnectionStatus('error');
        
        setTimeout(() => {
          if (!cancelled) {
            connect();
          }
        }, retryDelay);
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
