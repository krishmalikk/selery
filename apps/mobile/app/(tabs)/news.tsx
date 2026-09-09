import React, { useCallback } from "react";
import { Text } from "react-native";
import { NewsResponseSchema, formatTime } from "@selery/shared";
import { useSession } from "../../src/session";
import { useResource } from "../../src/resource";
import { Page, Card, ResourceStatus, ExternalLink, styles } from "../../src/ui";
export default function News() {
  const { client } = useSession();
  const fetcher = useCallback(() => client.news(), [client]);
  const r = useResource("news", fetcher, NewsResponseSchema);
  return (
    <Page title="News & context" refresh={r.refresh} loading={r.loading}>
      <ResourceStatus {...r} />
      {r.data?.stale && (
        <Text style={styles.warning}>Historical / stale news sample</Text>
      )}
      {r.data?.items.map((item) => (
        <Card key={item.id}>
          <Text style={styles.muted}>
            {item.source} · {formatTime(item.published_at)}
          </Text>
          <Text style={styles.heading}>{item.headline}</Text>
          <Text style={styles.text}>{item.summary}</Text>
          <Text style={styles.muted}>
            {item.symbols.join(" · ")}
            {item.sentiment === null
              ? " · Sentiment unavailable"
              : ` · Sentiment ${item.sentiment.toFixed(2)} (${item.sentiment_method})`}
          </Text>
          <ExternalLink url={item.url} label="Read source" />
        </Card>
      ))}
      {r.data?.items.length === 0 && (
        <Text style={styles.muted}>No news available.</Text>
      )}
    </Page>
  );
}
