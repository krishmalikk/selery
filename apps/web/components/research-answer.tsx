"use client";

import { useState } from "react";
import { formatTime, parseResearchMarkdown, safeResearchUrl, type Citation, type ResearchInline } from "@selery/shared";

/** Deliberately uses React text nodes only; no HTML or Markdown execution. */
export default function ResearchAnswer({ text, citations }: { text: string; citations: Citation[] }) {
  const [evidence, setEvidence] = useState<Citation | null>(null);
  function spans(values: ResearchInline[]) {
    return values.map((span, index) => {
      if (span.type === "strong") return <strong key={index}>{span.text}</strong>;
      if (span.type === "emphasis") return <em key={index}>{span.text}</em>;
      if (span.type === "code") return <code key={index}>{span.text}</code>;
      if (span.type === "link") return <a key={index} href={safeResearchUrl(span.url) || undefined} target="_blank" rel="noopener noreferrer">{span.text}</a>;
      if (span.type === "citation") {
        const citation = citations.find((item) => item.data_id === span.id);
        return citation ? <button key={index} type="button" className="research-citation" onClick={() => setEvidence(citation)} aria-label={`Evidence ${span.id}`}>[{span.id}]</button> : <span key={index} className="warning" title="This ID is not in the supplied evidence">[{span.id}] (unknown source)</span>;
      }
      return <span key={index}>{span.text}</span>;
    });
  }
  return <div className="research-answer">
    {parseResearchMarkdown(text, citations).map((block, index) => {
      if (block.type === "code") return <pre key={index}><code>{block.text}</code></pre>;
      if (block.type === "list") { const children = block.items.map((item, i) => <li key={i}>{spans(item)}</li>); return block.ordered ? <ol key={index}>{children}</ol> : <ul key={index}>{children}</ul>; }
      if (block.type === "heading") return <h3 key={index}>{spans(block.spans)}</h3>;
      if (block.type === "quote") return <blockquote key={index}>{spans(block.spans)}</blockquote>;
      return <p key={index}>{spans(block.spans)}</p>;
    })}
    {citations.length > 0 && <div className="research-sources" aria-label="Supplied evidence">{citations.map((citation, index) => <button key={index} type="button" className="citation" onClick={() => setEvidence(citation)}>{citation.label}<small>{formatTime(citation.timestamp)}{citation.data_id ? ` · ${citation.data_id}` : ""}</small></button>)}</div>}
    {evidence && <section className="research-evidence" aria-label="Evidence details">
      <div className="section-title"><strong>{evidence.label}</strong><button type="button" aria-label="Close evidence" onClick={() => setEvidence(null)}>×</button></div>
      <dl><dt>Provider</dt><dd>{evidence.provider || "Unavailable"}</dd><dt>Feed</dt><dd>{evidence.feed === "iex" ? "IEX only" : evidence.feed || "Unavailable"}</dd><dt>Observation time</dt><dd>{formatTime(evidence.timestamp)}</dd><dt>Available at</dt><dd>{evidence.available_at ? formatTime(evidence.available_at) : "Unavailable"}</dd></dl>
      <p>{evidence.observation || "Exact supporting observation is unavailable for this saved answer."}</p>
      {evidence.url && safeResearchUrl(evidence.url) && <a href={safeResearchUrl(evidence.url)!} target="_blank" rel="noopener noreferrer">Open original source</a>}
    </section>}
  </div>;
}
