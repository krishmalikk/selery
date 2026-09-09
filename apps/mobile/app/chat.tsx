import React, { useState } from "react";
import { Text } from "react-native";
import { useRouter } from "expo-router";
import { type ChatResponse } from "@selery/shared";
import { useSession } from "../src/session";
import { Page, Card, Input, Button, ExternalLink, styles } from "../src/ui";
export default function Chat() {
  const { client } = useSession(),
    router = useRouter();
  const [question, setQuestion] = useState(""),
    [symbol, setSymbol] = useState("SPY"),
    [response, setResponse] = useState<ChatResponse | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <Page title="Research assistant">
      <Button title="Back to workspace" onPress={() => router.back()} />
      <Text style={styles.muted}>
        Ask about available data and research. Responses do not create journal
        entries.
      </Text>
      <Input
        placeholder="Symbol"
        value={symbol}
        onChangeText={setSymbol}
        autoCapitalize="characters"
      />
      <Input
        placeholder="Ask a research question…"
        multiline
        value={question}
        onChangeText={setQuestion}
      />
      <Button
        title={busy ? "Analyzing…" : "Ask"}
        disabled={busy || !question.trim()}
        onPress={() => {
          setBusy(true);
          setError("");
          client
            .chat({
              message: question,
              symbol: symbol.toUpperCase(),
              debate: false,
            })
            .then(setResponse)
            .catch((e) => setError(e.message))
            .finally(() => setBusy(false));
        }}
      />
      {!!error && <Text style={styles.warning}>{error}</Text>}
      {response && (
        <Card>
          <Text style={styles.muted}>
            {response.mode === "local"
              ? "Local explanation"
              : "LLM explanation"}{" "}
            · ${response.cost_usd.toFixed(4)}
          </Text>
          <Text style={styles.text}>{response.message}</Text>
          {response.citations.map((citation, i) =>
            citation.url ? (
              <ExternalLink key={i} url={citation.url} label={citation.label} />
            ) : (
              <Text key={i} style={styles.muted}>
                {citation.label} · {citation.timestamp} · {citation.data_id}
              </Text>
            ),
          )}
        </Card>
      )}
    </Page>
  );
}
