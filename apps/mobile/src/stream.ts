import { useEffect, useState } from "react";
import { StreamEventSchema, type StreamEvent } from "@selery/shared";
import { useSession } from "./session";
export function useStream(onEvent: (event: StreamEvent) => void) {
  const { client, authenticated } = useSession();
  const [status, setStatus] = useState("Connecting");
  useEffect(() => {
    if (!authenticated) return;
    let stopped = false,
      attempt = 0,
      socket: WebSocket | undefined,
      timer: ReturnType<typeof setTimeout> | undefined;
    const retry = () => {
      if (stopped) return;
      setStatus("Reconnecting · last-known data");
      timer = setTimeout(connect, Math.min(30000, 1000 * 2 ** attempt++));
    };
    async function connect() {
      try {
        const { ticket } = await client.streamTicket();
        if (stopped) return;
        socket = new WebSocket(
          `${client.baseUrl.replace(/^http/, "ws")}/api/v1/stream?ticket=${encodeURIComponent(ticket)}`,
        );
        socket.onopen = () => {
          attempt = 0;
          setStatus("Connected");
        };
        socket.onmessage = (event) => {
          try {
            onEvent(StreamEventSchema.parse(JSON.parse(event.data)));
          } catch {
            setStatus("Unrecognized update · pull to refresh");
          }
        };
        socket.onclose = retry;
        socket.onerror = () => socket?.close();
      } catch {
        retry();
      }
    }
    void connect();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, [client, authenticated, onEvent]);
  return status;
}
