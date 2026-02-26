import { useState, useEffect, useRef, useCallback } from "react";
import { getWsUrl } from "../lib/api";

interface UseWebSocketReturn {
  lastMessage: unknown | null;
  sendMessage: (data: unknown) => void;
  isConnected: boolean;
}

export function useWebSocket(token: string | null): UseWebSocketReturn {
  const [lastMessage, setLastMessage] = useState<unknown | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectDelay = useRef(1000);

  const cleanup = useCallback(() => {
    if (heartbeatInterval.current) {
      clearInterval(heartbeatInterval.current);
      heartbeatInterval.current = null;
    }
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!token) return;

    const url = getWsUrl();
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      // Send auth as first message
      ws.send(JSON.stringify({ type: "auth", token }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "auth_ok") {
          setIsConnected(true);
          reconnectDelay.current = 1000; // Reset backoff

          // Start heartbeat
          heartbeatInterval.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "ping" }));
            }
          }, 30000);
        } else if (data.type === "error" && data.message?.includes("auth")) {
          // Auth failed — don't reconnect
          cleanup();
          return;
        } else if (data.type !== "pong") {
          setLastMessage(data);
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (heartbeatInterval.current) {
        clearInterval(heartbeatInterval.current);
        heartbeatInterval.current = null;
      }

      // Exponential backoff reconnect
      const delay = Math.min(reconnectDelay.current, 30000);
      reconnectTimeout.current = setTimeout(() => {
        reconnectDelay.current = delay * 2;
        connect();
      }, delay);
    };

    ws.onerror = () => {
      // onclose will handle reconnect
    };
  }, [token, cleanup]);

  useEffect(() => {
    connect();
    return cleanup;
  }, [connect, cleanup]);

  const sendMessage = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { lastMessage, sendMessage, isConnected };
}
