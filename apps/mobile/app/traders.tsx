import React, { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useRouter } from "expo-router";
import type { PublicActivity } from "@selery/shared";
import { useSession } from "../src/session";
import { Page, Card, Button, Input, styles } from "../src/ui";
import { usePublicResource, PublicStatus, PublicSourceLink, publicTime, publicNumber, sourceNames, activityStatus, instrumentNames } from "../src/public-traders";

const limit = 12;
export default function Traders() {
  const { client } = useSession(), router = useRouter();
  const [draft, setDraft] = useState(""), [q, setQ] = useState("");
  const [symbolDraft, setSymbolDraft] = useState(""), [fromDraft, setFromDraft] = useState(""), [toDraft, setToDraft] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [source, setSource] = useState<PublicActivity["source"] | "">("");
  const [traderId, setTraderId] = useState("");
  const [traderOffset, setTraderOffset] = useState(0), [activityOffset, setActivityOffset] = useState(0);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const sources = usePublicResource(useCallback(() => client.publicSources(), [client]));
  const traders = usePublicResource(useCallback(() => client.publicTraders({ q, ...(source ? { source } : {}), limit, offset: traderOffset }), [client, q, source, traderOffset]));
  const activities = usePublicResource(useCallback(() => client.publicActivity({ q, ...(source ? { source } : {}), ...filters, ...(traderId ? { trader_id: traderId } : {}), limit, offset: activityOffset }), [client, q, source, filters, traderId, activityOffset]));
  const reload = () => { void sources.refresh(); void traders.refresh(); void activities.refresh(); };
  const synchronize = async (id: string | null = null) => {
    setBusy(true); setMessage("");
    try { const result = await client.refreshPublicTraders(id); setMessage(result.message); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Refresh unavailable"); }
    finally { setBusy(false); reload(); }
  };
  return <Page title="Public Traders" refresh={reload} loading={sources.loading || traders.loading || activities.loading}>
    <Button title="Back to settings" onPress={() => router.back()} />
    <Text style={styles.muted}>Third-party public stock research. Published records may be delayed or incomplete. A disappearing open record does not establish a sale.</Text>
    <PublicStatus {...sources} />
    {sources.data?.map((item) => <Card key={item.id}>
      <Text style={styles.heading}>{item.name} · {item.status}</Text>
      <Text style={item.status === "verified" ? styles.muted : styles.warning}>{item.reason}</Text>
      <Text style={styles.muted}>Last checked: {publicTime(item.last_checked_at)} · AI analysis {item.llm_allowed ? "permitted" : "unavailable"}</Text>
    </Card>)}
    <Button title={busy ? "Refreshing sources…" : "Refresh public directory"} disabled={busy || !sources.data?.some((item) => item.can_refresh)} onPress={() => void synchronize()} />
    {!!message && <Text accessibilityRole="alert" style={styles.warning}>{message}</Text>}
    <Input accessibilityLabel="Search public traders and activity" placeholder="Search traders or symbols" value={draft} onChangeText={setDraft} returnKeyType="search" onSubmitEditing={() => { setQ(draft.trim()); setTraderOffset(0); setActivityOffset(0); setTraderId(""); }} />
    <Button title="Search" onPress={() => { setQ(draft.trim()); setTraderOffset(0); setActivityOffset(0); setTraderId(""); }} />
    <View style={styles.wrap}>{(["", "etoro", "kinfo", "afterhour"] as const).map((value) => <Button key={value} title={`${source === value ? "✓ " : ""}${value ? sourceNames[value] : "All sources"}`} onPress={() => { setSource(value); setTraderId(""); setTraderOffset(0); setActivityOffset(0); }} />)}</View>
    <Text style={styles.heading}>Traders</Text>
    <PublicStatus {...traders} />
    {traders.data?.items.map((trader) => <Card key={trader.id}>
      <Text style={styles.heading}>{trader.display_name}</Text>
      <Text style={styles.muted}>{sourceNames[trader.source]} · @{trader.username} · {trader.access}</Text>
      {(trader.synthetic || trader.stale) && <Text style={styles.warning}>{trader.synthetic ? "Synthetic fixture · not a real trader" : ""}{trader.synthetic && trader.stale ? " · " : ""}{trader.stale ? "Stale observation" : ""}</Text>}
      <Text style={styles.muted}>Observed: {publicTime(trader.observed_at)}</Text>
      <Text style={styles.muted}>{trader.statistics_note}</Text>
      {Object.entries(trader.statistics).map(([name, value]) => <Text key={name} style={styles.text}>{sourceNames[trader.source]} {name}: {publicNumber(value)}</Text>)}
      {!trader.synthetic && <PublicSourceLink source={trader.source} url={trader.source_url} label="View public profile" />}
      <Button title={traderId === trader.id ? "Showing this trader’s activity" : "View activity"} onPress={() => { setTraderId(trader.id); setQ(""); setDraft(""); setActivityOffset(0); }} />
      <Button title="Refresh this trader" disabled={busy || !sources.data?.find((item) => item.id === trader.source)?.can_refresh} onPress={() => void synchronize(trader.id)} />
    </Card>)}
    {traders.data && <>
      {!traders.data.items.length && <Text style={styles.muted}>No public traders match. Sources without authorized access remain pending.</Text>}
      <Text style={styles.muted}>{traders.data.total} traders · page {Math.floor(traderOffset / limit) + 1}</Text>
      <View style={styles.wrap}><Button title="Previous traders" disabled={traderOffset === 0} onPress={() => setTraderOffset(Math.max(0, traderOffset - limit))} /><Button title="Next traders" disabled={traderOffset + limit >= traders.data.total} onPress={() => setTraderOffset(traderOffset + limit)} /></View>
    </>}
    <Text style={styles.heading}>Public activity</Text>
    <Input accessibilityLabel="Activity symbol" placeholder="Symbol (optional)" autoCapitalize="characters" value={symbolDraft} onChangeText={setSymbolDraft} />
    <Input accessibilityLabel="Opened on or after UTC date" placeholder="Opened from: YYYY-MM-DD (UTC)" value={fromDraft} onChangeText={setFromDraft} autoCapitalize="none" />
    <Input accessibilityLabel="Opened on or before UTC date" placeholder="Opened through: YYYY-MM-DD (UTC)" value={toDraft} onChangeText={setToDraft} autoCapitalize="none" />
    <Button title="Apply activity filters" onPress={() => {
      const validDate = (value: string) => !value || (/^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value);
      const from = fromDraft.trim(), to = toDraft.trim();
      if (!validDate(from) || !validDate(to) || (from && to && from > to)) { setMessage("Use valid UTC dates in YYYY-MM-DD format, with the start no later than the end."); return; }
      setFilters({ ...(symbolDraft.trim() ? { symbol: symbolDraft.trim().toUpperCase() } : {}), ...(from ? { date_from: from } : {}), ...(to ? { date_to: to } : {}) });
      setActivityOffset(0); setMessage("");
    }} />
    {!!traderId && <Button title="Show activity from all traders" onPress={() => { setTraderId(""); setActivityOffset(0); }} />}
    <PublicStatus {...activities} />
    {activities.data?.items.map((item) => <Card key={item.id}>
      <Text style={styles.heading}>{item.symbol || item.instrument_name || "Unidentified instrument"} · {item.direction}</Text>
      <Text style={styles.muted}>{sourceNames[item.source]} · {instrumentNames[item.instrument_kind]} · {activityStatus[item.status]}</Text>
      {(item.synthetic || item.stale) && <Text style={styles.warning}>{item.synthetic ? "Synthetic fixture" : ""}{item.synthetic && item.stale ? " · " : ""}{item.stale ? "Stale observation" : ""}</Text>}
      <Text style={styles.text}>Entry price: {publicNumber(item.entry_price)}</Text>
      <Text style={styles.muted}>Opened: {publicTime(item.opened_at)}{"\n"}Observed: {publicTime(item.observed_at)}</Text>
      <Button title="View research details" onPress={() => router.push({ pathname: "/public-activity/[id]", params: { id: item.id } })} />
    </Card>)}
    {activities.data && <>
      {!activities.data.items.length && <Text style={styles.muted}>No published activity is available for these filters.</Text>}
      <Text style={styles.muted}>{activities.data.total} records · page {Math.floor(activityOffset / limit) + 1}</Text>
      <View style={styles.wrap}><Button title="Previous activity" disabled={activityOffset === 0} onPress={() => setActivityOffset(Math.max(0, activityOffset - limit))} /><Button title="Next activity" disabled={activityOffset + limit >= activities.data.total} onPress={() => setActivityOffset(activityOffset + limit)} /></View>
    </>}
  </Page>;
}
