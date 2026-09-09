import { StreamEventSchema, type StreamEvent } from './contracts';

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'closed';
export interface StreamSocket {
  onopen: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onerror: (() => void) | null;
  onclose: (() => void) | null;
  close(): void;
}
export type StreamOptions = {
  baseUrl: string;
  ticket: () => Promise<{ ticket: string }>;
  socket: (url: string) => StreamSocket;
  onEvent: (event: StreamEvent) => void;
  onStatus?: (status: ConnectionStatus) => void;
  onInvalidEvent?: () => void;
  schedule?: (callback: () => void, milliseconds: number) => unknown;
  cancel?: (handle: unknown) => void;
};
/** One reconnect policy for browser and native adapters. Tickets are refreshed per connection. */
export function connectResearchStream(options: StreamOptions): { stop: () => void } {
  let stopped = false;
  let attempt = 0;
  let socket: StreamSocket | null = null;
  let scheduled: unknown;
  let generation = 0;
  const schedule = options.schedule ?? ((callback, delay) => setTimeout(callback, delay));
  const cancel = options.cancel ?? ((handle) => clearTimeout(handle as ReturnType<typeof setTimeout>));
  const update = (status: ConnectionStatus) => options.onStatus?.(status);
  const reconnect = () => {
    if (stopped || scheduled !== undefined) return;
    update('reconnecting');
    scheduled = schedule(() => { scheduled = undefined; void connect(); }, Math.min(30_000, 1000 * 2 ** Math.min(attempt++, 5)));
  };
  const connect = async () => {
    if (stopped) return;
    const current = ++generation;
    try {
      const result = await options.ticket();
      if (stopped || current !== generation) return;
      const url = options.baseUrl.replace(/^http/, 'ws').replace(/\/$/, '');
      socket = options.socket(`${url}/api/v1/stream?ticket=${encodeURIComponent(result.ticket)}`);
      const active = socket;
      active.onopen = () => { if (!stopped && active === socket) { attempt = 0; update('connected'); } };
      active.onmessage = (event) => {
        if (stopped || active !== socket) return;
        const parsed = (() => { try { return StreamEventSchema.safeParse(JSON.parse(event.data)); } catch { return null; } })();
        if (parsed?.success) options.onEvent(parsed.data); else options.onInvalidEvent?.();
      };
      active.onclose = () => { if (active === socket) reconnect(); };
      active.onerror = () => { if (active === socket) { active.close(); reconnect(); } };
    } catch { if (!stopped && current === generation) reconnect(); }
  };
  update('connecting');
  void connect();
  return { stop() {
    if (stopped) return;
    stopped = true;
    generation++;
    if (scheduled !== undefined) cancel(scheduled);
    if (socket) { socket.onopen = null; socket.onclose = null; socket.onmessage = null; socket.onerror = null; socket.close(); }
    update('closed');
  } };
}
