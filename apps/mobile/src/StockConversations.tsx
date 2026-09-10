import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert, AppState, Keyboard, KeyboardAvoidingView, Platform, Pressable,
  ScrollView, StyleSheet, Text, View,
} from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  ApiError, formatPrice, formatTime, type ChartResponse, type Conversation,
  type ConversationDetail, type Timeframe,
} from "@selery/shared";
import { useSession } from "./session";
import { NativeChart } from "./NativeChart";
import { ResearchMarkdown } from "./ResearchMarkdown";
import { Button, Card, ExternalLink, FeedBadge, Input, Page, c, styles } from "./ui";

const pageSize = 20;
const requestId = () => `mobile_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 14)}`;
const errorText = (e: unknown) => e instanceof Error ? e.message : "Request unavailable. Try again.";

export function StockConversations() {
  const { symbol: routeSymbol, conversation: routeConversation } = useLocalSearchParams<{ symbol?: string | string[]; conversation?: string }>();
  const initialSymbol = (Array.isArray(routeSymbol) ? routeSymbol[0] : routeSymbol) || "";
  const { client, authenticated } = useSession();
  const router = useRouter();
  const [symbol, setSymbol] = useState(initialSymbol.toUpperCase());
  const [items, setItems] = useState<Conversation[]>([]);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [title, setTitle] = useState("");
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);
  const latestDetail = useRef<ConversationDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(routeConversation || null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [chart, setChart] = useState<ChartResponse | null>(null);
  const [timeframe, setTimeframe] = useState<Timeframe>("5m");
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [chartError, setChartError] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState(false);
  const [keyboardOpen, setKeyboardOpen] = useState(false);
  const generation = useRef(0);
  const mutation = useRef(0);
  const mutating = useRef(false);
  const transcript = useRef<ScrollView>(null);
  // Preserve an uncertain request ID in memory so a manual retry cannot charge twice.
  const attempted = useRef<{ conversationId: string; message: string; id: string; timeframe: Timeframe } | null>(null);

  useFocusEffect(useCallback(() => {
    function clearPrivateView() {
      generation.current++;
      setActive(false);
      setItems([]);
      setDetail(null);
      setChart(null);
      setDraft("");
      setTitle(""); setSearch(""); setSearchQuery("");
      setError("");
      setChartError("");
      setBusy(false);
      setLoading(false);
      // Keep an in-flight request identity across background/foreground transitions.
      if (!authenticated) attempted.current = null;
      latestDetail.current = null;
      pausedRef.current = false; setPaused(false);
      mutating.current = false;
    }
    setActive(authenticated && AppState.currentState === "active");
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") setActive(authenticated);
      else clearPrivateView();
    });
    return () => { subscription.remove(); clearPrivateView(); };
  }, [authenticated, client]));

  useEffect(() => { if (routeConversation) select(routeConversation); }, [routeConversation]);

  useEffect(() => { if (!selectedId) setSymbol(initialSymbol.toUpperCase()); }, [initialSymbol]);

  useEffect(() => {
    const show = Keyboard.addListener("keyboardDidShow", () => setKeyboardOpen(true));
    const hide = Keyboard.addListener("keyboardDidHide", () => setKeyboardOpen(false));
    return () => { show.remove(); hide.remove(); };
  }, []);

  useEffect(() => {
    if (!active) return;
    const current = generation.current;
    let disposed = false;
    let inFlight = false;
    let lastRead = 0;
    let lastChart = 0;
    const valid = () => !disposed && current === generation.current;
    async function refresh() {
      if (inFlight || (mutating.current && !selectedId)) return;
      const streaming = mutating.current || latestDetail.current?.messages.some((message) => message.status === "pending");
      if (lastRead && Date.now() - lastRead < (streaming ? 650 : 30_000)) return;
      lastRead = Date.now();
      inFlight = true;
      const mutationVersion = mutation.current;
      const currentRead = () => valid() && mutationVersion === mutation.current;
      setLoading(true);
      try {
        if (!selectedId) {
          const result = await client.conversations(pageSize, offset, searchQuery);
          if (currentRead()) { setItems(result); setError(""); }
        } else {
          const result = await client.conversation(selectedId);
          if (!currentRead()) return;
          latestDetail.current = result;
          if (!pausedRef.current) setDetail(result);
          setError("");
          try {
            if (lastChart && Date.now() - lastChart < 30_000) return;
            const value = result.conversation.signal ? await client.conversationChart(selectedId) : await client.chart(result.conversation.symbol, timeframe, "iex", 200);
            if (currentRead()) { setChart(value); setChartError(""); lastChart = Date.now(); }
          } catch (e) { if (currentRead()) setChartError(errorText(e)); }
        }
      } catch (e) { if (currentRead()) {
        setError(errorText(e));
        if (e instanceof ApiError && (e.status === 401 || e.status === 404)) {
          setDetail(null); setChart(null); setDraft(""); attempted.current = null;
        }
      } }
      finally { inFlight = false; if (valid()) setLoading(false); }
    }
    void refresh();
    // Reads only. Entering a conversation and polling never invoke the LLM.
    const timer = setInterval(() => void refresh(), selectedId ? 700 : 30_000);
    return () => { disposed = true; clearInterval(timer); };
  }, [active, client, offset, selectedId, timeframe, searchQuery]);

  function select(id: string | null) {
    generation.current++;
    setSelectedId(id);
    pausedRef.current = false; setPaused(false);
    latestDetail.current = null;
    setTitle("");
    setDetail(null);
    setChart(null);
    setDraft("");
    setError("");
    setChartError("");
    setBusy(false);
    mutating.current = false;
    attempted.current = null;
  }

  async function create() {
    if (mutating.current) return;
    mutating.current = true;
    const current = generation.current;
    setBusy(true);
    setError("");
    try {
      const result = await client.createConversation(symbol.trim().toUpperCase());
      if (current === generation.current) select(result.id);
    } catch (e) { if (current === generation.current) setError(errorText(e)); }
    finally { if (current === generation.current) { setBusy(false); mutating.current = false; } }
  }

  async function send() {
    if (!selectedId || !draft.trim() || busy || mutating.current) return;
    const current = generation.current;
    const message = draft.trim();
    if (!attempted.current || attempted.current.conversationId !== selectedId || attempted.current.message !== message) {
      attempted.current = { conversationId: selectedId, message, id: requestId(), timeframe: detail?.conversation.signal?.timeframe || timeframe };
    }
    const attempt = attempted.current;
    mutation.current++;
    mutating.current = true;
    setBusy(true);
    pausedRef.current = false; setPaused(false);
    setError("");
    try {
      const result = await client.sendConversationMessage(selectedId, message, attempt.id, attempt.timeframe);
      if (current !== generation.current) return;
      latestDetail.current = result;
      if (!pausedRef.current) setDetail(result);
      setDraft("");
      attempted.current = null;
    } catch (e) {
      if (current !== generation.current) return;
      setError(errorText(e));
      try {
        const result = await client.conversation(selectedId);
        if (current !== generation.current) return;
        latestDetail.current = result;
        if (!pausedRef.current) setDetail(result);
        // Only a confirmed terminal failure allows a new paid attempt.
        const turn = result.messages.find((m) => m.id === `${selectedId}:${attempt.id}`);
        if (turn?.status === "failed") attempted.current = null;
      } catch { /* Keep the draft and request ID until the user retries. */ }
    } finally { if (current === generation.current) { setBusy(false); mutating.current = false; } }
  }

  function toggleDisplay() {
    pausedRef.current = !pausedRef.current;
    setPaused(pausedRef.current);
    if (!pausedRef.current && latestDetail.current) setDetail(latestDetail.current);
  }

  async function updateConversation(kind: "rename" | "summary") {
    if (!selectedId || busy || mutating.current) return;
    const current = generation.current;
    mutation.current++; mutating.current = true; setBusy(true); setError("");
    try {
      const conversation = kind === "rename" ? await client.renameConversation(selectedId, title.trim()) : await client.summarizeConversation(selectedId);
      if (current === generation.current) {
        setDetail((previous) => previous ? { ...previous, conversation } : previous);
        if (latestDetail.current) latestDetail.current = { ...latestDetail.current, conversation };
        setTitle("");
      }
    } catch (e) { if (current === generation.current) setError(errorText(e)); }
    finally { if (current === generation.current) { setBusy(false); mutating.current = false; } }
  }

  async function remove() {
    if (!selectedId || busy) return;
    const current = generation.current;
    mutation.current++;
    mutating.current = true;
    setBusy(true);
    try {
      await client.deleteConversation(selectedId);
      if (current === generation.current) { setOffset(0); select(null); }
    } catch (e) { if (current === generation.current) setError(errorText(e)); }
    finally { if (current === generation.current) { setBusy(false); mutating.current = false; } }
  }

  if (!active) return <View style={styles.page} />;
  if (!selectedId) return (
    <Page title="Stock conversations">
      <Button title="Back to workspace" onPress={() => router.back()} />
      <Text style={styles.text}>Choose a stock to start a conversation. Your chart and chat stay together, and you can return to saved conversations.</Text>
      <Input accessibilityLabel="Stock symbol" placeholder="Stock symbol, e.g. SPY" value={symbol} onChangeText={setSymbol} autoCapitalize="characters" autoCorrect={false} maxLength={12} />
      <Button title={busy ? "Creating…" : "Start conversation"} disabled={busy || !/^[A-Za-z][A-Za-z0-9.-]{0,11}$/.test(symbol.trim())} onPress={() => void create()} />
      {!!error && <Text accessibilityRole="alert" style={styles.warning}>{error}</Text>}
      <Text style={styles.heading}>Saved conversations</Text>
      <Input accessibilityLabel="Search conversations" placeholder="Search saved conversations" value={search} onChangeText={setSearch} maxLength={100} />
      <Button title="Search" onPress={() => { setOffset(0); setItems([]); setSearchQuery(search.trim()); }} />
      {loading && <Text style={styles.muted}>Loading conversations…</Text>}
      {!loading && !items.length && <Text style={styles.muted}>No conversations on this page.</Text>}
      {items.map((item) => <Pressable key={item.id} accessibilityRole="button" accessibilityLabel={`Open ${item.symbol} conversation`} onPress={() => select(item.id)}>
        <Card><Text style={styles.heading}>{item.symbol} · {item.title}</Text><Text style={styles.muted}>Updated {new Date(item.updated_at).toLocaleString()}</Text></Card>
      </Pressable>)}
      <View style={styles.row}>
        <Button title="Previous" disabled={offset === 0 || loading} onPress={() => { setItems([]); setOffset(Math.max(0, offset - pageSize)); }} />
        <Text style={styles.muted}>Page {offset / pageSize + 1}</Text>
        <Button title="Next" disabled={items.length < pageSize || loading} onPress={() => { setItems([]); setOffset(offset + pageSize); }} />
      </View>
    </Page>
  );

  const pending = detail?.messages.some((m) => m.status === "pending") || false;
  const boundSignal = detail?.conversation.signal;
  return (
    <KeyboardAvoidingView style={styles.page} behavior={Platform.OS === "ios" ? "padding" : "height"}>
      <View style={s.header}>
        <Pressable accessibilityRole="button" onPress={() => select(null)}><Text style={s.link}>‹ Conversations</Text></Pressable>
        <Text style={styles.heading}>{detail?.conversation.symbol || "Loading…"} chat</Text>
        <Pressable accessibilityRole="button" accessibilityLabel="Delete conversation" disabled={busy || pending} onPress={() => Alert.alert("Delete conversation?", "This removes its saved messages.", [{ text: "Cancel", style: "cancel" }, { text: "Delete", style: "destructive", onPress: () => void remove() }])}><Text style={[styles.muted, (busy || pending) && { opacity: 0.4 }]}>Delete</Text></Pressable>
      </View>
      <View style={s.chart}>
        {boundSignal && <Text style={styles.warning}>Fixed signal · {boundSignal.strategy} · {formatTime(boundSignal.time)} · dated chart {detail?.conversation.chart_start ? formatTime(detail.conversation.chart_start) : "unavailable"} – {detail?.conversation.chart_end ? formatTime(detail.conversation.chart_end) : "unavailable"}</Text>}
        <View style={styles.row}>
          <View style={styles.wrap}>{(["5m", "1h", "1D"] as const).map((value) => <Pressable key={value} accessibilityRole="button" disabled={busy || pending || !!boundSignal} accessibilityState={{ selected: (boundSignal?.timeframe || timeframe) === value, disabled: busy || pending || !!boundSignal }} onPress={() => { if (value !== timeframe) { setChart(null); setChartError(""); setTimeframe(value); } }} style={[s.timeframe, (boundSignal?.timeframe || timeframe) === value && { borderColor: c.accent }]}><Text style={styles.muted}>{value}</Text></Pressable>)}</View>
          {chart && <View style={styles.row}><Text style={styles.text}>{formatPrice(chart.bars.at(-1)?.close)}</Text><FeedBadge feed={chart.provenance.feed} /></View>}
        </View>
        {chart ? <>
          <NativeChart key={`${selectedId}:${timeframe}`} data={chart} height={keyboardOpen ? 100 : 185} onSignal={() => {}} />
          <Text numberOfLines={1} style={chart.provenance.stale || chart.provenance.synthetic || chartError ? styles.warning : styles.muted}>
            {chart.provenance.synthetic ? "Synthetic fixture · " : ""}{chart.provenance.stale || chartError ? "Stale / last-known · " : ""}{chart.provenance.provider} · {chart.bars.length ? formatTime(chart.bars[chart.bars.length - 1].time) : "No bars available"}
          </Text>
          <ExternalLink url="https://www.tradingview.com/" label="TradingView Lightweight Charts™" />
        </> : <View style={{ height: keyboardOpen ? 60 : 150, justifyContent: "center" }}><Text style={styles.muted}>{loading ? "Loading stock chart…" : "Chart unavailable. You can still read the conversation."}</Text></View>}
        {!!chartError && <Text numberOfLines={2} style={styles.warning}>{chartError}</Text>}
      </View>
      <ScrollView ref={transcript} style={s.messages} contentContainerStyle={s.messageContent} keyboardShouldPersistTaps="handled" onContentSizeChange={() => transcript.current?.scrollToEnd({ animated: false })}>
        {detail && <View style={{ gap: 8 }}>
          <Text style={styles.heading}>{detail.conversation.title}</Text>
          <Input accessibilityLabel="Conversation title" value={title} onChangeText={setTitle} placeholder="New conversation title" maxLength={100} />
          <View style={styles.wrap}>
            <Button title="Rename" disabled={busy || pending || !title.trim()} onPress={() => void updateConversation("rename")} />
            <Button title="Summarize history" disabled={busy || pending || !detail.messages.length} onPress={() => void updateConversation("summary")} />
          </View>
          {detail.conversation.summary && <Card><Text style={styles.heading}>Conversation history summary</Text><Text style={styles.warning}>Earlier conversation text; not current evidence. {detail.conversation.summary_at}</Text><Text selectable style={styles.text}>{detail.conversation.summary}</Text></Card>}
        </View>}
        {detail && !detail.messages.length && <Text style={styles.muted}>Ask a question about {detail.conversation.symbol}. Follow-up questions use this conversation’s earlier messages. Start another conversation to discuss a different stock.</Text>}
        {detail?.messages.map((message) => <View key={message.id} style={[s.message, message.role === "user" && s.user]}>
          <Text style={styles.muted}>{message.role === "user" ? "You" : message.mode === "local" ? "Assistant · local explanation" : "Assistant"} · {new Date(message.created_at).toLocaleTimeString()}{message.cost_usd > 0 ? ` · $${message.cost_usd.toFixed(4)}` : ""}</Text>
          <ResearchMarkdown text={message.message} citations={message.citations} />
          {message.status === "pending" && <Text style={styles.warning}>{message.phase === "generating" ? "Generating response…" : "Retrieving research context…"}</Text>}
          {message.status === "failed" && <Text style={styles.warning}>{message.error || "Response failed. You can retry your question."}</Text>}
        </View>)}
        {busy && <Text style={styles.muted}>Waiting for the assistant…</Text>}
      </ScrollView>
      <View style={s.composer}>
        {(busy || pending || paused) && <><Button title={paused ? "Resume display" : "Stop display"} onPress={toggleDisplay} /><Text style={styles.muted}>{paused ? "Display paused. " : ""}Stopping display does not cancel the provider request or its cost.</Text></>}
        {!!error && <Text accessibilityRole="alert" numberOfLines={3} style={styles.warning}>{error}</Text>}
        <View style={s.composeRow}>
          <Input accessibilityLabel="Message assistant" placeholder={detail ? `Ask about ${detail.conversation.symbol}…` : "Loading conversation…"} multiline value={draft} onChangeText={setDraft} maxLength={4000} editable={!!detail && !busy && !pending} style={s.input} />
          <Button title={busy || pending ? "Waiting…" : "Send"} disabled={!detail || busy || pending || !draft.trim()} onPress={() => void send()} />
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  header: { padding: 12, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  link: { color: c.accent, fontSize: 13 },
  chart: { paddingHorizontal: 12, paddingBottom: 8, gap: 5, borderBottomColor: c.border, borderBottomWidth: 1 },
  timeframe: { borderColor: c.border, borderWidth: 1, borderRadius: 7, paddingHorizontal: 10, paddingVertical: 5 },
  messages: { flex: 1 },
  messageContent: { padding: 12, gap: 12 },
  message: { backgroundColor: c.surface, borderRadius: 12, padding: 12, gap: 7, borderColor: c.border, borderWidth: 1 },
  user: { marginLeft: 20, backgroundColor: c.raised },
  composer: { padding: 10, borderTopColor: c.border, borderTopWidth: 1, gap: 6 },
  composeRow: { flexDirection: "row", alignItems: "flex-end", gap: 8 },
  input: { flex: 1, minHeight: 48, maxHeight: 110, padding: 10 },
});
