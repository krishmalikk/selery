import React, { useCallback, useEffect } from "react";
import { Text, View, Pressable } from "react-native";
import { useRouter } from "expo-router";
import {
  WatchlistResponseSchema,
  formatPrice,
  formatPercent,
  formatTime,
} from "@selery/shared";
import { useSession } from "../../src/session";
import { useResource } from "../../src/resource";
import { useStream } from "../../src/stream";
import type { StreamEvent } from "@selery/shared";
import { Page, Card, ResourceStatus, FeedBadge, styles, c } from "../../src/ui";
export default function Watchlist() {
  const { client } = useSession(),
    router = useRouter();
  const fetcher = useCallback(() => client.watchlist(), [client]);
  const r = useResource("watchlist", fetcher, WatchlistResponseSchema);
  const onStream = useCallback(
    (event: StreamEvent) => {
      if (event.type === "quotes") void r.refresh();
    },
    [r.refresh],
  );
  const streamStatus = useStream(onStream);
  useEffect(() => {
    const timer = setInterval(() => void r.refresh(), 30000);
    return () => clearInterval(timer);
  }, [r.refresh]);
  return (
    <Page title="Market overview" refresh={r.refresh} loading={r.loading}>
      <Text style={styles.muted}>SELERY / PERSONAL RESEARCH</Text>
      <Text style={styles.muted}>{streamStatus}</Text>
      <ResourceStatus {...r} />
      {r.data && (
        <Text style={styles.warning}>
          {r.data.data_mode === "fixtures"
            ? "Fixture mode · historical sample, not current market prices"
            : "Market data · research only"}
        </Text>
      )}
      {r.data?.quotes.map((q) => (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Open ${q.symbol} chart`}
          key={q.symbol}
          onPress={() =>
            router.navigate({
              pathname: "/chart",
              params: { symbol: q.symbol },
            })
          }
        >
          <Card>
            <View style={styles.row}>
              <Text style={styles.heading}>{q.symbol}</Text>
              <FeedBadge feed={q.provenance.feed} />
            </View>
            <View style={styles.row}>
              <Text style={styles.mono}>{formatPrice(q.price)}</Text>
              <Text
                style={{
                  color: (q.change_percent ?? 0) >= 0 ? c.accent : c.negative,
                }}
              >
                {formatPercent(q.change_percent)}
              </Text>
            </View>
            <Text style={styles.muted}>
              {q.provenance.provider} · {formatTime(q.provenance.observed_at)}
              {q.provenance.synthetic ? " · synthetic" : ""}
              {q.provenance.stale ? " · stale" : ""}
            </Text>
            <Text style={styles.muted}>
              View price action and research signals →
            </Text>
          </Card>
        </Pressable>
      ))}
    </Page>
  );
}
