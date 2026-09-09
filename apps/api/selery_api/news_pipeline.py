"""Deterministic, source-linked news research. Scores describe text, never causation."""
from __future__ import annotations

import hashlib
import html
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from selery_shared.models import NewsItem

UTC = timezone.utc
METHOD = 'lexical-finance-v1; TF-IDF unigram/bigram cosine v1'
POSITIVE = {'beat', 'beats', 'growth', 'grows', 'gain', 'gains', 'upgrade', 'upgraded', 'profit', 'profits', 'record', 'improves', 'strong', 'recovery', 'surplus'}
NEGATIVE = {'miss', 'misses', 'decline', 'declines', 'downgrade', 'downgraded', 'loss', 'losses', 'weak', 'recession', 'default', 'bankruptcy', 'fraud', 'layoffs', 'shortfall'}
NEGATION = {'not', 'no', 'never', 'without', "isn't", "wasn't", "doesn't"}
HIGH_IMPACT_TERMS = {'fomc', 'inflation', 'earnings', 'bankruptcy', 'merger', 'acquisition', 'guidance', 'rates', 'employment', 'default'}
FEEDS = {
    'sec_latest': ('SEC EDGAR', 'https://www.sec.gov/cgi-bin/browse-edgar',
                   {'action': 'getcurrent', 'owner': 'include', 'count': '100', 'output': 'atom'}),
    'federal_reserve': ('Federal Reserve', 'https://www.federalreserve.gov/feeds/press_all.xml', {}),
}


class NewsUnavailable(ValueError):
    pass


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.suppressed += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.suppressed:
            self.suppressed -= 1

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(data)


def plain_text(value: str) -> str:
    parser = _TextOnly()
    parser.feed(html.unescape(value))
    return ' '.join(' '.join(parser.parts).split())


def tokens(text: str):
    return re.findall(r"[a-z]+(?:'[a-z]+)?", plain_text(text).lower())


def canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
        raise NewsUnavailable('News source must be a public HTTP(S) link')
    query = [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True)
             if not key.lower().startswith('utm_') and key.lower() not in ('ref', 'source', 'fbclid', 'gclid')]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip('/') or '/', urlencode(sorted(query)), ''))


def score_sentiment(text: str) -> dict:
    hits, score = [], 0
    for clause in re.split(r'[.;:!?]', plain_text(text)):
        words = tokens(clause)
        for index, word in enumerate(words):
            polarity = 1 if word in POSITIVE else -1 if word in NEGATIVE else 0
            if not polarity:
                continue
            negated = any(w in NEGATION for w in words[max(0, index - 3):index])
            if negated:
                polarity *= -1
            score += polarity
            hits.append({'term': word, 'polarity': polarity, 'negated': negated})
    return {'score': score / len(hits) if hits else 0.0, 'method': 'lexical-finance-v1', 'hits': hits,
            'limitation': 'Text polarity heuristic; sarcasm, scope, context and economic impact are not modeled.'}


def similarity_to_previous(text: str, earlier: list[str]) -> list[float]:
    """Fit on only the documents already known plus this candidate, never future text."""
    if not earlier:
        return []
    try:
        matrix = TfidfVectorizer(lowercase=True, stop_words='english', ngram_range=(1, 2), sublinear_tf=True,
                                max_features=10000).fit_transform([*earlier, text])
    except ValueError:  # e.g. punctuation or stop-words only
        return [0.0] * len(earlier)
    return cosine_similarity(matrix[-1], matrix[:-1]).ravel().tolist()


@dataclass
class NewsAnalysis:
    items: list[NewsItem]
    events: list[dict]
    discarded_future: int
    method: str = METHOD


def process_news(items: list[NewsItem], *, observed_at: datetime, as_of: datetime | None = None,
                 known_availability: dict[str, datetime] | None = None,
                 watch_symbols: tuple[str, ...] = ('SPY', 'QQQ', 'AAPL', 'NVDA'), similarity_threshold=.84) -> NewsAnalysis:
    """First-observed timestamps can be loaded from immutable archival news records.

    Without those records availability defaults to this retrieval, not publication.
    A historical as_of therefore cannot accidentally see newly retrieved old stories.
    """
    if observed_at.tzinfo is None or (as_of is not None and as_of.tzinfo is None):
        raise ValueError('News observation and as-of timestamps must include timezone')
    if not 0 <= similarity_threshold <= 1 or len(items) > 500:
        raise ValueError('Use a threshold in [0, 1] and at most 500 news items per batch')
    cutoff = as_of or observed_at
    known_availability = known_availability or {}
    candidates, discarded = [], 0
    for item in items:
        published = item.published_at
        available = known_availability.get(item.id, observed_at)
        if available.tzinfo is None or published.tzinfo is None:
            raise ValueError('News timestamps must include timezone')
        available = max(published, available)
        if published > cutoff or available > cutoff:
            discarded += 1
            continue
        candidates.append((available, published, item))
    candidates.sort(key=lambda row: (row[0], row[1], row[2].id))
    accepted, events, texts, urls = [], [], [], []
    for available, published, item in candidates:
        headline, summary = plain_text(item.headline), plain_text(item.summary)
        if not headline:
            continue
        url = canonical_url(item.url)
        text = headline + '. ' + summary
        similarities = similarity_to_previous(text, texts)
        nearest = max(range(len(similarities)), key=similarities.__getitem__) if similarities else None
        duplicate = urls.index(url) if url in urls else nearest if nearest is not None and similarities[nearest] >= similarity_threshold else None
        citation = {'id': item.id, 'source': item.source, 'url': url, 'published_at': published.isoformat(), 'available_at': available.isoformat()}
        if duplicate is not None:
            if not any(source['id'] == item.id for source in events[duplicate]['sources']):
                events[duplicate]['sources'].append(citation)
            continue
        sentiment = score_sentiment(text)
        novelty = 1.0 - max(similarities, default=0.0)
        words = set(tokens(text))
        impact_terms = sorted(words & HIGH_IMPACT_TERMS)
        impact = min(1.0, .25 + .15 * len(impact_terms))
        relevance = {symbol: 1.0 if symbol in item.symbols else .6 if re.search(rf'\b{re.escape(symbol)}\b', text, re.I) else
                     .3 if symbol in ('SPY', 'QQQ') and words & {'fomc', 'inflation', 'rates', 'employment'} else 0.0 for symbol in watch_symbols}
        enriched = item.model_copy(update={'headline': headline, 'summary': summary, 'url': url,
                                  'sentiment': sentiment['score'], 'sentiment_method': sentiment['method']})
        accepted.append(enriched)
        texts.append(text)
        urls.append(url)
        events.append({'id': item.id, 'headline': headline, 'available_at': available.isoformat(),
                       'published_at': published.isoformat(), 'sources': [citation], 'sentiment': sentiment,
                       'novelty': round(max(0, min(1, novelty)), 6), 'relevance': relevance,
                       'impact_score': impact, 'impact_terms': impact_terms, 'impact_method': 'keyword-salience-v1',
                       'explanation': 'Related source text; temporal proximity does not establish the cause of a price move.',
                       'confidence': None, 'version': '1'})
    return NewsAnalysis(list(reversed(accepted)), list(reversed(events)), discarded)


def parse_feed(raw: bytes, *, source: str, retrieved_at: datetime) -> list[NewsItem]:
    if len(raw) > 2_000_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise NewsUnavailable('Feed markup or size is not permitted')
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        raise NewsUnavailable('Feed XML is invalid') from None
    atom = '{http://www.w3.org/2005/Atom}'
    entries = root.findall(f'{atom}entry') if root.tag == f'{atom}feed' else root.findall('./channel/item')
    items = []
    for entry in entries[:200]:
        is_atom = entry.tag == f'{atom}entry'
        def value(name):
            element = entry.find(f'{atom}{name}' if is_atom else name)
            return ''.join(element.itertext()) if element is not None else ''
        title = plain_text(value('title'))
        summary = plain_text(value('summary') or value('content') if is_atom else value('description'))
        if is_atom:
            links = entry.findall(f'{atom}link')
            url = next((link.get('href', '') for link in links if link.get('rel', 'alternate') == 'alternate'), '')
            timestamp = value('published') or value('updated')
        else:
            url, timestamp = value('link'), value('pubDate')
        try:
            url = canonical_url(url)
            published = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if is_atom else parsedate_to_datetime(timestamp)
            if not title or published.tzinfo is None or published > retrieved_at:
                continue
        except (ValueError, TypeError, NewsUnavailable):
            continue
        identity = hashlib.sha256(f'{source}\n{url}\n{published.isoformat()}'.encode()).hexdigest()[:32]
        items.append(NewsItem(id=identity, headline=title, summary=summary, url=url, source=source,
                              published_at=published, symbols=[]))
    return items


async def fetch_feed(feed_id: str, *, user_agent: str, transport=None, now=None) -> list[NewsItem]:
    """Only named, fixed official feeds are fetchable; caller-supplied URLs are rejected."""
    if feed_id not in FEEDS:
        raise NewsUnavailable('Unknown news feed identifier')
    if not re.fullmatch(r'[^\r\n]{3,120} [^\s@]+@[^\s@]+\.[^\s@]+', user_agent):
        raise NewsUnavailable('An application name and contact email are required for official feeds')
    source, url, params = FEEDS[feed_id]
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False, transport=transport) as client:
            async with client.stream('GET', url, params=params, headers={'User-Agent': user_agent, 'Accept': 'application/atom+xml, application/rss+xml'}) as response:
                if response.status_code != 200:
                    raise NewsUnavailable(f'{source} feed unavailable (HTTP {response.status_code})')
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2_000_000:
                        raise NewsUnavailable('Feed response exceeds size limit')
    except httpx.HTTPError:
        raise NewsUnavailable(f'{source} feed connection unavailable') from None
    return parse_feed(bytes(raw), source=source, retrieved_at=now or datetime.now(UTC))
