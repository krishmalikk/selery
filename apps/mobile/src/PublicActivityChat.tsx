import React, { useCallback, useRef, useState } from "react";
import { AppState, Text } from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { type ChatResponse } from "@selery/shared";
import { useSession } from "./session";
import { Page, Card, Input, Button, ExternalLink, styles } from "./ui";
export function PublicActivityChat() {
  const params = useLocalSearchParams<{ activity_id?: string | string[]; symbol?: string | string[] }>();
  const activityId = Array.isArray(params.activity_id) ? params.activity_id[0] : params.activity_id;
  const initialSymbol = Array.isArray(params.symbol) ? params.symbol[0] : params.symbol;
  const { client } = useSession(),
    router = useRouter();
  const [question, setQuestion] = useState(""),
    [symbol, setSymbol] = useState(initialSymbol || "SPY"),
    [response, setResponse] = useState<ChatResponse | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const requestGeneration = useRef(0);
  useFocusEffect(useCallback(() => {
    if (!activityId) return;
    const clear = () => { requestGeneration.current++; setResponse(null); setQuestion(""); setError(""); setBusy(false); };
    clear();
    setSymbol(initialSymbol || "SPY");
    const subscription = AppState.addEventListener("change", (state) => { if (state !== "active") clear(); });
    return () => { clear(); subscription.remove(); };
  }, [activityId, initialSymbol, client]));
  return (
    <Page title="Research assistant">
      <Button title="Back to workspace" onPress={() => router.back()} />
      <Text style={styles.muted}>
        Ask about available data and research. Responses do not create journal
        entries.
      </Text>
      {!!activityId && <Text style={styles.warning}>This question uses the selected public activity as evidence. Missing exits and the trader’s motive remain unknown.</Text>}
      {!activityId && <Input
        placeholder="Symbol"
        value={symbol}
        onChangeText={setSymbol}
        autoCapitalize="characters"
      />}
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
          const generation = ++requestGeneration.current;
          client
            .chat({
              message: question,
              symbol: symbol.toUpperCase(),
              debate: false,
              activity_id: activityId || null,
            })
            .then((value) => { if (generation === requestGeneration.current) setResponse(value); })
            .catch((e) => { if (generation === requestGeneration.current) setError(e.message); })
            .finally(() => { if (generation === requestGeneration.current) setBusy(false); });
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
