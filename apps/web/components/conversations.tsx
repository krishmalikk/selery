"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, MessageSquare, Plus, RefreshCw, Trash2 } from "lucide-react";
import { ApiError, formatPrice, formatTime, type ChartResponse, type Conversation, type ConversationDetail, type SeleryClient, type Settings, type Timeframe } from "@selery/shared";
import ResearchChart from "./chart";
import "./conversations.css";

const explain = (error: unknown) => error instanceof Error ? error.message : "The request could not be completed.";
const sourceLink = (value: string | null) => value && /^https?:\/\//i.test(value) ? value : undefined;
const ignoreSignal = () => {};

export default function Conversations({ api, suggestedSymbol, settings }: { api: SeleryClient; suggestedSymbol: string; settings: Settings | null }) {
  const [items, setItems] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [symbol, setSymbol] = useState(suggestedSymbol);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [timeframes, setTimeframes] = useState<Record<string, Timeframe>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [sending, setSending] = useState<Record<string, boolean>>({});
  const [more, setMore] = useState(false);
  const active = useRef<string | null>(null);
  const selection = useRef(0);
  const mounted = useRef(true);
  const locks = useRef(new Set<string>());
  const attempts = useRef<Record<string, { message: string; id: string; timeframe: Timeframe }>>({});
  const messages = useRef<HTMLDivElement>(null);
  const createLock = useRef(false);

  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const clearUnavailable = useCallback((failure: unknown, id?: string) => {
    if (!(failure instanceof ApiError) || ![401, 404].includes(failure.status)) return false;
    if (!mounted.current) return true;
    if (failure.status === 401) { setItems([]); setDrafts({}); attempts.current = {}; }
    else if (id) { setItems((all) => all.filter((item) => item.id !== id)); delete attempts.current[id]; }
    if (failure.status === 401 || active.current === id) {
      ++selection.current; active.current = null;
      setSelected(null); setDetail(null); setLoading(false);
      setError(explain(failure));
    }
    return true;
  }, []);
  const refreshList = useCallback(async () => {
    try {
      const result = await api.conversations();
      if (mounted.current) { setItems(result); setMore(result.length === 50); }
    } catch (failure) { if (!clearUnavailable(failure) && mounted.current) setError(explain(failure)); }
  }, [api, clearUnavailable]);
  useEffect(() => { void refreshList(); }, [refreshList]);
  useEffect(() => { if (messages.current) messages.current.scrollTop = messages.current.scrollHeight; }, [detail?.messages.length, selected?.id]);
  useEffect(() => {
    if (!selected || loading) return;
    const id = selected.id;
    let cancelled = false, fetching = false;
    async function poll() {
      if (cancelled || fetching || document.hidden || locks.current.has(id)) return;
      const version = selection.current;
      fetching = true;
      const valid = () => !cancelled && mounted.current && active.current === id && version === selection.current && !locks.current.has(id);
      try {
        const result = await api.conversation(id);
        if (!valid()) return;
        setDetail(result);
        setErrors((all) => all[id]?.startsWith("Conversation refresh failed:") ? { ...all, [id]: "" } : all);
        const attempt = attempts.current[id];
        const sent = attempt && result.messages.find((entry) => entry.id === `${id}:${attempt.id}`);
        if (sent?.status === "failed") delete attempts.current[id];
        if (attempt && sent?.status === "complete" && result.messages.some((entry) => entry.id === `${sent.id}:answer` && entry.status === "complete")) {
          delete attempts.current[id];
          setErrors((all) => ({ ...all, [id]: "" }));
          setDrafts((all) => all[id]?.trim() === attempt.message ? { ...all, [id]: "" } : all);
        }
      } catch (failure) {
        if (valid() && !clearUnavailable(failure, id)) setErrors((all) => ({ ...all, [id]: `Conversation refresh failed: ${explain(failure)}` }));
      } finally { fetching = false; }
    }
    const timer = window.setInterval(() => void poll(), 5000);
    const visible = () => { if (!document.hidden) void poll(); };
    document.addEventListener("visibilitychange", visible);
    return () => { cancelled = true; window.clearInterval(timer); document.removeEventListener("visibilitychange", visible); };
  }, [api, selected?.id, loading, clearUnavailable]);

  async function open(conversation: Conversation) {
    const version = ++selection.current;
    active.current = conversation.id;
    setSelected(conversation); setDetail(null); setLoading(true); setError("");
    try {
      const result = await api.conversation(conversation.id);
      if (mounted.current && version === selection.current) setDetail(result);
    } catch (failure) { if (mounted.current && version === selection.current && !clearUnavailable(failure, conversation.id)) setError(explain(failure)); }
    finally { if (mounted.current && version === selection.current) setLoading(false); }
  }

  function startNew() {
    ++selection.current; active.current = null;
    setSelected(null); setDetail(null); setLoading(false); setError("");
    setSymbol(suggestedSymbol);
  }

  async function create() {
    if (createLock.current) return;
    const ticker = symbol.trim().toUpperCase();
    if (!/^[A-Z][A-Z0-9.-]{0,11}$/.test(ticker)) { setError("Enter a stock symbol, such as SPY or AAPL."); return; }
    createLock.current = true; setCreating(true); setError("");
    const version = selection.current;
    try {
      const result = await api.createConversation(ticker);
      if (!mounted.current) return;
      setItems((all) => [result, ...all]);
      if (version === selection.current) await open(result);
    } catch (failure) { if (mounted.current) setError(explain(failure)); }
    finally { createLock.current = false; if (mounted.current) setCreating(false); }
  }

  async function send() {
    if (!selected || !detail || loading || detail.messages.some((entry) => entry.status === "pending")) return;
    const id = selected.id, message = (drafts[id] || "").trim();
    if (!message || locks.current.has(id)) return;
    locks.current.add(id); setSending((all) => ({ ...all, [id]: true }));
    setErrors((all) => ({ ...all, [id]: "" }));
    if (attempts.current[id]?.message !== message) attempts.current[id] = { message, id: crypto.randomUUID(), timeframe: timeframes[id] || "5m" };
    try {
      const result = await api.sendConversationMessage(id, message, attempts.current[id].id, attempts.current[id].timeframe);
      if (!mounted.current) return;
      if (active.current === id) { ++selection.current; setDetail(result); setLoading(false); }
      const pending = result.messages.some((entry) => entry.status === "pending");
      if (!pending) {
        delete attempts.current[id];
        setDrafts((all) => all[id]?.trim() === message ? { ...all, [id]: "" } : all);
      }
      await refreshList();
    } catch (failure) {
      if (!mounted.current) return;
      if (clearUnavailable(failure, id)) return;
      setErrors((all) => ({ ...all, [id]: explain(failure) }));
      try {
        const result = await api.conversation(id);
        if (!mounted.current) return;
        if (active.current === id) { ++selection.current; setDetail(result); setLoading(false); }
        const sent = result.messages.find((entry) => entry.id === `${id}:${attempts.current[id]?.id}`);
        if (sent?.status === "failed") delete attempts.current[id];
        if (sent?.status === "complete" && result.messages.some((entry) => entry.id === `${sent.id}:answer` && entry.status === "complete")) {
          delete attempts.current[id];
          setErrors((all) => ({ ...all, [id]: "" }));
          setDrafts((all) => all[id]?.trim() === message ? { ...all, [id]: "" } : all);
        }
      } catch (refreshFailure) { clearUnavailable(refreshFailure, id); /* Keep the draft and attempt id when delivery is uncertain. */ }
    } finally {
      locks.current.delete(id);
      if (mounted.current) setSending((all) => ({ ...all, [id]: false }));
    }
  }

  async function remove() {
    if (!selected || locks.current.has(selected.id)) return;
    const id = selected.id;
    try {
      await api.deleteConversation(id);
      if (!mounted.current) return;
      setItems((all) => all.filter((item) => item.id !== id));
      setDrafts((all) => { const next = { ...all }; delete next[id]; return next; });
      if (active.current === id) startNew();
    } catch (failure) { if (!clearUnavailable(failure, id) && mounted.current) setError(explain(failure)); }
  }

  const busy = !!(selected && sending[selected.id]);
  const pending = !!detail?.messages.some((entry) => entry.status === "pending");
  return <section className="conversations" aria-label="Stock conversations">
    <aside className="panel conversation-sidebar">
      <div className="section-title"><h2>Conversations</h2><button className="icon-button" aria-label="Refresh conversations" onClick={() => void refreshList()}><RefreshCw size={14} /></button></div>
      <button className="quiet-button conversation-new" onClick={startNew}><Plus size={14} />New conversation</button>
      <nav aria-label="Saved conversations">{items.map((item) => <button key={item.id} className={`conversation-item ${selected?.id === item.id ? "active" : ""}`} onClick={() => void open(item)} aria-current={selected?.id === item.id ? "page" : undefined}><strong>{item.symbol}</strong><span>{item.title}</span><small>{formatTime(item.updated_at)}</small></button>)}</nav>
      {!items.length && <p className="muted small padded">Your stock conversations will appear here.</p>}
      {more && <button className="quiet-button conversation-new" onClick={async () => {
        try { const page = await api.conversations(50, items.length); setItems((all) => [...all, ...page.filter((item) => !all.some((existing) => existing.id === item.id))]); setMore(page.length === 50); }
        catch (failure) { setError(explain(failure)); }
      }}>Load older conversations</button>}
    </aside>
    <div className="conversation-main">
      {error && <div className="notice" role="alert">{error}</div>}
      {!selected ? <section className="panel conversation-start">
        <MessageSquare size={30} /><span className="badge">READ-ONLY RESEARCH</span>
        <h2>A conversation, centered on a stock.</h2>
        <p>Choose a symbol to start. Its chart stays beside your conversation, and you can ask follow-up questions as you explore.</p>
        <form onSubmit={(event) => { event.preventDefault(); void create(); }}><label htmlFor="conversation-symbol">Stock symbol</label><input id="conversation-symbol" value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} placeholder="SPY" maxLength={12} autoComplete="off" required /><button className="primary" disabled={creating}>{creating ? "Creating…" : "Start conversation"}<ArrowUpRight size={15} /></button></form>
        <small className="muted">Choosing a stock does not request AI analysis. Messages are sent only when you press Send.</small>
      </section> : <div className="conversation-workspace">
        <ConversationChart key={selected.id} api={api} symbol={selected.symbol} timeframe={timeframes[selected.id] || "5m"} onTimeframe={(value) => setTimeframes((all) => ({ ...all, [selected.id]: value }))} />
        <section className="panel conversation-thread" aria-label={`${selected.symbol} conversation`}>
          <div className="section-title"><div><h2>{selected.symbol} conversation</h2><small className="muted">This conversation stays on {selected.symbol}.</small></div><button className="icon-button" aria-label="Delete conversation" disabled={busy} onClick={() => void remove()}><Trash2 size={15} /></button></div>
          <div className="conversation-messages" ref={messages} role="log" aria-label="Conversation messages" aria-live="polite">
            {loading ? <p className="muted">Loading conversation…</p> : detail?.messages.length ? detail.messages.map((entry) => <article key={entry.id} className={`conversation-message ${entry.role}`}>
              <header><strong>{entry.role === "user" ? "You" : "Selery"}</strong><small>{formatTime(entry.created_at)}{entry.mode ? ` · ${entry.mode === "llm" ? "AI" : "Local summary"}` : ""}</small></header>
              <p>{entry.message}</p>
              {entry.status !== "complete" && <p className="warning small">{entry.status === "failed" ? `Response failed: ${entry.error || "No answer was generated. You can resend your message."}` : "Response pending"}</p>}
              {entry.citations.map((citation, index) => <div className="citation" key={index}>{sourceLink(citation.url) ? <a href={sourceLink(citation.url)} target="_blank" rel="noreferrer">{citation.label}</a> : <span>{citation.label}</span>}<small>{formatTime(citation.timestamp)}{citation.data_id ? ` · ${citation.data_id}` : ""}</small></div>)}
            </article>) : <div className="empty"><MessageSquare size={25} /><p>Ask about {selected.symbol}, then keep the conversation going. Earlier messages provide context for your follow-ups.</p></div>}
            {busy && <p className="muted small" role="status">Reading {selected.symbol} evidence…</p>}
          </div>
          <form className="conversation-compose" onSubmit={(event) => { event.preventDefault(); void send(); }}>
            {errors[selected.id] && <div className="notice" role="alert">{errors[selected.id]} Your draft is preserved.</div>}
            <label htmlFor="conversation-message">Message about {selected.symbol}</label>
            <textarea id="conversation-message" value={drafts[selected.id] || ""} onChange={(event) => setDrafts((all) => ({ ...all, [selected.id]: event.target.value }))} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(); } }} maxLength={4000} disabled={loading || !detail} placeholder={`What would you like to understand about ${selected.symbol}?`} />
            <div className="conversation-send"><small className="muted">{pending ? "Waiting for the saved response…" : "Enter to send · Shift + Enter for a new line"}</small><button className="primary" disabled={busy || pending || loading || !detail || !(drafts[selected.id] || "").trim()}>{busy ? "Thinking…" : "Send"}<ArrowUpRight size={14} /></button></div>
            <small className="muted">{settings?.llm_enabled ? `LLM cap ${formatPrice(settings.llm_monthly_cap_usd)} / month` : "AI disabled · local summaries available"} · Recent conversation context is included; older messages remain readable.</small>
          </form>
        </section>
      </div>}
    </div>
  </section>;
}

function ConversationChart({ api, symbol, timeframe, onTimeframe }: { api: SeleryClient; symbol: string; timeframe: Timeframe; onTimeframe: (value: Timeframe) => void }) {
  const [data, setData] = useState<ChartResponse | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let cancelled = false, fetching = false;
    setData((current) => current?.symbol === symbol && current.timeframe === timeframe ? current : null);
    async function load() {
      if (fetching || document.visibilityState === "hidden") return;
      fetching = true;
      try {
        const chart = await api.chart(symbol, timeframe, "iex", 1000);
        if (chart.symbol !== symbol || chart.timeframe !== timeframe) throw new Error("Chart response did not match this conversation.");
        if (!cancelled) { setData(chart); setError(""); }
      } catch (failure) { if (!cancelled) setError(explain(failure)); }
      finally { fetching = false; }
    }
    void load(); const timer = window.setInterval(() => void load(), 30_000);
    const visible = () => { if (!document.hidden) void load(); };
    document.addEventListener("visibilitychange", visible);
    return () => { cancelled = true; window.clearInterval(timer); document.removeEventListener("visibilitychange", visible); };
  }, [api, symbol, timeframe, refresh]);
  return <section className="panel conversation-chart" aria-label={`${symbol} chart context`}>
    <div className="panel-heading"><div><h2>{symbol} chart</h2><span className="badge">IEX only</span>{data && <span className="muted small"> · {data.provenance.provider}</span>}</div><button className="icon-button" aria-label="Refresh conversation chart" onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={15} /></button></div>
    <div className="chart-toolbar"><div className="segmented">{(["5m", "1h", "1D"] as Timeframe[]).map((value) => <button key={value} aria-pressed={timeframe === value} className={timeframe === value ? "active" : ""} onClick={() => onTimeframe(value)}>{value}</button>)}</div><button disabled>VWAP <span className="warning">needs SIP data</span></button>{data?.provenance.synthetic && <span className="badge warning">FIXTURE DATA</span>}</div>
    {error && <div className="notice" role="status">{error}{data ? " Showing stale chart from the last successful refresh." : " Chart unavailable; you can still use the conversation."}</div>}
    {data ? <><ResearchChart data={data} replay={0} onSignal={ignoreSignal} /><div className="chart-meta"><span className={data.provenance.stale || error ? "warning" : ""}>{data.provenance.stale || error ? "Stale · " : ""}Observed {formatTime(data.provenance.observed_at)}<br />Retrieved {formatTime(data.provenance.retrieved_at)}</span><span>Refreshes every 30 seconds while visible.<br /><a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">Charts by TradingView</a></span></div></> : <div className="chart-loading">{error ? "No chart data available" : `Loading ${symbol} chart…`}</div>}
    <p className="muted small conversation-chart-note">New messages use this stock and chart interval. Answers cite their dated backend evidence; they do not see your cursor or chart position.</p>
  </section>;
}
