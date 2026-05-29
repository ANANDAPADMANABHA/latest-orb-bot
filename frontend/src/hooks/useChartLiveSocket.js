import { useCallback, useEffect, useRef, useState } from 'react';

function wsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/ws/charts/`;
}

const RECONNECT_BASE_MS = 5000;
const RECONNECT_MAX_MS = 60000;

/**
 * Angel One SmartAPI WebSocket v2 ticks relayed from Django (/ws/charts/).
 * Reconnects with backoff when tab is visible again or stream drops.
 */
export default function useChartLiveSocket(enabled) {
  const [ticks, setTicks] = useState({});
  const [status, setStatus] = useState('idle');
  const [statusDetail, setStatusDetail] = useState('');
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const reconnectAttemptRef = useRef(0);
  const mountedRef = useRef(false);
  const connectRef = useRef(null);

  const clearReconnectTimer = () => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  };

  const scheduleReconnect = useCallback(() => {
    if (!enabled || !mountedRef.current) return;
    clearReconnectTimer();
    reconnectAttemptRef.current += 1;
    const delay = Math.min(
      RECONNECT_BASE_MS * reconnectAttemptRef.current,
      RECONNECT_MAX_MS,
    );
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      if (mountedRef.current && wsRef.current?.readyState !== WebSocket.OPEN) {
        connectRef.current?.();
      }
    }, delay);
  }, [enabled]);

  const connect = useCallback(() => {
    if (!enabled || !mountedRef.current) return;

    if (wsRef.current) {
      const state = wsRef.current.readyState;
      if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
        return;
      }
      try {
        wsRef.current.close();
      } catch {
        /* ignore */
      }
      wsRef.current = null;
    }

    setStatus('connecting');
    setStatusDetail('');
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptRef.current = 0;
      setStatus((prev) => (prev === 'live' ? 'live' : 'connected'));
    };
    ws.onclose = () => {
      wsRef.current = null;
      setStatus('disconnected');
      scheduleReconnect();
    };
    ws.onerror = () => {
      setStatus('error');
      setStatusDetail('Browser WebSocket error');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'status') {
          setStatus(msg.message || 'status');
          setStatusDetail(msg.detail || '');
          if (msg.message === 'live') {
            reconnectAttemptRef.current = 0;
          }
          if (msg.message === 'reconnecting') {
            clearReconnectTimer();
          }
          return;
        }
        if (msg.type === 'tick' && msg.symbol) {
          setStatus('live');
          setStatusDetail('');
          setTicks((prev) => ({
            ...prev,
            [msg.symbol]: {
              ltp: msg.ltp,
              bar: msg.bar,
            },
          }));
        }
      } catch {
        /* ignore malformed */
      }
    };
  }, [enabled, scheduleReconnect]);

  connectRef.current = connect;

  useEffect(() => {
    if (!enabled) return undefined;

    mountedRef.current = true;
    connect();

    const onVisibility = () => {
      if (document.visibilityState !== 'visible') return;
      if (wsRef.current?.readyState === WebSocket.OPEN) return;
      clearReconnectTimer();
      reconnectTimerRef.current = setTimeout(() => connectRef.current?.(), 800);
    };

    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      mountedRef.current = false;
      document.removeEventListener('visibilitychange', onVisibility);
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [enabled, connect]);

  return { ticks, status, statusDetail };
}
