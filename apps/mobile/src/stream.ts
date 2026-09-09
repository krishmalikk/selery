import { useEffect, useState } from "react";
import type { StreamEvent } from "@selery/shared";
import {
  connectResearchStream,
  type StreamSocket,
} from "@selery/shared/src/stream";
import { useSession } from "./session";
export function useStream(onEvent: (event: StreamEvent) => void) {
  const { client, authenticated } = useSession();
  const [status, setStatus] = useState("Connecting");
  useEffect(() => {
    if (!authenticated) return;
    const connection = connectResearchStream({
      baseUrl: client.baseUrl,
      ticket: () => client.streamTicket(),
      socket: (url) => new WebSocket(url) as unknown as StreamSocket,
      onEvent,
      onStatus: (value) =>
        setStatus(
          value === "connected"
            ? "Connected"
            : value === "reconnecting"
              ? "Reconnecting · last-known data"
              : value === "closed"
                ? "Disconnected"
                : "Connecting",
        ),
      onInvalidEvent: () => setStatus("Unrecognized update · pull to refresh"),
    });
    return () => connection.stop();
  }, [client, authenticated, onEvent]);
  return status;
}
