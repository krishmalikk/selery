import React, { useCallback, useState } from "react";
import { Text } from "react-native";
import { z } from "zod";
import { JournalEntrySchema, formatTime } from "@selery/shared";
import { useSession } from "../../src/session";
import { useResource } from "../../src/resource";
import {
  Page,
  Card,
  Button,
  Input,
  ResourceStatus,
  styles,
} from "../../src/ui";
const schema = z.array(JournalEntrySchema);
export default function Journal() {
  const { client } = useSession();
  const fetcher = useCallback(() => client.journal(), [client]);
  const r = useResource("journal", fetcher, schema);
  const [symbol, setSymbol] = useState("SPY"),
    [thesis, setThesis] = useState(""),
    [outcome, setOutcome] = useState(""),
    [reflection, setReflection] = useState(""),
    [message, setMessage] = useState(""),
    [saving, setSaving] = useState(false);
  async function save() {
    setSaving(true);
    setMessage("");
    try {
      await client.saveJournal({
        symbol: symbol.toUpperCase().trim(),
        thesis,
        outcome,
        reflection,
      });
      setThesis("");
      setOutcome("");
      setReflection("");
      setMessage("Entry saved.");
      await r.refresh();
    } catch (e) {
      setMessage(
        e instanceof Error
          ? e.message
          : "Save failed; your draft is still here.",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <Page title="Research journal" refresh={r.refresh} loading={r.loading}>
      <Text style={styles.muted}>
        Your observations and reflections. Entries change only when you tap Save
        entry.
      </Text>
      <Card>
        <Input
          accessibilityLabel="Symbol"
          placeholder="Symbol"
          value={symbol}
          onChangeText={setSymbol}
          autoCapitalize="characters"
        />
        <Input
          accessibilityLabel="Thesis"
          placeholder="What are you researching?"
          multiline
          value={thesis}
          onChangeText={setThesis}
        />
        <Input
          accessibilityLabel="Observed outcome"
          placeholder="Observed outcome (optional)"
          multiline
          value={outcome}
          onChangeText={setOutcome}
        />
        <Input
          accessibilityLabel="Reflection"
          placeholder="Reflection (optional)"
          multiline
          value={reflection}
          onChangeText={setReflection}
        />
        <Button
          title={saving ? "Saving…" : "Save entry"}
          disabled={saving || !symbol.trim() || !thesis.trim()}
          onPress={() => void save()}
        />
        {!!message && (
          <Text accessibilityRole="alert" style={styles.warning}>
            {message}
          </Text>
        )}
      </Card>
      <ResourceStatus {...r} />
      {r.data?.map((entry, index) => (
        <Card key={entry.id || index}>
          <Text style={styles.heading}>{entry.symbol}</Text>
          <Text style={styles.text}>{entry.thesis}</Text>
          {!!entry.outcome && (
            <Text style={styles.text}>Observed outcome: {entry.outcome}</Text>
          )}
          {!!entry.reflection && (
            <Text style={styles.muted}>Reflection: {entry.reflection}</Text>
          )}
          <Text style={styles.muted}>
            {entry.created_at ? formatTime(entry.created_at) : ""}
          </Text>
        </Card>
      ))}
    </Page>
  );
}
