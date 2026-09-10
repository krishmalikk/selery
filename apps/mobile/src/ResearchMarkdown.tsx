import React, { useState } from 'react';
import { Linking, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { parseResearchMarkdown, safeResearchUrl, type Citation, type ResearchInline } from '@selery/shared';
import { Button, ExternalLink, FeedBadge, c, styles } from './ui';

export function ResearchMarkdown({ text, citations = [] }: { text: string; citations?: Citation[] }) {
  const [evidence, setEvidence] = useState<Citation | null>(null);
  function spans(items: ResearchInline[]) {
    return items.map((span, i) => {
      if (span.type === 'citation') return <Text key={i} accessibilityRole={span.known ? 'button' : undefined}
        accessibilityLabel={span.known ? `Open source ${span.id}` : `Unknown source ${span.id}`}
        onPress={span.known ? () => setEvidence(citations.find((item) => item.data_id === span.id) ?? null) : undefined}
        style={{ color: span.known ? c.accent : c.warning }}>{span.text}{!span.known ? ' (unknown source)' : ''}</Text>;
      if (span.type === 'link') return <Text key={i} accessibilityRole="link" style={{ color: c.accent }}
        onPress={() => { const url = safeResearchUrl(span.url); if (url) void Linking.openURL(url).catch(() => {}); }}>{span.text}</Text>;
      return <Text key={i} style={span.type === 'strong' ? { fontWeight: '700' } : span.type === 'emphasis' ? { fontStyle: 'italic' } : span.type === 'code' ? { fontFamily: 'JetBrainsMono_400Regular', backgroundColor: c.raised } : undefined}>{span.text}</Text>;
    });
  }
  return <View style={{ gap: 8 }}>
    {parseResearchMarkdown(text, citations).map((block, i) => block.type === 'code'
      ? <Text selectable key={i} style={[styles.text, { fontFamily: 'JetBrainsMono_400Regular', backgroundColor: c.raised, padding: 8 }]}>{block.text}</Text>
      : block.type === 'list' ? <View key={i} style={{ gap: 4 }}>{block.items.map((item, j) => <Text selectable key={j} style={styles.text}>{block.ordered ? `${j + 1}.` : '•'} {spans(item)}</Text>)}</View>
      : <Text selectable key={i} style={[styles.text, block.type === 'heading' && { fontSize: 18, fontWeight: '700' }, block.type === 'quote' && { borderLeftWidth: 2, borderLeftColor: c.accent, paddingLeft: 8 }]}>{spans(block.spans)}</Text>)}
    {citations.length > 0 && <View style={{ gap: 5 }}>{citations.map((citation, i) => <Pressable key={`${citation.data_id}:${i}`} accessibilityRole="button" onPress={() => setEvidence(citation)}><Text style={styles.muted}>Source: <Text style={{ color: c.accent }}>{citation.label}</Text></Text></Pressable>)}</View>}
    <Modal visible={!!evidence} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setEvidence(null)}>
      <ScrollView style={styles.page} contentContainerStyle={styles.content}>
        {evidence && <>
          <Text style={styles.title}>Supporting evidence</Text>
          <Text style={styles.heading}>{evidence.label}</Text>
          <Text selectable style={styles.muted}>{evidence.data_id || 'Source identifier unavailable'}</Text>
          <Text style={styles.text}>Provider: {evidence.provider || 'Unavailable'}</Text>
          {evidence.feed ? <FeedBadge feed={evidence.feed} /> : <Text style={styles.muted}>Feed unavailable</Text>}
          <Text style={styles.text}>Observed: {evidence.timestamp || 'Unavailable'}</Text>
          <Text style={styles.text}>Available: {evidence.available_at || 'Unavailable'}</Text>
          <Text selectable style={styles.text}>{evidence.observation || 'Supporting observation unavailable.'}</Text>
          {evidence.url && safeResearchUrl(evidence.url) && <ExternalLink url={safeResearchUrl(evidence.url)!} label="Open original source" />}
          <Button title="Close evidence" onPress={() => setEvidence(null)} />
        </>}
      </ScrollView>
    </Modal>
  </View>;
}
