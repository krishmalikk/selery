import React, { useCallback } from "react";
import { Text } from "react-native";
import { useRouter } from "expo-router";
import { AlertListSchema, formatTime } from "@selery/shared";
import { useSession } from "../../src/session";
import { useResource } from "../../src/resource";
import { Page, Card, Button, ResourceStatus, styles } from "../../src/ui";
const schema = AlertListSchema;
export default function Alerts() {
  const { client } = useSession(),
    router = useRouter();
  const fetcher = useCallback(() => client.alerts(), [client]);
  const r = useResource("alerts", fetcher, schema);
  return (
    <Page title="Research alerts" refresh={r.refresh} loading={r.loading}>
      <ResourceStatus {...r} />
      {r.data?.length === 0 && (
        <Card>
          <Text style={styles.heading}>All quiet</Text>
          <Text style={styles.muted}>
            Signal and research updates appear here. Push setup is available in
            Settings.
          </Text>
        </Card>
      )}
      {r.data?.map((alert) => (
        <Card key={alert.id}>
          <Text style={styles.heading}>
            {alert.read ? "" : "• "}
            {alert.title}
          </Text>
          <Text style={styles.text}>{alert.body}</Text>
          <Text style={styles.muted}>{formatTime(alert.created_at)}</Text>
          {alert.symbol && (
            <Button
              title={`Open ${alert.symbol} research`}
              onPress={() =>
                router.navigate({
                  pathname: "/chart",
                  params: {
                    symbol: alert.symbol!,
                    ...(alert.signal_id ? { signal: alert.signal_id } : {}),
                  },
                })
              }
            />
          )}
          {!alert.read && (
            <Button
              title="Mark read"
              onPress={() => {
                void client
                  .readAlert(alert.id)
                  .then(() => r.refresh())
                  .catch(() => r.refresh());
              }}
            />
          )}
        </Card>
      ))}
    </Page>
  );
}
