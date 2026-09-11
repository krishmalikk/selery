"use client";
import {
  useState,
  useEffect,
  useCallback,
  useRef,
  type FormEvent,
} from "react";
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  ChartNoAxesCombined,
  ChevronRight,
  Command,
  FlaskConical,
  Leaf,
  LogOut,
  MessageSquare,
  Search,
  Settings as SettingsIcon,
  ShieldCheck,
  SlidersHorizontal,
  Bell,
  WifiOff,
  RefreshCw,
  PanelLeftClose,
  ExternalLink,
  Users,
} from "lucide-react";
import {
  SeleryClient,
  ApiError,
  disclaimer,
  feedLabel,
  formatPrice,
  formatPercent,
  formatTime,
  signalConfidence,
  WatchlistResponseSchema,
  ChartResponseSchema,
  NewsResponseSchema,
  type Quote,
  type ChartResponse,
  type NewsItem,
  type Signal,
  type Settings,
  type PasskeyStatus,
  type Timeframe,
  type ResearchReport,
  type StrategyInfo,
  type JournalEntry,
  type SizingResponse,
  type OutcomeSummary,
  type Alert,
} from "@selery/shared";
import { encodeCache, parseCache } from "@selery/shared/src/cache";
import {
  connectResearchStream,
  type StreamSocket,
} from "@selery/shared/src/stream";
import {
  chartIndicatorGroups,
  defaultChartIndicators,
} from "@selery/shared/src/chart";
import ResearchChart from "./chart";
import ReportChart from "./report-chart";
import ReportLibrary from "./report-library";
import PublicTraders from "./public-traders";
import Conversations, { type SignalConversation } from "./conversations";
import {PasskeySettings} from "./passkey-settings";
import {signInWithPasskey, supportsPasskeys} from "./passkeys";
const api = new SeleryClient("");
const views = [
  "Overview",
  "Research",
  "Traders",
  "Outcomes",
  "Journal",
  "Sizing",
  "Alerts",
  "Assistant",
  "Settings",
] as const;
type View = (typeof views)[number];
const icons = [
  ChartNoAxesCombined,
  FlaskConical,
  Users,
  Activity,
  BookOpen,
  SlidersHorizontal,
  Bell,
  MessageSquare,
  SettingsIcon,
];
const errorText = (e: unknown) =>
  e instanceof Error ? e.message : "Something went wrong";
const saveCache = (key: string, data: unknown) => {
  try {
    localStorage.setItem(`selery:${key}`, encodeCache(data));
  } catch {}
};
const readCache = <T,>(
  key: string,
  schema: { parse: (value: unknown) => T },
) => {
  try {
    return parseCache(localStorage.getItem(`selery:${key}`), schema);
  } catch {
    return null;
  }
};
function Badge({
  children,
  warn = false,
}: {
  children: React.ReactNode;
  warn?: boolean;
}) {
  return <span className={`badge ${warn ? "warning" : ""}`}>{children}</span>;
}
function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="empty">
      <Leaf size={24} />
      <p>{children}</p>
    </div>
  );
}
function Notice({ children }: { children: React.ReactNode }) {
  return <div className="notice">{children}</div>;
}
export default function Workspace() {
  const [authenticated, setAuthenticated] = useState(false),
    [booting, setBooting] = useState(true),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [passkeyStatus, setPasskeyStatus] = useState<PasskeyStatus | null>(null);
  const [passkeySupported, setPasskeySupported] = useState(false);
  const [passwordFallback, setPasswordFallback] = useState(false);
  const refreshPasskeys = useCallback(() => {
    void api.passkeyStatus().then(setPasskeyStatus).catch(() => setPasskeyStatus(null));
  }, []);
  useEffect(() => {setPasskeySupported(supportsPasskeys());refreshPasskeys();}, [refreshPasskeys]);
  const [view, setView] = useState<View>("Overview"),
    [symbol, setSymbol] = useState("SPY"),
    [timeframe, setTimeframe] = useState<Timeframe>("5m"),
    [quotes, setQuotes] = useState<Quote[]>([]),
    [chart, setChart] = useState<ChartResponse | null>(null),
    [news, setNews] = useState<NewsItem[]>([]),
    [settings, setSettings] = useState<Settings | null>(null),
    [offline, setOffline] = useState(false),
    [stream, setStream] = useState("Connecting"),
    [selected, setSelected] = useState<Signal | null>(null),
    [command, setCommand] = useState(false),
    [query, setQuery] = useState(""),
    [replay, setReplay] = useState(0),
    [visibleIndicators, setVisibleIndicators] = useState<string[]>(
      defaultChartIndicators,
    ),
    [sidebar, setSidebar] = useState(true),
    [refresh, setRefresh] = useState(0);
  const [signalConversation, setSignalConversation] = useState<SignalConversation | null>(null);
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]),
    [strategy, setStrategy] = useState(""),
    [report, setReport] = useState<ResearchReport | null>(null),
    [outcomes, setOutcomes] = useState<OutcomeSummary[]>([]),
    [journal, setJournal] = useState<JournalEntry[]>([]),
    [alerts, setAlerts] = useState<Alert[]>([]),
    [sizing, setSizing] = useState<SizingResponse | null>(null),
    [domain, setDomain] = useState<Record<string, unknown> | null>(null),
    [models, setModels] = useState<Record<string, unknown> | null>(null),
    [success, setSuccess] = useState("");
  const currentSymbol = useRef(symbol);
  currentSymbol.current = symbol;
  const currentKey = useRef(`${symbol}:${timeframe}`);
  currentKey.current = `${symbol}:${timeframe}`;
  const loadSequence = useRef(0);
  const [compare, setCompare] = useState(false),
    [comparison, setComparison] = useState<ChartResponse | null>(null),
    [compareError, setCompareError] = useState("");
  const compareSymbol = symbol === "SPY" ? "QQQ" : "SPY";
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const ticker = q.get("symbol");
    if (ticker && /^[A-Z.]{1,10}$/.test(ticker)) setSymbol(ticker);
    const v = q.get("view");
    if (views.includes(v as View)) setView(v as View);
    api
      .settings()
      .then((s) => {
        setSettings(s);
        setAuthenticated(true);
      })
      .catch(() => {})
      .finally(() => setBooting(false));
  }, []);
  useEffect(() => {
    const url = new URL(location.href);
    url.searchParams.set("symbol", symbol);
    url.searchParams.set("view", view);
    history.replaceState({}, "", url);
  }, [symbol, view]);
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommand((c) => !c);
      }
      if (e.key === "Escape") setCommand(false);
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  const load = useCallback(async () => {
    if (!authenticated) return;
    const sequence = ++loadSequence.current,
      key = `${symbol}:${timeframe}`;
    const valid = () =>
      sequence === loadSequence.current && key === currentKey.current;
    setError("");
    try {
      const [w, c, n] = await Promise.all([
        api.watchlist(),
        api.chart(symbol, timeframe),
        api.news(),
      ]);
      if (!valid()) return;
      setQuotes(w.quotes);
      setChart(c);
      setNews(n.items);
      setOffline(false);
      saveCache("watchlist", w);
      saveCache(`chart:${key}`, c);
      saveCache("news", n);
    } catch (e) {
      if (!valid()) return;
      if (e instanceof ApiError && e.status === 401) {
        setAuthenticated(false);
        return;
      }
      setError(errorText(e));
      setOffline(true);
      const w = readCache("watchlist", WatchlistResponseSchema),
        c = readCache(`chart:${key}`, ChartResponseSchema),
        n = readCache("news", NewsResponseSchema);
      if (w) setQuotes(w.data.quotes);
      if (c)
        setChart({
          ...c.data,
          provenance: { ...c.data.provenance, stale: true },
        });
      if (n) setNews(n.data.items);
    }
  }, [authenticated, symbol, timeframe]);
  useEffect(() => {
    setChart(null);
    setSelected(null);
    setReplay(0);
    void load();
    const poll = setInterval(load, 30000);
    return () => {
      clearInterval(poll);
      loadSequence.current++;
    };
  }, [load]);
  useEffect(() => {
    if (refresh) void load();
  }, [refresh, load]);
  useEffect(() => {
    if (!authenticated) return;
    const configured = process.env.NEXT_PUBLIC_SELERY_WS_URL;
    if (!configured) {
      setStream("Polling · 30s");
      return;
    }
    let base: string;
    try {
      const url = new URL(configured);
      base = `${url.protocol}//${url.host}${url.pathname.replace(/\/api\/v1\/stream\/?$/, "").replace(/\/$/, "")}`;
    } catch {
      setStream("Polling · invalid stream URL");
      return;
    }
    const connection = connectResearchStream({
      baseUrl: base,
      ticket: () => api.streamTicket(),
      socket: (url) => new WebSocket(url) as unknown as StreamSocket,
      onEvent: (event) => {
        if (event.type !== "heartbeat") setRefresh((n) => n + 1);
      },
      onStatus: (value) =>
        setStream(
          value === "connected"
            ? "Connected"
            : value === "reconnecting"
              ? "Reconnecting · polling available"
              : "Connecting",
        ),
      onInvalidEvent: () =>
        setStream("Unrecognized update · polling available"),
    });
    return () => connection.stop();
  }, [authenticated]);
  useEffect(() => {
    if (!compare || !authenticated) {
      setComparison(null);
      return;
    }
    let active = true;
    setComparison((previous) =>
      previous?.symbol === compareSymbol && previous.timeframe === timeframe
        ? previous
        : null,
    );
    setCompareError("");
    api
      .chart(compareSymbol, timeframe)
      .then((value) => {
        if (active) setComparison(value);
      })
      .catch((e) => {
        if (active) setCompareError(errorText(e));
      });
    return () => {
      active = false;
    };
  }, [compare, compareSymbol, timeframe, authenticated, refresh]);
  function layout(preset: string) {
    if (preset === "trend") setVisibleIndicators(["ema9", "ema21", "sma50"]);
    if (preset === "momentum")
      setVisibleIndicators(["ema9", "ema21", "rsi14", "macd"]);
    if (preset === "volatility")
      setVisibleIndicators(["bb_upper", "bb_lower", "atr14"]);
    if (preset === "saved") {
      try {
        const value = JSON.parse(
          localStorage.getItem("selery:layout:overview") || "null",
        );
        const known = new Set<string>(
          chartIndicatorGroups.flatMap((group) => [...group.keys]),
        );
        if (
          value &&
          Array.isArray(value.indicators) &&
          value.indicators.every(
            (key: unknown) => typeof key === "string" && known.has(key),
          )
        ) {
          setVisibleIndicators(value.indicators);
          setCompare(value.compare === true);
        } else setError("No saved chart layout available.");
      } catch {
        setError("Saved chart layout could not be read.");
      }
    }
  }
  function saveLayout() {
    try {
      localStorage.setItem(
        "selery:layout:overview",
        JSON.stringify({ indicators: visibleIndicators, compare }),
      );
      setSuccess("Chart layout saved on this browser.");
    } catch {
      setError("This browser could not save the chart layout.");
    }
  }
  useEffect(() => {
    if (!authenticated) return;
    setError("");
    setSuccess("");
    const tasks: Promise<unknown>[] = [];
    if (view === "Research")
      tasks.push(
        api.strategies().then((s) => {
          setStrategies(s);
          setStrategy((v) => v || s.find((i) => i.enabled)?.id || "");
        }),
      );
    if (view === "Outcomes") tasks.push(api.outcomes().then(setOutcomes));
    if (view === "Journal") tasks.push(api.journal().then(setJournal));
    if (view === "Alerts") tasks.push(api.alerts().then(setAlerts));
    if (view === "Settings")
      tasks.push(
        api.settings().then(setSettings),
        api.domain().then(setDomain),
        api.modelStatus().then(setModels),
      );
    Promise.all(tasks).catch((e) => setError(errorText(e)));
  }, [view, authenticated]);
  async function action(run: () => Promise<void>) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await run();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  async function login(e: FormEvent) {
    e.preventDefault();
    await action(async () => {
      const entered = password;
      setPassword("");
      await api.login(entered);
      setSettings(await api.settings());
      setAuthenticated(true);
    });
  }
  async function logout() {
    await action(async () => {
      await api.logout();
      setAuthenticated(false);
      setPasswordFallback(false);
      refreshPasskeys();
      setChart(null);
      setQuotes([]);
      for (const key of Object.keys(localStorage))
        if (key.startsWith("selery:")) localStorage.removeItem(key);
    });
  }
  const quote = quotes.find((q) => q.symbol === symbol);
  const passkeyReady = passkeySupported && passkeyStatus?.enabled && passkeyStatus.registered;
  const lastBar = chart?.bars.at(-1);
  const shownSignals =
    chart?.signals
      .filter((s) => !replay || s.time <= (chart.bars[replay - 1]?.time || 0))
      .slice(-12)
      .reverse() || [];
  const selectTicker = (ticker: string) => {
    setSymbol(ticker);
    setView("Overview");
    setCommand(false);
    setQuery("");
  };
  if (booting)
    return (
      <main className="login">
        <Leaf size={36} />
        <p>Opening your research workspace…</p>
      </main>
    );
  if (!authenticated)
    return (
      <main className="login">
        <div className="login-card">
          <div className="wordmark">
            <Leaf size={28} />
            <span>
              selery<span className="dot">.</span>
            </span>
          </div>
          <Badge>PERSONAL RESEARCH WORKSPACE</Badge>
          <h1>Hi Krish.</h1>
          <p>
            Welcome back to your research workspace.
          </p>
          {passkeyReady && !passwordFallback ? <div>
            <button className="primary" disabled={busy} onClick={() => void action(async () => {
              await signInWithPasskey(api);
              setSettings(await api.settings());setAuthenticated(true);
            })}>
              {busy ? "Waiting for Touch ID…" : "Open workspace"}
              <ArrowUpRight size={16}/>
            </button>
            <p className="muted small" style={{marginTop:12}}>Unlock with Touch ID or your device’s passkey.</p>
            <button disabled={busy} onClick={() => {setPasswordFallback(true);setError("");}}>Use workspace password instead</button>
          </div> : <form onSubmit={login}>
            <label htmlFor="password">Workspace password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button className="primary" disabled={busy}>
              {busy ? "Connecting…" : "Open workspace"}
              <ArrowUpRight size={16} />
            </button>
          </form>}
          {passkeyReady && passwordFallback && <button disabled={busy} onClick={() => {setPasswordFallback(false);setPassword("");setError("");}}>Use Touch ID / passkey instead</button>}
          {error && <Notice>{error}</Notice>}
          <small>
            {passkeyReady ? "Your workspace stays private. The password is available for recovery." : "Sign in once, then enable Touch ID / passkey in Settings."}
          </small>
        </div>
        <footer>{disclaimer}</footer>
      </main>
    );
  return (
    <div className={`app-shell ${sidebar ? "" : "collapsed"}`}>
      <aside className="navigation">
        <a className="wordmark" href="/">
          <Leaf size={24} />
          <span>
            selery<span className="dot">.</span>
          </span>
        </a>
        <div className="workspace-label">PERSONAL WORKSPACE</div>
        <nav>
          {views.map((v, i) => {
            const Icon = icons[i];
            return (
              <button
                key={v}
                className={view === v ? "active" : ""}
                onClick={() => setView(v)}
              >
                <Icon size={17} />
                <span>{v}</span>
                {v === "Overview" && <span className="nav-dot" />}
              </button>
            );
          })}
        </nav>
        <div className="nav-bottom">
          <div className="research-note">
            <ShieldCheck size={18} />
            <strong>Built for perspective.</strong>
            <p>
              Research signals.
              <br />
              Understand the evidence.
            </p>
          </div>
          <button className="muted-button" onClick={logout}>
            <LogOut size={15} />
            Sign out
          </button>
          <div className="profile">
            <span>K</span>
            <div>
              Personal workspace<small>Research access</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="icon-button"
            aria-label="Toggle navigation"
            onClick={() => setSidebar((s) => !s)}
          >
            <PanelLeftClose size={17} />
          </button>
          <div className="breadcrumb">
            Workspace
            <ChevronRight size={12} />
            <strong>{view}</strong>
          </div>
          <button className="search-trigger" onClick={() => setCommand(true)}>
            <Search size={14} />
            <span>Find a symbol or page</span>
            <kbd>⌘ K</kbd>
          </button>
          <Badge warn={settings?.data_mode === "fixtures"}>
            {settings?.data_mode === "fixtures" ? "FIXTURE DATA" : "LIVE DATA"}
          </Badge>
          <button
            className="icon-button"
            aria-label="Refresh data"
            onClick={() => setRefresh((n) => n + 1)}
          >
            <RefreshCw size={15} />
          </button>
        </header>
        <main className="content">
          <div className="page-heading">
            <div className="eyebrow">MARKETS, IN CONTEXT</div>
            <div className="heading-row">
              <h1>
                {view === "Overview"
                  ? "Market overview"
                  : view === "Assistant"
                    ? "Research assistant"
                    : view}
              </h1>
              <span className={`connection ${offline ? "warning" : ""}`}>
                <span />
                {offline ? "Offline · cached data" : stream}
              </span>
            </div>
            <p>
              {view === "Overview"
                ? "Follow the price. Explore the signal. Keep the full picture."
                : "A traceable workspace for your own research."}
            </p>
          </div>
          {error && (
            <Notice>
              {offline && <WifiOff size={15} />} {error}
              {offline ? " Displayed cache may be outdated." : ""}
            </Notice>
          )}
          {success && (
            <div className="success" role="status">
              {success}
            </div>
          )}
          {view === "Traders" && <PublicTraders api={api} />}
          {view === "Overview" && (
            <>
              <section className="quote-strip" aria-label="Watchlist">
                {quotes.length ? (
                  quotes.map((q) => (
                    <button
                      className={`quote-card ${symbol === q.symbol ? "selected" : ""}`}
                      key={q.symbol}
                      onClick={() => selectTicker(q.symbol)}
                    >
                      <div>
                        <strong>{q.symbol}</strong>
                        <Badge>{feedLabel(q.provenance.feed)}</Badge>
                      </div>
                      <div className="quote-price">
                        {formatPrice(q.price)}
                        <span
                          className={
                            (q.change_percent || 0) < 0
                              ? "negative"
                              : "positive"
                          }
                        >
                          {formatPercent(q.change_percent)}
                        </span>
                      </div>
                      <div className="quote-foot">
                        <span>
                          {q.provenance.synthetic
                            ? "Synthetic fixture"
                            : q.provenance.provider}
                          {q.provenance.stale ? " · stale" : ""}
                        </span>
                        <Spark
                          values={q.sparkline}
                          negative={(q.change_percent || 0) < 0}
                        />
                      </div>
                    </button>
                  ))
                ) : (
                  <Empty>
                    No quotes available. Start the backend or check credentials.
                  </Empty>
                )}
              </section>
              <div className="overview-grid">
                <section className="panel chart-panel">
                  <div className="panel-heading">
                    <div className="symbol-title">
                      <div className="ticker-avatar">{symbol[0]}</div>
                      <div>
                        <h2>
                          {symbol}{" "}
                          <span>
                            {symbol === "SPY"
                              ? "S&P 500 ETF"
                              : symbol === "QQQ"
                                ? "Nasdaq-100 ETF"
                                : "Price research"}
                          </span>
                        </h2>
                        <div className="inline-meta">
                          {quote && (
                            <>
                              <strong>{formatPrice(quote.price)}</strong>
                              <Badge>{feedLabel(quote.provenance.feed)}</Badge>
                            </>
                          )}
                          <span>USD</span>
                        </div>
                      </div>
                    </div>
                    <button
                      className="quiet-button"
                      onClick={() => {
                        setView("Assistant");
                      }}
                    >
                      Explain this move
                      <ArrowUpRight size={13} />
                    </button>
                  </div>
                  <div className="chart-toolbar">
                    <div className="segmented">
                      {(["5m", "1h", "1D"] as Timeframe[]).map((t) => (
                        <button
                          key={t}
                          className={timeframe === t ? "active" : ""}
                          onClick={() => setTimeframe(t)}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                    <span className="divider" />
                    {chartIndicatorGroups.map((group) => {
                      const available = group.keys.every(
                        (key) => !!chart?.indicators[key],
                      );
                      const active = group.keys.every((key) =>
                        visibleIndicators.includes(key),
                      );
                      return (
                        <button
                          key={group.id}
                          className={`indicator-toggle ${active ? "positive" : ""}`}
                          disabled={!available}
                          title={
                            available
                              ? "Toggle backend indicator"
                              : group.id === "vwap"
                                ? "needs SIP data"
                                : "Backend series unavailable"
                          }
                          onClick={() =>
                            setVisibleIndicators((current) =>
                              active
                                ? current.filter(
                                    (key) =>
                                      !(
                                        group.keys as readonly string[]
                                      ).includes(key),
                                  )
                                : [...new Set([...current, ...group.keys])],
                            )
                          }
                        >
                          {group.label}
                          {!available && (
                            <span className="warning">
                              {" "}
                              ·{" "}
                              {group.id === "vwap"
                                ? "needs SIP data"
                                : "unavailable"}
                            </span>
                          )}
                        </button>
                      );
                    })}
                    <select
                      aria-label="Chart layout preset"
                      defaultValue=""
                      onChange={(event) => {
                        layout(event.target.value);
                        event.target.value = "";
                      }}
                    >
                      <option value="" disabled>
                        Layout preset
                      </option>
                      <option value="trend">Price & trend</option>
                      <option value="momentum">Momentum</option>
                      <option value="volatility">Volatility</option>
                      <option value="saved">My saved layout</option>
                    </select>
                    <button onClick={saveLayout}>Save layout</button>
                    <button
                      aria-pressed={compare}
                      onClick={() => setCompare((value) => !value)}
                    >
                      Compare {compareSymbol}
                    </button>
                  </div>
                  {chart ? (
                    <ResearchChart
                      data={chart}
                      onSignal={setSelected}
                      replay={replay}
                      indicators={visibleIndicators}
                    />
                  ) : (
                    <div className="chart-loading">Loading finalized bars…</div>
                  )}
                  <div className="chart-meta">
                    <span>
                      {chart?.provenance.synthetic
                        ? "SYNTHETIC FIXTURE · "
                        : ""}
                      {chart
                        ? `${chart.provenance.provider} · ${feedLabel(chart.provenance.feed)} · ${chart.provenance.stale ? "STALE" : "as of"} ${formatTime(chart.provenance.observed_at)}`
                        : "Waiting for data"}
                    </span>
                    {lastBar && (
                      <span>
                        Vol {lastBar.volume.toLocaleString()} ·{" "}
                        {feedLabel(lastBar.feed)}
                      </span>
                    )}
                  </div>
                  <div className="replay-row">
                    <label htmlFor="replay">Replay</label>
                    <input
                      id="replay"
                      type="range"
                      min={30}
                      max={Math.max(chart?.bars.length || 30, 30)}
                      value={replay || chart?.bars.length || 30}
                      onChange={(e) => setReplay(Number(e.target.value))}
                    />
                    <button onClick={() => setReplay(0)}>
                      {replay ? "Return to latest" : "Latest"}
                    </button>
                    <a
                      href="https://www.tradingview.com/"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Charts by TradingView
                    </a>
                  </div>
                </section>
                <aside className="panel context-panel">
                  <div className="section-title">
                    <h2>Signal context</h2>
                    <Activity size={16} />
                  </div>
                  {selected ? (
                    <><SignalDetails signal={selected} /><button className="quiet-button" onClick={() => { setSignalConversation({ signal: selected, start: chart?.bars[0]?.time || selected.time, end: selected.time }); setView("Assistant"); }}>Ask about this signal</button></>
                  ) : (
                    <>
                      <div className="context-illustration">
                        <Activity size={32} />
                      </div>
                      <h3>The evidence behind the arrow.</h3>
                      <p>
                        Select a chart marker or a signal below to explore its
                        reference levels, features, and research horizon.
                      </p>
                      <div className="context-rule">
                        <span className="small-dot" />
                        Finalized bars only
                      </div>
                      <div className="context-rule">
                        <span className="small-dot" />
                        Confidence requires calibration
                      </div>
                    </>
                  )}
                  <div className="capabilities">
                    <h4>DATA AVAILABILITY</h4>
                    {chart?.capabilities
                      .filter((c) => !c.enabled)
                      .slice(0, 4)
                      .map((c) => (
                        <div key={c.id}>
                          <span>{c.label}</span>
                          <span className="warning">
                            {c.reason || "needs SIP data"}
                          </span>
                        </div>
                      ))}
                  </div>
                </aside>
              </div>
              {compare && (
                <section
                  className="panel chart-panel"
                  style={{ marginTop: 20, marginBottom: 20 }}
                >
                  <div className="panel-heading">
                    <h2>
                      {compareSymbol} comparison · {timeframe}
                    </h2>
                    <Badge>
                      {comparison
                        ? feedLabel(comparison.provenance.feed)
                        : "Waiting for data"}
                    </Badge>
                  </div>
                  {comparison ? (
                    <>
                      <ResearchChart
                        data={comparison}
                        onSignal={setSelected}
                        replay={0}
                        indicators={visibleIndicators}
                      />
                      <div className="chart-meta">
                        {comparison.provenance.provider} ·{" "}
                        {comparison.provenance.stale ? "Stale · " : ""}
                        {formatTime(comparison.provenance.observed_at)} ·
                        Independent price scale
                      </div>
                    </>
                  ) : (
                    <div className="chart-loading">
                      {compareError || "Loading comparison bars…"}
                    </div>
                  )}
                </section>
              )}
              <div className="bottom-grid">
                <section className="panel">
                  <div className="section-title">
                    <h2>
                      Recent signals{" "}
                      <span className="count">{shownSignals.length}</span>
                    </h2>
                    <span className="muted">
                      {timeframe} · {symbol}
                    </span>
                  </div>
                  {shownSignals.length ? (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Strategy / timestamp</th>
                            <th>Direction</th>
                            <th>Reference</th>
                            <th>Horizon</th>
                            <th>Confidence</th>
                          </tr>
                        </thead>
                        <tbody>
                          {shownSignals.map((s) => (
                            <tr
                              key={s.id}
                              onClick={() => setSelected(s)}
                              tabIndex={0}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") setSelected(s);
                              }}
                            >
                              <td>
                                <strong>
                                  {s.strategy.replaceAll("_", " ")}
                                </strong>
                                <small>
                                  {formatTime(s.time)} · {feedLabel(s.feed)}
                                </small>
                              </td>
                              <td>
                                <Badge warn={s.direction === "bearish"}>
                                  {s.direction}
                                </Badge>
                              </td>
                              <td className="mono">
                                {formatPrice(s.reference_price)}
                              </td>
                              <td>{s.horizon_bars} bars</td>
                              <td title={signalConfidence(s).detail}>
                                <strong className={signalConfidence(s).available ? "mono" : "muted"}>
                                  {signalConfidence(s).label}
                                </strong>
                                <small className="muted">
                                  {signalConfidence(s).available ? "Calibrated · target first" : "No calibrated estimate"}
                                </small>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <Empty>No finalized signals in this window.</Empty>
                  )}
                  <p className="muted small" style={{ padding: "12px 18px" }}>
                    Confidence estimates whether the analytical target is reached before the stop within the signal horizon.
                    Select a signal for its scope or the reason a score is unavailable.
                  </p>
                  {shownSignals.length > 0 && shownSignals.every(s => !signalConfidence(s).available) &&
                    <p className="notice" style={{margin:"0 18px 16px"}}>
                      Confidence is unavailable for these signals: no calibrated prediction was recorded at signal time.
                      A validated model must be active before new signals occur. Training later does not add scores to old signals.
                    </p>}
                </section>
                <section className="panel news-panel">
                  <div className="section-title">
                    <h2>Headlines & context</h2>
                    <BookOpen size={15} />
                  </div>
                  {news.length ? (
                    news.slice(0, 6).map((n) => (
                      <article className="news-item" key={n.id}>
                        <div className="eyebrow">
                          {n.source} <span>· {formatTime(n.published_at)}</span>
                        </div>
                        <a
                          href={safeLink(n.url)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {n.headline}
                          <ArrowUpRight size={12} />
                        </a>
                        <p>{n.summary}</p>
                        <div className="news-tags">
                          {n.symbols.map((s) => (
                            <span key={s}>{s}</span>
                          ))}
                          {n.sentiment !== null && (
                            <span
                              title={n.sentiment_method || "Method unavailable"}
                            >
                              Sentiment {n.sentiment.toFixed(2)}
                            </span>
                          )}
                        </div>
                      </article>
                    ))
                  ) : (
                    <Empty>No source-linked news available.</Empty>
                  )}
                </section>
              </div>
            </>
          )}
          {view === "Research" && (
            <div className="research-layout">
              <section className="panel padded">
                <div className="section-title">
                  <h2>Historical event study</h2>
                  <FlaskConical size={18} />
                </div>
                <p className="muted">
                  Evaluate signal thresholds on finalized historical bars.
                  Reports describe analytical outcomes and assumptions.
                </p>
                <form
                  className="form-grid"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void action(async () =>
                      setReport(
                        await api.research({
                          symbol,
                          timeframe,
                          strategy,
                          feed: settings?.feed || "iex",
                          horizon_bars: Number(
                            new FormData(e.currentTarget).get("horizon"),
                          ),
                        }),
                      ),
                    );
                  }}
                >
                  <label>
                    Symbol
                    <select
                      value={symbol}
                      onChange={(e) => setSymbol(e.target.value)}
                    >
                      {["SPY", "QQQ", "AAPL", "NVDA"].map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Timeframe
                    <select
                      value={timeframe}
                      onChange={(e) =>
                        setTimeframe(e.target.value as Timeframe)
                      }
                    >
                      {["5m", "1h", "1D"].map((t) => (
                        <option key={t}>{t}</option>
                      ))}
                    </select>
                  </label>
                  <label className="wide">
                    Strategy
                    <select
                      value={strategy}
                      onChange={(e) => setStrategy(e.target.value)}
                    >
                      {strategies.map((s) => (
                        <option value={s.id} disabled={!s.enabled} key={s.id}>
                          {s.name}
                          {s.enabled ? "" : ` — ${s.reason}`}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Horizon in bars
                    <input
                      name="horizon"
                      type="number"
                      min="1"
                      max="252"
                      defaultValue="12"
                      required
                    />
                  </label>
                  <div className="align-bottom">
                    <Badge>{feedLabel(settings?.feed || "iex")}</Badge>
                  </div>
                  <button className="primary wide" disabled={busy || !strategy}>
                    {busy ? "Evaluating…" : "Run event study"}
                    <ArrowUpRight size={15} />
                  </button>
                </form>
              </section>
              <section className="panel padded">
                {report ? (
                  <>
                    <h2>
                      {report.request.symbol} ·{" "}
                      {report.request.strategy.replaceAll("_", " ")}
                    </h2>
                    <p className="muted">
                      {report.signal_count} signals ·{" "}
                      {formatTime(report.created_at)} ·{" "}
                      {feedLabel(report.request.feed)}
                    </p>
                    <div className="metric-grid">
                      {Object.entries(report.metrics).map(([key, value]) => (
                        <div className="metric" key={key}>
                          <small>{key.replaceAll("_", " ")}</small>
                          <strong>
                            {value === null
                              ? "Unavailable"
                              : Number(value.toFixed(4)).toLocaleString()}
                          </strong>
                        </div>
                      ))}
                    </div>
                    {report.series.length > 0 && (
                      <ReportChart report={report} />
                    )}
                    <h3>Assumptions</h3>
                    <ul className="readable-list">
                      {report.assumptions.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                    <h3>Limitations</h3>
                    <ul className="readable-list warning">
                      {report.limitations.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                    <button
                      className="quiet-button"
                      onClick={() => downloadReport(report)}
                    >
                      Download report JSON
                    </button>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Outcome</th>
                            <th>Observed bars</th>
                            <th>Evidence</th>
                          </tr>
                        </thead>
                        <tbody>
                          {report.outcomes.map((o) => (
                            <tr key={o.signal_id}>
                              <td>{o.status.replaceAll("_", " ")}</td>
                              <td>{o.bars_observed}</td>
                              <td>{o.reason || "Threshold evaluation"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <Empty>
                    Your report will appear here. Every unavailable metric
                    includes the study limitations.
                  </Empty>
                )}
              </section>
              <ReportLibrary onSelect={setReport} refreshKey={report?.id} />
            </div>
          )}
          {view === "Outcomes" && (
            <section className="panel">
              <div className="section-title">
                <h2>Forward signal observations</h2>
                <Badge>IMMUTABLE SNAPSHOTS</Badge>
              </div>
              <p className="padded muted">
                Ambiguous outcomes remain ambiguous. Historical comparisons
                require matching feeds, strategy versions, and research
                horizons.
              </p>
              {outcomes.length ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Strategy / feed</th>
                        <th>Matured</th>
                        <th>Target first</th>
                        <th>Stop first</th>
                        <th>Neither</th>
                        <th>Ambiguous</th>
                        <th>Hit rate</th>
                        <th>Comparison</th>
                      </tr>
                    </thead>
                    <tbody>
                      {outcomes.map((o) => (
                        <tr key={`${o.strategy}:${o.feed}`}>
                          <td>
                            {o.strategy}
                            <small>{feedLabel(o.feed)}</small>
                          </td>
                          <td>{o.matured}</td>
                          <td>{o.target_first}</td>
                          <td>{o.stop_first}</td>
                          <td>{o.neither}</td>
                          <td>{o.ambiguous}</td>
                          <td>
                            {o.hit_rate === null
                              ? "Unavailable"
                              : formatPercent(o.hit_rate * 100)}
                            <small>{o.denominator}</small>
                          </td>
                          <td>
                            {o.comparison_reason || "Matched cohort"}
                            <small>
                              {o.historical_hit_rate === null
                                ? "Historical rate unavailable"
                                : formatPercent(o.historical_hit_rate * 100)}
                            </small>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty>No forward observations have matured yet.</Empty>
              )}
            </section>
          )}
          {view === "Journal" && (
            <div className="research-layout">
              <section className="panel padded">
                <h2>Your research journal</h2>
                <p className="muted">
                  Write down your thesis and what you learned. Entries are saved
                  only when you choose Save entry.
                </p>
                <form
                  className="form-grid"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const form = e.currentTarget;
                    const d = new FormData(form);
                    void action(async () => {
                      const entry = await api.saveJournal({
                        symbol: String(d.get("symbol")),
                        thesis: String(d.get("thesis")),
                        outcome: String(d.get("outcome")),
                        reflection: String(d.get("reflection")),
                      });
                      setJournal((j) => [entry, ...j]);
                      form.reset();
                      setSuccess("Your journal entry was saved.");
                    });
                  }}
                >
                  <label className="wide">
                    Symbol
                    <input
                      name="symbol"
                      defaultValue={symbol}
                      pattern="[A-Za-z.]{1,10}"
                      required
                      maxLength={10}
                    />
                  </label>
                  <label className="wide">
                    Thesis
                    <textarea
                      name="thesis"
                      placeholder="What am I observing, and why might it matter?"
                      required
                      maxLength={10000}
                    />
                  </label>
                  <label className="wide">
                    Observed outcome
                    <textarea
                      name="outcome"
                      placeholder="What actually happened?"
                      maxLength={10000}
                    />
                  </label>
                  <label className="wide">
                    Reflection
                    <textarea
                      name="reflection"
                      placeholder="What changed my understanding?"
                      maxLength={10000}
                    />
                  </label>
                  <button disabled={busy} className="primary wide">
                    Save entry
                    <BookOpen size={15} />
                  </button>
                </form>
              </section>
              <section className="panel padded">
                <h2>
                  Saved entries <span className="count">{journal.length}</span>
                </h2>
                {journal.length ? (
                  journal.map((j, i) => (
                    <article className="journal-entry" key={j.id || i}>
                      <div className="section-title">
                        <Badge>{j.symbol}</Badge>
                        <small>
                          {j.created_at ? formatTime(j.created_at) : "Saved"}
                        </small>
                      </div>
                      <h3>{j.thesis}</h3>
                      {j.outcome && (
                        <p>
                          <strong>Outcome</strong>
                          <br />
                          {j.outcome}
                        </p>
                      )}
                      {j.reflection && (
                        <p>
                          <strong>Reflection</strong>
                          <br />
                          {j.reflection}
                        </p>
                      )}
                    </article>
                  ))
                ) : (
                  <Empty>A place for your own observations.</Empty>
                )}
              </section>
            </div>
          )}
          {view === "Sizing" && (
            <div className="research-layout">
              <section className="panel padded">
                <h2>Research sizing calculator</h2>
                <p className="muted">
                  Explore hypothetical risk and allocation limits with your own
                  inputs. Calculations run on the research backend.
                </p>
                <form
                  className="form-grid"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const d = new FormData(e.currentTarget);
                    void action(async () =>
                      setSizing(
                        await api.size({
                          research_capital: Number(d.get("capital")),
                          risk_percent: Number(d.get("risk")),
                          reference_price: Number(d.get("reference")),
                          stop: Number(d.get("stop")),
                          max_allocation_percent: Number(d.get("allocation")),
                        }),
                      ),
                    );
                  }}
                >
                  <label>
                    Research capital ($)
                    <input
                      name="capital"
                      type="number"
                      min="1"
                      step="0.01"
                      required
                      placeholder="10000"
                    />
                  </label>
                  <label>
                    Risk budget (%)
                    <input
                      name="risk"
                      type="number"
                      min="0.01"
                      max="5"
                      step="0.01"
                      required
                      placeholder="1"
                    />
                  </label>
                  <label>
                    Reference price ($)
                    <input
                      name="reference"
                      type="number"
                      min="0.01"
                      step="0.01"
                      required
                    />
                  </label>
                  <label>
                    Analytical stop level ($)
                    <input
                      name="stop"
                      type="number"
                      min="0.01"
                      step="0.01"
                      required
                    />
                  </label>
                  <label className="wide">
                    Maximum allocation (%)
                    <input
                      name="allocation"
                      type="number"
                      min="0.01"
                      max="100"
                      step="0.01"
                      required
                      placeholder="20"
                    />
                  </label>
                  <button disabled={busy} className="primary wide">
                    Calculate research size
                    <ArrowUpRight size={15} />
                  </button>
                </form>
              </section>
              <section className="panel padded">
                {sizing ? (
                  <>
                    <h2>Analytical size</h2>
                    <div className="metric-grid">
                      {[
                        ["Units", sizing.units.toLocaleString()],
                        ["Risk budget", formatPrice(sizing.risk_budget)],
                        [
                          "Analytical risk",
                          formatPrice(sizing.analytical_risk),
                        ],
                        ["Notional", formatPrice(sizing.notional)],
                      ].map(([k, v]) => (
                        <div className="metric" key={k}>
                          <small>{k}</small>
                          <strong>{v}</strong>
                        </div>
                      ))}
                    </div>
                    <Notice>{sizing.disclaimer}</Notice>
                  </>
                ) : (
                  <Empty>
                    Enter your research assumptions to calculate an
                    informational size.
                  </Empty>
                )}
              </section>
            </div>
          )}
          {view === "Alerts" && (
            <section className="panel padded">
              <div className="section-title">
                <h2>Research alerts</h2>
                <Badge>{alerts.filter((a) => !a.read).length} UNREAD</Badge>
              </div>
              {alerts.length ? (
                alerts.map((a) => (
                  <article
                    className={`alert-item ${a.read ? "read" : ""}`}
                    key={a.id}
                  >
                    <Bell size={18} />
                    <div>
                      <small>
                        {a.kind} · {formatTime(a.created_at)}
                      </small>
                      <h3>{a.title}</h3>
                      <p>{a.body}</p>
                      {a.symbol && (
                        <button
                          className="quiet-button"
                          onClick={() => selectTicker(a.symbol!)}
                        >
                          Open {a.symbol}
                          <ChevronRight size={14} />
                        </button>
                      )}
                    </div>
                    {!a.read && (
                      <button
                        className="quiet-button"
                        disabled={busy}
                        onClick={() =>
                          void action(async () => {
                            await api.readAlert(a.id);
                            setAlerts((all) =>
                              all.map((item) =>
                                item.id === a.id
                                  ? { ...item, read: true }
                                  : item,
                              ),
                            );
                          })
                        }
                      >
                        Mark read
                      </button>
                    )}
                  </article>
                ))
              ) : (
                <Empty>
                  No alerts yet. Finalized research events will appear here.
                </Empty>
              )}
            </section>
          )}
          {view === "Assistant" && <Conversations api={api} suggestedSymbol={symbol} settings={settings} signalRequest={signalConversation} onSignalOpened={() => setSignalConversation(null)} />}
          {view === "Settings" && (
            <div className="settings-grid">
              <PasskeySettings api={api} onChanged={refreshPasskeys}/>
              <section className="panel padded">
                <h2>Workspace configuration</h2>
                <p className="muted">
                  Sensitive settings are managed on the backend.
                </p>
                {settings && (
                  <dl className="details">
                    <dt>Data mode</dt>
                    <dd>
                      <Badge warn={settings.data_mode === "fixtures"}>
                        {settings.data_mode}
                      </Badge>
                    </dd>
                    <dt>Market feed</dt>
                    <dd>{feedLabel(settings.feed)}</dd>
                    <dt>LLM access</dt>
                    <dd>{settings.llm_enabled ? "Enabled" : "Disabled"}</dd>
                    <dt>Monthly LLM cap</dt>
                    <dd>{formatPrice(settings.llm_monthly_cap_usd)}</dd>
                    <dt>LLM spend</dt>
                    <dd>{formatPrice(settings.llm_spent_usd)}</dd>
                    <dt>Quantitative logic</dt>
                    <dd>Python backend</dd>
                  </dl>
                )}
                <Notice>{disclaimer}</Notice>
              </section>
              <section className="panel padded">
                <h2>SPY research availability</h2>
                {domain ? (
                  <DataTree value={domain} />
                ) : (
                  <Empty>No domain metadata available.</Empty>
                )}
              </section>
              <section className="panel padded wide">
                <h2>Model registry & calibration</h2>
                <p className="muted">
                  Confidence and explanations require trained, validated models.
                  Training is manual.
                </p>
                {models ? (
                  <>
                    {models.status === "untrained" && <p className="notice">No validated model is active. Numerical signal confidence remains unavailable until a model passes validation and records predictions for new signals.</p>}
                    <DataTree value={models} />
                  </>
                ) : (
                  <Empty>No model metadata available.</Empty>
                )}
              </section>
            </div>
          )}
          <footer className="footer">
            <span>
              <Leaf size={12} />
              {disclaimer}
            </span>
            <span>SELERY / RESEARCH WORKSPACE</span>
          </footer>
        </main>
      </div>
      {command && (
        <div className="modal-backdrop" onClick={() => setCommand(false)}>
          <div
            className="command-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Find a symbol or page"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="command-search">
              <Search size={18} />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search symbols and pages…"
              />
              <kbd>ESC</kbd>
            </div>
            <h4>SYMBOLS</h4>
            {["SPY", "QQQ", "AAPL", "NVDA"]
              .filter((s) => s.includes(query.toUpperCase()))
              .map((s) => (
                <button key={s} onClick={() => selectTicker(s)}>
                  <ChartNoAxesCombined size={16} />
                  {s}
                  <ArrowUpRight size={14} />
                </button>
              ))}
            <h4>PAGES</h4>
            {views
              .filter((v) => v.toLowerCase().includes(query.toLowerCase()))
              .map((v) => (
                <button
                  key={v}
                  onClick={() => {
                    setView(v);
                    setCommand(false);
                    setQuery("");
                  }}
                >
                  <Command size={16} />
                  {v}
                  <ChevronRight size={14} />
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
function SignalDetails({ signal: s }: { signal: Signal }) {
  const confidence = signalConfidence(s);
  return (
    <div className="signal-details">
      <Badge warn={s.direction === "bearish"}>
        {s.direction} research signal
      </Badge>
      <h3>
        {s.symbol} · {s.strategy.replaceAll("_", " ")}
      </h3>
      <p>{s.explanation}</p>
      <dl className="details">
        <dt>Reference</dt>
        <dd>{formatPrice(s.reference_price)}</dd>
        <dt>Analytical stop</dt>
        <dd>{formatPrice(s.stop)}</dd>
        <dt>Analytical target</dt>
        <dd>{formatPrice(s.target)}</dd>
        <dt>Horizon</dt>
        <dd>{s.horizon_bars} bars</dd>
        <dt>Feed</dt>
        <dd>{feedLabel(s.feed)}</dd>
        <dt>Available</dt>
        <dd>{formatTime(s.available_at)}</dd>
        <dt>Confidence</dt>
        <dd>
          {confidence.label}
        </dd>
      </dl>
      <p className={confidence.available ? "muted small" : "warning small"}>{confidence.detail}</p>
      <details>
        <summary>Signal-time features</summary>
        <dl className="details">
          {Object.entries(s.features).map(([k, v]) => (
            <div className="detail-pair" key={k}>
              <dt>{k}</dt>
              <dd>{Number(v.toFixed(4))}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  );
}
function Spark({ values, negative }: { values: number[]; negative: boolean }) {
  if (values.length < 2) return null;
  const min = Math.min(...values),
    range = Math.max(...values) - min || 1;
  const points = values
    .map(
      (v, i) =>
        `${(i / (values.length - 1)) * 70},${23 - ((v - min) / range) * 21}`,
    )
    .join(" ");
  return (
    <svg width="72" height="26" viewBox="0 0 72 26" aria-hidden="true">
      <polyline
        points={points}
        fill="none"
        stroke={negative ? "#cf8982" : "#a7c9a0"}
        strokeWidth="1.5"
      />
    </svg>
  );
}
function safeLink(url: string) {
  try {
    const u = new URL(url);
    return ["https:", "http:"].includes(u.protocol) ? url : undefined;
  } catch {
    return undefined;
  }
}
function downloadReport(report: ResearchReport) {
  const a = document.createElement("a"),
    url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
    );
  a.href = url;
  a.download = `selery-${report.request.symbol}-${report.id}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
function DataTree({ value }: { value: unknown }) {
  if (value === null || value === undefined)
    return <span className="muted">Unavailable</span>;
  if (typeof value !== "object")
    return (
      <span>
        {typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}
      </span>
    );
  if (Array.isArray(value))
    return (
      <div className="data-array">
        {value.length ? (
          value.map((v, i) => (
            <div key={i}>
              <DataTree value={v} />
            </div>
          ))
        ) : (
          <span className="muted">None available</span>
        )}
      </div>
    );
  return (
    <dl className="data-tree">
      {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
        <div key={k}>
          <dt>{k.replaceAll("_", " ")}</dt>
          <dd>
            <DataTree value={v} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
