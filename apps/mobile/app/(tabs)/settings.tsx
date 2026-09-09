import React, { useCallback, useState } from "react";
import { Text } from "react-native";
import { useRouter } from "expo-router";
import { SettingsSchema, feedLabel } from "@selery/shared";
import { useSession } from "../../src/session";
import { useResource } from "../../src/resource";
import { registerNotifications } from "../../src/notifications";
import { Page, Card, Button, ResourceStatus, styles } from "../../src/ui";
export default function Settings() {
  const { client, logout, endpoint } = useSession(),
    router = useRouter();
  const fetcher = useCallback(() => client.settings(), [client]);
  const r = useResource("settings", fetcher, SettingsSchema);
  const [push, setPush] = useState(""),
    [pushToken, setPushToken] = useState("");
  return (
    <Page title="Workspace settings" refresh={r.refresh} loading={r.loading}>
      <ResourceStatus {...r} />
      <Card>
        <Text style={styles.heading}>Connection</Text>
        <Text style={styles.muted}>{endpoint}</Text>
        <Text style={styles.text}>
          Mode: {r.data?.data_mode || "Unavailable"}
        </Text>
        <Text style={styles.text}>
          Feed: {r.data ? feedLabel(r.data.feed) : "Unavailable"}
        </Text>
        <Text style={styles.warning}>
          Volume-dependent research needs SIP data.
        </Text>
      </Card>
      <Card>
        <Text style={styles.heading}>Research assistant</Text>
        <Text style={styles.muted}>
          Read-only, source-linked explanations. LLM calls are disabled until
          server configuration allows a funded cap.
        </Text>
        <Text style={styles.text}>
          LLM: {r.data?.llm_enabled ? "Enabled" : "Disabled"} · Monthly cap $
          {r.data?.llm_monthly_cap_usd ?? 0}
        </Text>
        <Text style={styles.muted}>Spent: ${r.data?.llm_spent_usd ?? 0}</Text>
        <Button
          title="Ask about research"
          onPress={() => router.push("/chat")}
        />
      </Card>
      <Card>
        <Text style={styles.heading}>Notifications</Text>
        <Text style={styles.muted}>
          Requires a physical device, EAS development build, project ID and push
          credentials. Registration alone does not enable server delivery.
        </Text>
        <Button
          title="Register this device"
          onPress={() => {
            setPush("Registering…");
            registerNotifications()
              .then((token) => {
                setPushToken(token);
                setPush(
                  "Registered with Expo. Server delivery is not configured; use this token for an explicit test notification.",
                );
              })
              .catch((e) => setPush(e.message));
          }}
        />
        {!!push && <Text style={styles.warning}>{push}</Text>}
        {!!pushToken && (
          <Text selectable style={styles.muted}>
            {pushToken}
          </Text>
        )}
      </Card>
      <Button
        title="Sign out and clear cache"
        onPress={() => void logout().catch(() => {})}
      />
    </Page>
  );
}
