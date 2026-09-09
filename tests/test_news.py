from datetime import datetime, timedelta, timezone

import httpx
import pytest

from selery_api.news_pipeline import NewsUnavailable, canonical_url, fetch_feed, parse_feed, plain_text, process_news, score_sentiment
from selery_shared.models import NewsItem

NOW = datetime(2026, 9, 9, 20, tzinfo=timezone.utc)


def article(id='one', headline='AAPL earnings beat forecasts as profit grows', url='https://example.com/news', delta=0):
    return NewsItem(id=id, headline=headline, summary='Company publishes quarterly results.', source='Test source', url=url,
                    published_at=NOW + timedelta(minutes=delta), symbols=['AAPL'])


def test_sentiment_negation_is_transparent_and_unknown_is_neutral():
    positive = score_sentiment('profit growth')
    negative = score_sentiment('not strong; misses guidance')
    assert positive['score'] == 1
    assert negative['score'] == -1
    assert negative['hits'][0]['negated']
    assert score_sentiment('meeting at noon')['score'] == 0
    assert 'heuristic' in positive['limitation']


def test_tracking_links_deduplicate_with_all_citations():
    items = [article('a', delta=-1), article('b', url='https://example.com/news?utm_source=mail#top')]
    analysis = process_news(items, observed_at=NOW)
    assert len(analysis.items) == 1
    assert len(analysis.events[0]['sources']) == 2
    assert analysis.items[0].sentiment_method == 'lexical-finance-v1'
    assert analysis.events[0]['confidence'] is None


def test_identical_syndicated_text_deduplicates_across_domains():
    result = process_news([article('a'), article('b', url='https://second.example.com/story')], observed_at=NOW)
    assert len(result.items) == 1
    assert len(result.events[0]['sources']) == 2


def test_future_mutation_cannot_change_historical_news_or_scores():
    old = article('old', delta=-60)
    available = {'old': NOW - timedelta(minutes=59), 'future': NOW + timedelta(days=1)}
    baseline = process_news([old], observed_at=NOW, as_of=NOW - timedelta(minutes=30), known_availability=available)
    future = article('future', 'Fraud default bankruptcy recession', 'https://future.example.com', delta=100)
    full = process_news([future, old], observed_at=NOW, as_of=NOW - timedelta(minutes=30), known_availability=available)
    assert baseline.items == full.items and baseline.events == full.events
    assert full.discarded_future == 1
    assert process_news([old], observed_at=NOW, as_of=NOW-timedelta(seconds=1)).items == []


def test_event_relevance_is_symbol_specific_and_not_causal():
    analysis = process_news([article()], observed_at=NOW)
    event = analysis.events[0]
    assert event['relevance']['AAPL'] == 1 and event['relevance']['NVDA'] == 0
    assert 'does not establish' in event['explanation']
    assert event['impact_terms'] == ['earnings']


def test_html_plaintext_and_unsafe_urls():
    assert plain_text('<p>Hello <b>world</b></p><script>secret()</script>') == 'Hello world'
    assert canonical_url('https://EXAMPLE.com/news/?utm_campaign=x&id=2#top') == 'https://example.com/news?id=2'
    with pytest.raises(NewsUnavailable):
        canonical_url('javascript:alert(1)')


def test_atom_and_rss_dates_and_links_are_preserved():
    atom = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>8-K Example company</title><updated>2026-09-09T12:00:00Z</updated><link href="https://www.sec.gov/Archives/example"/><summary>New filing</summary></entry></feed>'''
    items = parse_feed(atom, source='SEC EDGAR', retrieved_at=NOW)
    assert len(items) == 1 and items[0].published_at.hour == 12
    assert items[0].symbols == []  # Do not guess ticker from a company name.
    rss = b'''<rss><channel><item><title>Policy announcement</title><pubDate>Wed, 09 Sep 2026 14:00:00 GMT</pubDate><link>https://www.federalreserve.gov/newsevents/example.htm</link><description>Official release</description></item><item><title>No timestamp</title></item></channel></rss>'''
    assert len(parse_feed(rss, source='Federal Reserve', retrieved_at=NOW)) == 1


def test_dtd_and_entity_markup_is_rejected():
    with pytest.raises(NewsUnavailable, match='markup'):
        parse_feed(b'<!DOCTYPE x [<!ENTITY x "boom">]><rss/>', source='Test', retrieved_at=NOW)


@pytest.mark.asyncio
async def test_feed_fetch_allowlist_and_redirect_refusal():
    with pytest.raises(NewsUnavailable, match='Unknown'):
        await fetch_feed('https://127.0.0.1/private', user_agent='Selery researcher@example.com')
    def handle(request):
        assert request.url.host == 'www.sec.gov'
        assert request.url.params['output'] == 'atom'
        return httpx.Response(302, headers={'location': 'https://untrusted.example'})
    with pytest.raises(NewsUnavailable, match='302'):
        await fetch_feed('sec_latest', user_agent='Selery researcher@example.com', transport=httpx.MockTransport(handle))
