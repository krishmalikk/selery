"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ExternalLink, RefreshCw, Search } from "lucide-react";
import { feedLabel, type SeleryClient, type PublicSource, type PublicTraderPage, type PublicActivityPage, type PublicActivityDetail, type ChatResponse } from "@selery/shared";
import ResearchChart from "./chart";
import styles from "./public-traders.module.css";

const names = { etoro: "eToro", kinfo: "Kinfo", afterhour: "AfterHour" };
const time = (value: string | null) => value ? new Date(value).toLocaleString() : "Unavailable";
const humanize = (value: string) => value.replaceAll("_", " ");
const sourcePrice = (value: number) => new Intl.NumberFormat("en-US", { maximumFractionDigits: 6 }).format(value);
const errorText = (error: unknown) => error instanceof Error ? error.message : "Public activity could not be loaded.";
const noSignal = () => {};
const noIndicators: readonly string[] = [];

function SourceLink({ href, children }: { href: string | null; children: React.ReactNode }) {
  // Defense in depth: the backend produces source links; never render an active non-HTTPS link.
  if (!href?.startsWith("https://")) return <span>{children} · link unavailable</span>;
  return <a href={href} target="_blank" rel="noopener noreferrer">{children} <ExternalLink size={12} /></a>;
}

function Pager({ total, offset, limit, busy, onPage }: { total: number; offset: number; limit: number; busy: boolean; onPage: (n: number) => void }) {
  return <div className={styles.pager}>
    <span>{total ? `${offset + 1}–${Math.min(offset + limit, total)} of ${total}` : "0 results"}</span>
    <button className="quiet-button" disabled={busy || offset === 0} onClick={() => onPage(Math.max(0, offset - limit))}>Previous page</button>
    <button className="quiet-button" disabled={busy || offset + limit >= total} onClick={() => onPage(offset + limit)}>Next page</button>
  </div>;
}

export default function PublicTraders({ api }: { api: SeleryClient }) {
  const [sources, setSources] = useState<PublicSource[]>([]);
  const [tab, setTab] = useState<"directory" | "activity">("directory");
  const [source, setSource] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [traderId, setTraderId] = useState("");
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [readTick, setReadTick] = useState(0);
  const [visible, setVisible] = useState(true);
  const [traders, setTraders] = useState<PublicTraderPage | null>(null);
  const [activity, setActivity] = useState<PublicActivityPage | null>(null);
  const [busy, setBusy] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<PublicActivityDetail | null>(null);
  const [detailError, setDetailError] = useState("");
  const [question, setQuestion] = useState("What does this public activity show, and what remains unknown?");
  const [answer, setAnswer] = useState<ChatResponse | null>(null);
  const [asking, setAsking] = useState(false);
  const detailSequence = useRef(0);
  const listSequence = useRef(0);
  const detailRequest = useRef(0);
  const detailValue = useRef<PublicActivityDetail | null>(null);
  const detailKey = useRef("");
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    const visibility = () => {
      const showing = document.visibilityState !== "hidden";
      setVisible(showing);
      if (showing) { setReadTick(n => n + 1); return; }
      listSequence.current++; detailRequest.current++; detailSequence.current++;
      detailValue.current = null;
      setSources([]); setTraders(null); setActivity(null); setDetail(null); setAnswer(null);
      setAsking(false); setError(""); setDetailError(""); setNotice("");
    };
    visibility();
    document.addEventListener("visibilitychange", visibility);
    const timer = window.setInterval(() => {
      if (document.visibilityState !== "hidden") setReadTick(n => n + 1);
    }, 60_000);
    return () => {
      mounted.current = false; listSequence.current++; detailRequest.current++; detailSequence.current++;
      document.removeEventListener("visibilitychange", visibility); window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const sequence = ++listSequence.current;
    const current = () => mounted.current && sequence === listSequence.current;
    if (!visible) return;
    setBusy(true); setError(""); setTraders(null); setActivity(null);
    const filters: Record<string, string | number> = { limit: 12, offset };
    if (source) filters.source = source;
    if (query) filters.q = query;
    if (tab === "activity" && traderId) filters.trader_id = traderId;
    if (tab === "activity" && dateFrom) filters.date_from = dateFrom;
    if (tab === "activity" && dateTo) filters.date_to = dateTo;
    Promise.all([api.publicSources(), tab === "directory" ? api.publicTraders(filters) : api.publicActivity(filters)])
      .then(([statuses, page]) => {
        if (!current()) return;
        setSources(statuses);
        if (tab === "directory") setTraders(page as PublicTraderPage);
        else setActivity(page as PublicActivityPage);
      })
      .catch(e => { if (current()) setError(errorText(e)); })
      .finally(() => { if (current()) setBusy(false); });
    return () => { listSequence.current++; };
  }, [api, tab, source, query, traderId, dateFrom, dateTo, offset, revision, readTick, visible]);

  useEffect(() => {
    const request = ++detailRequest.current;
    if (!visible) return;
    const previous = detailValue.current;
    if (!selectedId || previous?.activity.id !== selectedId) {
      detailSequence.current++; detailValue.current = null;
      setDetail(null); setDetailError(""); setAnswer(null); setAsking(false);
    }
    if (!selectedId) return;
    const key = `${selectedId}:${revision}`;
    const snapshotOnly = previous?.activity.id === selectedId && detailKey.current === key;
    detailKey.current = key;
    // Periodic checks only inspect stored access/revisions; no chart/provider request.
    const pending = snapshotOnly
      ? api.publicActivityDetail(selectedId, false)
      : api.publicActivityDetail(selectedId);
    pending.then(result => {
      if (request !== detailRequest.current || !mounted.current) return;
      const old = detailValue.current;
      const unchanged = old?.activity.id === result.activity.id
        && old.activity.revision === result.activity.revision
        && old.llm_allowed === result.llm_allowed && result.trader.access === "public";
      if (!unchanged) { detailSequence.current++; setAnswer(null); setAsking(false); }
      const retainedChart = old?.chart ? { ...old.chart, provenance: { ...old.chart.provenance, stale: old.chart.provenance.stale || Date.now() - Date.parse(old.chart.provenance.available_at) > 120_000 } } : null;
      const next = snapshotOnly && unchanged && old
        ? { ...result, chart: retainedChart, market_context_reason: old.market_context_reason, reference_move_percent: old.reference_move_percent }
        : result;
      detailValue.current = next; setDetail(next); setDetailError("");
    }).catch(e => {
      if (request !== detailRequest.current || !mounted.current) return;
      detailSequence.current++; detailValue.current = null;
      setDetail(null); setAnswer(null); setAsking(false); setDetailError(errorText(e));
    });
    return () => { detailRequest.current++; };
  }, [api, selectedId, revision, readTick, visible]);

  const closeDetail = () => { detailSequence.current++; detailRequest.current++; detailValue.current = null; setSelectedId(""); setDetail(null); setAnswer(null); setAsking(false); };
  const changeTab = (value: "directory" | "activity") => { setTab(value); setOffset(0); setTraderId(""); closeDetail(); };
  const submitSearch = (event: FormEvent) => { event.preventDefault(); setQuery(search.trim()); setOffset(0); closeDetail(); };
  const refresh = async (id: string | null = null) => {
    setRefreshing(true); setError(""); setNotice("");
    try {
      const result = await api.refreshPublicTraders(id);
      if (mounted.current && document.visibilityState !== "hidden") { setNotice(result.message); setRevision(n => n + 1); }
    } catch (e) { if (mounted.current && document.visibilityState !== "hidden") setError(errorText(e)); }
    finally { if (mounted.current) setRefreshing(false); }
  };
  const ask = async (event: FormEvent) => {
    event.preventDefault();
    if (!detail || !question.trim() || asking) return;
    const sequence = detailSequence.current;
    setAsking(true); setAnswer(null); setDetailError("");
    try {
      const result = await api.chat({ message: question.trim(), symbol: detail.activity.symbol || "SPY", debate: false, activity_id: detail.activity.id });
      if (sequence === detailSequence.current) setAnswer(result);
    } catch (e) { if (sequence === detailSequence.current) setDetailError(errorText(e)); }
    finally { if (sequence === detailSequence.current) setAsking(false); }
  };
  const page = tab === "directory" ? traders : activity;

  return <section className={styles.root} aria-label="Public traders research">
    <div className="notice">Public activity is a dated third-party observation. A missing record does not prove a sale. Trader motives and unavailable exits remain unknown.</div>
    <div className={styles.sources} aria-label="Public source availability">
      {sources.map(item => <article key={item.id} className={`panel ${styles.source}`}>
        <div className={styles.row}><h2>{item.name}</h2><span className={`badge ${item.status === "verified" ? "" : "warning"}`}>{item.status === "fixtures" ? "Synthetic fixtures" : item.status}</span></div>
        <p>{item.reason}</p>
        <small>Last checked: {time(item.last_checked_at)}</small>
      </article>)}
    </div>
    <div className={styles.toolbar}>
      <div className={styles.tabs} aria-label="Public research view">
        <button className="quiet-button" aria-pressed={tab === "directory"} onClick={() => changeTab("directory")}>Trader directory</button>
        <button className="quiet-button" aria-pressed={tab === "activity"} onClick={() => changeTab("activity")}>Public activity</button>
      </div>
      <button className="quiet-button" disabled={refreshing || !sources.some(item => item.can_refresh)} onClick={() => void refresh()}><RefreshCw size={13} /> {refreshing ? "Refreshing…" : "Load / refresh directory page"}</button>
    </div>
    <form className={styles.filters} onSubmit={submitSearch}>
      <label>Source<select aria-label="Source" value={source} onChange={e => { setSource(e.target.value); setOffset(0); setTraderId(""); closeDetail(); }}><option value="">All sources</option>{Object.entries(names).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
      <label className={styles.search}>{tab === "directory" ? "Search public traders" : "Search public activity"}<input value={search} onChange={e => setSearch(e.target.value)} placeholder={tab === "directory" ? "Name or username" : "Symbol or instrument"} maxLength={100} /></label>
      {tab === "activity" && <><label>Opened from (UTC)<input type="date" value={dateFrom} max={dateTo || undefined} onChange={e => { setDateFrom(e.target.value); setOffset(0); closeDetail(); }} /></label><label>Opened through (UTC)<input type="date" value={dateTo} min={dateFrom || undefined} onChange={e => { setDateTo(e.target.value); setOffset(0); closeDetail(); }} /></label></>}
      <button className="quiet-button" type="submit"><Search size={13} /> Search</button>
    </form>
    {traderId && <div className={styles.row}><span className="muted">Activity for the selected source-specific trader</span><button className="quiet-button" onClick={() => { setTraderId(""); setOffset(0); closeDetail(); }}>Show all traders</button></div>}
    {notice && <p className="success" role="status">{notice}</p>}
    {error && <p className="notice" role="alert">{error}</p>}
    {busy && <p role="status" className="muted">Loading public research…</p>}
    {!busy && !error && !page?.items.length && <div className="empty"><p>No public records match these filters. Pending sources require authorized access; a subscription alone does not establish data rights.</p></div>}
    <div className={styles.directory}>
      {traders?.items.map(trader => <article className={`panel ${styles.trader}`} key={trader.id}>
        <div className={styles.row}><span className="badge">{names[trader.source]}</span><div className={styles.badges}>{trader.synthetic && <span className="badge warning">Synthetic</span>}{trader.stale && <span className="badge warning">Stale</span>}{trader.access === "unavailable" && <span className="badge warning">Access unavailable</span>}</div></div>
        <h2>{trader.display_name}</h2><p className="muted">@{trader.username}</p>
        <small>Observed: {time(trader.observed_at)}</small>
        <details><summary>{names[trader.source]} statistics</summary><p className="muted">{trader.statistics_note}</p>{Object.keys(trader.statistics).length ? <dl className={styles.metrics}>{Object.entries(trader.statistics).map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{String(value)}</dd></div>)}</dl> : <p className="muted">Unavailable</p>}</details>
        <div className={styles.actions}><SourceLink href={trader.source_url}>Source profile</SourceLink><button className="quiet-button" onClick={() => { setTraderId(trader.id); setTab("activity"); setQuery(""); setSearch(""); setOffset(0); closeDetail(); }}>View activity</button></div>
        <button className="quiet-button" disabled={refreshing || !sources.find(item => item.id === trader.source)?.can_refresh} onClick={() => void refresh(trader.id)}>Refresh this trader</button>
      </article>)}
    </div>
    {activity && activity.items.length > 0 && <div className={`panel ${styles.tableWrap}`}><table><thead><tr><th>Instrument / source</th><th>Public record</th><th>Entry reference</th><th>Observed</th><th>Details</th></tr></thead><tbody>{activity.items.map(item => <tr key={item.id}>
      <td><strong>{item.symbol || item.instrument_name}</strong><small>{names[item.source]} · {humanize(item.instrument_kind)}</small></td>
      <td>{humanize(item.status)}<small>{item.direction} · {item.verification}</small><div className={styles.badges}>{item.synthetic && <span className="badge warning">Synthetic</span>}{item.stale && <span className="badge warning">Stale</span>}{item.instrument_kind === "unclassified" && <span className="badge warning">Unclassified</span>}</div></td>
      <td className="mono">{item.entry_price === null ? "Unavailable" : sourcePrice(item.entry_price)}</td><td>{time(item.observed_at)}</td>
      <td><button className="quiet-button" onClick={() => { if (item.id !== selectedId) { detailSequence.current++; setSelectedId(item.id); } }}>View record</button></td>
    </tr>)}</tbody></table></div>}
    {page && <Pager total={page.total} limit={page.limit} offset={page.offset} busy={busy} onPage={n => { setOffset(n); closeDetail(); }} />}
    {selectedId && <section className={`panel ${styles.detail}`} aria-label="Public activity detail">
      <div className={styles.row}><h2>Public activity detail</h2><button className="quiet-button" onClick={closeDetail}>Close detail</button></div>
      {!detail && !detailError && <p role="status">Loading source record…</p>}
      {detailError && <p className="notice" role="alert">{detailError}</p>}
      {detail && <>
        <h3>{detail.activity.symbol || detail.activity.instrument_name} · {detail.trader.display_name}</h3>
        <div className={styles.badges}><span className="badge">{names[detail.activity.source]}</span><span className={`badge ${detail.activity.instrument_kind === "unclassified" ? "warning" : ""}`}>{humanize(detail.activity.instrument_kind)}</span><span className="badge">{humanize(detail.activity.status)}</span>{detail.activity.synthetic && <span className="badge warning">Synthetic fixture</span>}{detail.activity.stale && <span className="badge warning">Stale observation</span>}</div>
        <dl className={styles.metrics}>
          <div><dt>Source entry price</dt><dd>{detail.activity.entry_price === null ? "Unavailable" : sourcePrice(detail.activity.entry_price)}</dd></div>
          <div><dt>Direction</dt><dd>{detail.activity.direction}</dd></div>
          <div><dt>Source quantity</dt><dd>{detail.activity.quantity ?? "Unavailable"}</dd></div>
          <div><dt>Source allocation</dt><dd>{detail.activity.allocation_percent === null ? "Unavailable" : `${detail.activity.allocation_percent}%`}</dd></div>
          <div><dt>Source opening time</dt><dd>{time(detail.activity.opened_at)}</dd></div>
          <div><dt>Publication time</dt><dd>{time(detail.activity.published_at)}</dd></div>
          <div><dt>Provider updated</dt><dd>{time(detail.activity.provider_updated_at)}</dd></div>
          <div><dt>First observed by SELERY</dt><dd>{time(detail.activity.first_observed_at)}</dd></div>
          <div><dt>Latest SELERY observation</dt><dd>{time(detail.activity.observed_at)}</dd></div>
          <div><dt>Source exit price</dt><dd>{detail.activity.exit_price === null ? "Unavailable; no exit inferred" : sourcePrice(detail.activity.exit_price)}</dd></div>
        </dl>
        <p className="muted">{detail.activity.verification} · Revision {detail.activity.revision}. Source price currency is not supplied; no currency is assumed.</p>
        <SourceLink href={detail.activity.source_url}>Original source record</SourceLink>
        {detail.activity.limitations.map((item, index) => <p key={index} className="notice">{item}</p>)}
        <h3 className={styles.chartTitle}>Dated market context</h3>
        <p className="muted">{detail.market_context_reason}</p>
        {detail.reference_move_percent !== null && <p>Underlying reference-price change: {detail.reference_move_percent.toFixed(2)}%. This is not the trader’s return.</p>}
        {detail.chart && <><div className="chart-meta"><span>{detail.chart.symbol} · {detail.chart.timeframe} · {feedLabel(detail.chart.provenance.feed)}{detail.chart.provenance.stale ? " · Stale" : ""}{detail.chart.provenance.synthetic ? " · Synthetic" : ""}</span><span>Observed {time(detail.chart.provenance.observed_at)} · {detail.chart.bars.length ? `${time(new Date(detail.chart.bars[0].time * 1000).toISOString())} – ${time(new Date(detail.chart.bars[detail.chart.bars.length - 1].time * 1000).toISOString())}` : "No bars available"}</span></div><ResearchChart data={detail.chart} onSignal={noSignal} replay={0} indicators={noIndicators} /><a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer">Charts by TradingView</a></>}
        <form onSubmit={ask} className={styles.chat}>
          <h3>Ask about this trade</h3>
          {!detail.llm_allowed && <p className="notice">This source is not approved for LLM analysis. Questions receive local evidence only; source data will not be sent to OpenAI.</p>}
          <label>Question about this public record<textarea value={question} onChange={e => setQuestion(e.target.value)} maxLength={4000} rows={3} required /></label>
          <button className="primary" type="submit" disabled={asking || !question.trim()}>{asking ? "Reviewing evidence…" : "Ask about this trade"}</button>
        </form>
        {answer && <div className="answer" aria-live="polite"><span className="badge">{answer.mode === "llm" ? "AI research explanation" : "Local evidence"}</span><p>{answer.message}</p>{answer.citations.map((citation, index) => <div className="citation" key={`${citation.data_id}-${index}`}><SourceLink href={citation.url}>{citation.label}</SourceLink><small>{time(citation.timestamp)}</small></div>)}</div>}
      </>}
    </section>}
  </section>;
}
