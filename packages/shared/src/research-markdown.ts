/** Restricted, platform-neutral Markdown. Render strings as text; never interpret HTML. */
export type ResearchInline =
  | { type: 'text' | 'strong' | 'emphasis' | 'code'; text: string }
  | { type: 'link'; text: string; url: string }
  | { type: 'citation'; text: string; id: string; known: boolean };
export type ResearchBlock =
  | { type: 'paragraph' | 'heading' | 'quote'; spans: ResearchInline[] }
  | { type: 'list'; ordered: boolean; items: ResearchInline[][] }
  | { type: 'code'; text: string };

export function safeResearchUrl(value: string): string | null {
  // Reject control characters, protocol-relative URLs, credentials and URL parser normalization tricks.
  if (!/^https?:\/\//i.test(value) || /[\s\\\u0000-\u001f\u007f]/.test(value)) return null;
  try {
    const url = new URL(value);
    return (url.protocol === 'https:' || url.protocol === 'http:') && !!url.hostname && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

function inline(text: string, known: Set<string>): ResearchInline[] {
  const spans: ResearchInline[] = [];
  // No HTML parser, images, embedded media, autolinks, or recursive parsing.
  const pattern = /`([^`\n]+)`|\*\*([^*\n]+)\*\*|__([^_\n]+)__|\*([^*\n]+)\*|_([^_\n]+)_|\[([^\]\n]+)\]\(([^)\n]*)\)|\[([^\]\n]+)\]/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index! > cursor) spans.push({ type: 'text', text: text.slice(cursor, match.index) });
    const [raw, code, strong, strongAlt, emphasis, emphasisAlt, label, href, id] = match;
    if (code !== undefined) spans.push({ type: 'code', text: code });
    else if (strong !== undefined || strongAlt !== undefined) spans.push({ type: 'strong', text: strong ?? strongAlt });
    else if (emphasis !== undefined || emphasisAlt !== undefined) spans.push({ type: 'emphasis', text: emphasis ?? emphasisAlt });
    else if (label !== undefined) {
      const url = safeResearchUrl(href);
      // Blocked links retain their label and an explicit warning, with no navigation target.
      spans.push(url ? { type: 'link', text: label, url } : { type: 'text', text: `${label} (unsafe link blocked)` });
    } else spans.push({ type: 'citation', text: `[${id}]`, id, known: known.has(id) });
    cursor = match.index! + raw.length;
  }
  if (cursor < text.length) spans.push({ type: 'text', text: text.slice(cursor) });
  return spans;
}

export function parseResearchMarkdown(text: string, citations: ReadonlyArray<{ data_id?: string | null }> = []): ResearchBlock[] {
  const known = new Set(citations.flatMap((citation) => citation.data_id ? [citation.data_id] : []));
  const lines = text.replace(/\r\n?/g, '\n').split('\n');
  const blocks: ResearchBlock[] = [];
  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (/^\s*```/.test(line)) {
      const content: string[] = []; i++;
      while (i < lines.length && !/^\s*```/.test(lines[i])) content.push(lines[i++]);
      if (i < lines.length) i++;
      blocks.push({ type: 'code', text: content.join('\n') }); continue;
    }
    const heading = /^#{1,6}\s+(.+)$/.exec(line);
    if (heading) { blocks.push({ type: 'heading', spans: inline(heading[1], known) }); i++; continue; }
    const quote = /^>\s?(.*)$/.exec(line);
    if (quote) { blocks.push({ type: 'quote', spans: inline(quote[1], known) }); i++; continue; }
    const list = /^\s*(?:([-+*])|\d+\.)\s+(.+)$/.exec(line);
    if (list) {
      const ordered = !list[1]; const items: ResearchInline[][] = [];
      while (i < lines.length) {
        const item = /^\s*(?:([-+*])|\d+\.)\s+(.+)$/.exec(lines[i]);
        if (!item || !item[1] !== ordered) break;
        items.push(inline(item[2], known)); i++;
      }
      blocks.push({ type: 'list', ordered, items }); continue;
    }
    const content = [line]; i++;
    while (i < lines.length && lines[i].trim() && !/^\s*(?:```|#{1,6}\s|>\s?|[-+*]\s|\d+\.\s)/.test(lines[i])) content.push(lines[i++]);
    blocks.push({ type: 'paragraph', spans: inline(content.join('\n'), known) });
  }
  return blocks;
}

/** The same readable text projection is shared by browser/native renderers and parity tests. */
export function researchMarkdownText(blocks: ResearchBlock[]): string {
  const text = (spans: ResearchInline[]) => spans.map((span) => span.text + (span.type === 'citation' && !span.known ? ' (unknown source)' : '')).join('');
  return blocks.map((block) => block.type === 'code' ? block.text : block.type === 'list'
    ? block.items.map((item, i) => `${block.ordered ? `${i + 1}.` : '•'} ${text(item)}`).join('\n')
    : text(block.spans)).join('\n\n');
}
