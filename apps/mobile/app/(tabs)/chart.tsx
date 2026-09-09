import React, { useCallback, useEffect, useState } from "react";
import { View, Text, Pressable, Modal, ScrollView } from "react-native";
import { useLocalSearchParams } from "expo-router";
import {
  ChartResponseSchema,
  formatPrice,
  formatTime,
  watchlist,
  type Signal,
  type Timeframe,
} from "@selery/shared";
import { useSession } from "../../src/session";
import { useResource } from "../../src/resource";
import { NativeChart } from "../../src/NativeChart";
import {
  Page,
  Card,
  ResourceStatus,
  FeedBadge,
  Button,
  ExternalLink,
  styles,
  c,
} from "../../src/ui";
export default function Chart() {
  const params = useLocalSearchParams<{ symbol?: string; signal?: string }>();
  const [symbol, setSymbol] = useState(params.symbol || "SPY"),
    [timeframe, setTimeframe] = useState<Timeframe>("5m"),
    [selected, setSelected] = useState<Signal | null>(null);
  const { client } = useSession();
  useEffect(() => {
    if (params.symbol) setSymbol(params.symbol.toUpperCase());
  }, [params.symbol]);
  const fetcher = useCallback(
    () => client.chart(symbol, timeframe, "iex"),
    [client, symbol, timeframe],
  );
  const r = useResource(
    `chart:${symbol}:${timeframe}:iex`,
    fetcher,
    ChartResponseSchema,
  );
  useEffect(() => {
    if (params.signal && r.data) {
      setSelected(r.data.signals.find((s) => s.id === params.signal) || null);
    }
  }, [params.signal, r.data]);
  return (
    <Page title={symbol + " research"} refresh={r.refresh} loading={r.loading}>
      <View style={styles.wrap}>
        {watchlist.map((s) => (
          <Pressable
            key={s}
            onPress={() => setSymbol(s)}
            style={[
              styles.card,
              {
                padding: 10,
                backgroundColor: s === symbol ? c.raised : c.surface,
              },
            ]}
          >
            <Text style={styles.text}>{s}</Text>
          </Pressable>
        ))}
      </View>
      <View style={styles.wrap}>
        {(["5m", "1h", "1D"] as const).map((t) => (
          <Pressable
            key={t}
            onPress={() => setTimeframe(t)}
            style={[
              styles.card,
              {
                padding: 10,
                borderColor: t === timeframe ? c.accent : c.border,
              },
            ]}
          >
            <Text style={styles.text}>{t}</Text>
          </Pressable>
        ))}
      </View>
      <ResourceStatus {...r} />
      {r.data && (
        <>
          <View style={styles.row}>
            <Text style={styles.mono}>
              {formatPrice(r.data.bars.at(-1)?.close)}
            </Text>
            <FeedBadge feed={r.data.provenance.feed} />
          </View>
          <Text style={styles.warning}>
            {r.data.provenance.synthetic ? "Synthetic fixture · " : ""}
            {r.data.provenance.stale ? "Stale historical data · " : ""}
            {r.data.provenance.provider}
          </Text>
          <NativeChart data={r.data} onSignal={setSelected} />
          <Text style={styles.muted}>
            EMA 9 · EMA 21 · RSI 14. Pinch to zoom, drag to pan, hold to inspect
            a signal.
          </Text>
          <ExternalLink
            url="https://www.tradingview.com/"
            label="Charts powered by TradingView Lightweight Charts™"
          />
          <Text style={styles.muted}>
            Volume: {r.data.bars.at(-1)?.volume.toLocaleString() ?? "—"} ·{" "}
            {r.data.provenance.feed === "iex"
              ? "IEX only"
              : r.data.provenance.feed}
          </Text>
          <Card>
            <Text style={styles.heading}>Data capabilities</Text>
            {r.data.capabilities
              .filter((cap) => !cap.enabled)
              .map((cap) => (
                <Text key={cap.id} style={styles.warning}>
                  {cap.label} · {cap.reason || "needs SIP data"}
                </Text>
              ))}
          </Card>
          <Text style={styles.heading}>Research signals</Text>
          {r.data.signals.length === 0 && (
            <Text style={styles.muted}>No signals in this window.</Text>
          )}
          {r.data.signals
            .slice(-12)
            .reverse()
            .map((signal) => (
              <Pressable key={signal.id} onPress={() => setSelected(signal)}>
                <Card>
                  <View style={styles.row}>
                    <Text style={styles.heading}>
                      {signal.direction} · {signal.strategy}
                    </Text>
                    <FeedBadge feed={signal.feed} />
                  </View>
                  <Text style={styles.muted}>
                    {formatTime(signal.time)} ·{" "}
                    {formatPrice(signal.reference_price)}
                  </Text>
                </Card>
              </Pressable>
            ))}
        </>
      )}
      <Modal
        visible={!!selected}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setSelected(null)}
      >
        <ScrollView style={styles.page} contentContainerStyle={styles.content}>
          {selected && (
            <>
              <Text style={styles.title}>
                {selected.symbol} · {selected.direction}
              </Text>
              <FeedBadge feed={selected.feed} />
              <Text style={styles.text}>{selected.explanation}</Text>
              <Text style={styles.muted}>
                {selected.strategy} v{selected.strategy_version} ·{" "}
                {formatTime(selected.time)}
              </Text>
              <Card>
                <Text style={styles.text}>
                  Reference {formatPrice(selected.reference_price)}
                </Text>
                <Text style={styles.text}>
                  Analytical stop {formatPrice(selected.stop)}
                </Text>
                <Text style={styles.text}>
                  Analytical target {formatPrice(selected.target)}
                </Text>
                <Text style={styles.text}>
                  Horizon {selected.horizon_bars} bars
                </Text>
                <Text style={styles.warning}>
                  {selected.confidence === null
                    ? selected.confidence_reason ||
                      "Confidence unavailable until calibrated"
                    : `Calibrated confidence ${(selected.confidence * 100).toFixed(1)}%`}
                </Text>
              </Card>
              <Button title="Close detail" onPress={() => setSelected(null)} />
            </>
          )}
        </ScrollView>
      </Modal>
    </Page>
  );
}
