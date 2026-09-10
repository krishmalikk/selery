import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseResearchMarkdown, researchMarkdownText, safeResearchUrl } from '../packages/shared/src/research-markdown';

test('readable subset produces one shared text representation for native and web', () => {
  const blocks = parseResearchMarkdown('# Plan\n\n**Support** at *100* and `EMA9`. [spy:5m]\n\n- Wait\n- Check [source](https://example.org/news)\n\n1. First\n2. Second\n\n> Uncertain\n\n```\n<literal>\n```', [{ data_id: 'spy:5m' }]);
  assert.equal(researchMarkdownText(blocks), 'Plan\n\nSupport at 100 and EMA9. [spy:5m]\n\n• Wait\n• Check source\n\n1. First\n2. Second\n\nUncertain\n\n<literal>');
  assert.equal(blocks[1].type, 'paragraph');
});
test('unsafe protocols and normalization tricks have no link targets', () => {
  for (const value of ['javascript:alert(1)', 'data:text/html,hello', '//example.com', 'https:\\evil.com', 'https://user:password@example.com', 'https://example.com\n.evil.com', '\thttps://example.com']) assert.equal(safeResearchUrl(value), null);
  assert.equal(safeResearchUrl('https://example.com/news?q=spy#one'), 'https://example.com/news?q=spy#one');
  assert.equal(safeResearchUrl('http://localhost:3000/'), 'http://localhost:3000/');
  const blocks = parseResearchMarkdown('[click](javascript:alert) [file](file:///etc/passwd)');
  assert.ok(!JSON.stringify(blocks).includes('"type":"link"'));
  assert.match(researchMarkdownText(blocks), /unsafe link blocked/);
});
test('HTML, images and unknown source IDs cannot inject or invent evidence', () => {
  const blocks = parseResearchMarkdown('<script>alert(1)</script> <img src=x onerror=alert(1)>\n\n![image](data:image/svg+xml,foo) [fabricated] [real]', [{ data_id: 'real' }]);
  assert.match(researchMarkdownText(blocks), /<script>alert\(1\)<\/script>/);
  assert.match(researchMarkdownText(blocks), /\[fabricated\] \(unknown source\)/);
  assert.ok(!researchMarkdownText(blocks).includes('[real] (unknown source)'));
});
test('unterminated formatting and streaming fences remain readable', () => {
  assert.equal(researchMarkdownText(parseResearchMarkdown('**partial')), '**partial');
  assert.equal(researchMarkdownText(parseResearchMarkdown('```\npartial')), 'partial');
  assert.equal(researchMarkdownText(parseResearchMarkdown('')), '');
});
