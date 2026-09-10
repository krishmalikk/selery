import React, { useCallback, useState } from "react";
import { Text } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { feedLabel } from "@selery/shared";
import { useSession } from "../../src/session";
import { NativeChart } from "../../src/NativeChart";
import { Page, Card, Button, ExternalLink, styles } from "../../src/ui";
import { usePublicResource, PublicStatus, PublicSourceLink, publicTime, publicNumber, sourceNames, activityStatus, instrumentNames } from "../../src/public-traders";

export default function PublicActivityDetail() {
  const params = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { client } = useSession(), router = useRouter();
  const resource = usePublicResource(useCallback(() => id ? client.publicActivityDetail(id) : Promise.reject(new Error("Missing public activity reference")), [client, id]));
  const [marker, setMarker] = useState("");
  const detail = resource.data, activity = detail?.activity;
  return <Page title="Public activity research" refresh={resource.refresh} loading={resource.loading}>
    <Button title="Back to public traders" onPress={() => router.canGoBack() ? router.back() : router.replace("/traders")} />
    <PublicStatus {...resource} />
    {detail && activity && <>
      <Card>
        <Text style={styles.heading}>{activity.symbol || activity.instrument_name || "Unidentified instrument"}</Text>
        <Text style={styles.text}>{detail.trader.display_name} · {sourceNames[activity.source]}</Text>
        <Text style={styles.muted}>{instrumentNames[activity.instrument_kind]} · {activity.direction} · {activityStatus[activity.status]}</Text>
        {activity.synthetic && <Text style={styles.warning}>Synthetic fixture. This is not a real person’s trading activity.</Text>}
        {activity.stale && <Text style={styles.warning}>Stale public observation. It may no longer describe the trader’s published activity.</Text>}
        <Text style={styles.muted}>Verification: {activity.verification} · Revision {activity.revision}</Text>
        <Text style={styles.text}>Entry price: {publicNumber(activity.entry_price)}{"\n"}Published allocation: {activity.allocation_percent === null ? "Unavailable" : `${publicNumber(activity.allocation_percent)}%`}{"\n"}Quantity: {publicNumber(activity.quantity)}{"\n"}Exit price: {publicNumber(activity.exit_price)}</Text>
        <Text style={styles.muted}>Opened: {publicTime(activity.opened_at)}{"\n"}Published: {publicTime(activity.published_at)}{"\n"}Provider updated: {publicTime(activity.provider_updated_at)}{"\n"}First observed by SELERY: {publicTime(activity.first_observed_at)}{"\n"}Last observed by SELERY: {publicTime(activity.observed_at)}</Text>
        <Text style={styles.warning}>An open record disappearing does not establish a sale. The trader’s motive is unknown.</Text>
        {activity.limitations.map((note, i) => <Text key={i} style={styles.warning}>{note}</Text>)}
        {!activity.synthetic && <PublicSourceLink source={activity.source} url={activity.source_url} label="View source record" />}
      </Card>
      <Card>
        <Text style={styles.heading}>Dated market context</Text>
        <Text style={styles.muted}>{detail.market_context_reason}</Text>
        <Text style={styles.text}>IEX reference price movement: {detail.reference_move_percent === null ? "Unavailable" : `${publicNumber(detail.reference_move_percent)}%`}</Text>
        <Text style={styles.muted}>This comparison is not the trader’s realized return.</Text>
        {detail.chart && <>
          <Text style={styles.muted}>{detail.chart.symbol} · {detail.chart.timeframe} · {feedLabel(detail.chart.provenance.feed)}{"\n"}Market observed: {publicTime(detail.chart.provenance.observed_at)}{"\n"}Available: {publicTime(detail.chart.provenance.available_at)}</Text>
          {detail.chart.provenance.synthetic && <Text style={styles.warning}>Synthetic chart data</Text>}
          {detail.chart.provenance.stale && <Text style={styles.warning}>Stale market data</Text>}
          <NativeChart data={detail.chart} onSignal={(signal) => setMarker(`${signal.strategy} · ${signal.direction}`)} />
          {!!marker && <Text style={styles.muted}>{marker}</Text>}
          <ExternalLink url="https://www.tradingview.com/" label="Charts by TradingView" />
          {detail.chart.provenance.feed === "iex" && <Text style={styles.warning}>IEX only · Volume research: needs SIP data.</Text>}
        </>}
      </Card>
      <Button title="Ask about this trade" onPress={() => router.push({ pathname: "/chat", params: { activity_id: activity.id, symbol: activity.symbol || "SPY" } })} />
      <Text style={styles.muted}>{detail.llm_allowed ? "AI analysis depends on the server’s enabled model and remaining monthly cap." : "Provider data is not permitted for LLM analysis. Only a local research explanation is available."}</Text>
    </>}
  </Page>;
}
