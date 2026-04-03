import { useEffect, useRef, useState } from "react";

export type BackendConnectionStatus = "connecting" | "connected" | "disconnected";

export type BackendWebSocketMessage = {
  type: string;
  data?: unknown;
  timestamp?: string;
};

type UseBackendWebSocketOptions = {
  enabled: boolean;
  url: string;
  onMessage?: (message: BackendWebSocketMessage) => void;
};

export function useBackendWebSocket({ enabled, url, onMessage }: UseBackendWebSocketOptions): BackendConnectionStatus {
  const [status, setStatus] = useState<BackendConnectionStatus>(enabled ? "connecting" : "disconnected");
  const onMessageRef = useRef(onMessage);
  const reconnectTimerRef = useRef<number | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);

  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!enabled || !url) {
      setStatus("disconnected");
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      return;
    }

    let cancelled = false;

    const connect = () => {
      if (cancelled) return;

      setStatus("connecting");
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.addEventListener("open", () => {
        reconnectAttemptRef.current = 0;
        setStatus("connected");
      });

      socket.addEventListener("message", (event) => {
        try {
          const parsed = JSON.parse(event.data) as BackendWebSocketMessage;
          onMessageRef.current?.(parsed);
        } catch {
          // Ignore malformed websocket messages.
        }
      });

      socket.addEventListener("close", () => {
        if (cancelled) return;
        setStatus("disconnected");
        const delay = Math.min(5000, 1000 * 2 ** reconnectAttemptRef.current);
        reconnectAttemptRef.current += 1;
        reconnectTimerRef.current = window.setTimeout(connect, delay);
      });

      socket.addEventListener("error", () => {
        socket.close();
      });
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [enabled, url]);

  return status;
}
