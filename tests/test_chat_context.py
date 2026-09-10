"""Deterministic evidence checks; never dispatch a model or a provider request."""
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from selery_api.chat_context import build_context, exchange_context, known_bars, quantitative_summary, regular_session_levels, requested_timeframes
from selery_api.storage import Store
from selery_shared.indicators import capabilities
from selery_shared.models import Bar, ChartResponse, Conversation, Feed, NewsItem, Outcome, Provenance, Signal, Timeframe

UTC = timezone.utc
NOW = datetime(2026, 9, 9, 20, 5, tzinfo=UTC)


def bars(opening='2026-09-09T13:30:00+00:00', count=78, step=300):
    start = int(datetime.fromisoformat(opening).timestamp())
    return [Bar(symbol='SPY', time=start + i * step, available_at=start + (i+1) * step,
                open=100+i, high=102+i, low=99+i, close=101+i, feed=Feed.IEX) for i in range(count)]


def chart(values=None, timeframe=Timeframe.M5, stale=False):
    values = values if values is not None else bars()
    return ChartResponse(symbol='SPY', timeframe=timeframe, bars=values, signals=[], indicators={}, capabilities=capabilities(Feed.IEX),
                         provenance=Provenance(provider='offline-test', feed=Feed.IEX, observed_at=NOW, available_at=NOW, retrieved_at=NOW, stale=stale))


def conversation(signal=None):
    return Conversation(id='thread', symbol='SPY', title='SPY', created_at=NOW, updated_at=NOW, signal=signal)


def app(news=None):
    async def get_news(symbols): return news or []
    return SimpleNamespace(state=SimpleNamespace(store=Store('sqlite:///:memory:'), provider=SimpleNamespace(news=get_news)))


def build(question='Explain the chart', values=None, stale=False, signal=None, source=None):
    calls = []
    async def get_chart(symbol, timeframe, feed, limit):
        calls.append((symbol, timeframe, feed, limit))
        return chart(values, timeframe, stale)
    result = asyncio.run(build_context(source or app(), get_chart, conversation(signal), question, Timeframe.M5, NOW))
    return result, calls


def test_question_selects_bounded_multiple_intervals():
    (_, _, _), calls = build('How should I research SPY tomorrow?')
    assert [entry[1] for entry in calls] == [Timeframe.M5, Timeframe.H1, Timeframe.D1]
    assert all(entry[2] == Feed.IEX and entry[3] <= 240 for entry in calls)
    assert requested_timeframes('Explain the current cross', Timeframe.H1) == [Timeframe.H1, Timeframe.M5]


def test_calendar_holiday_weekend_and_dst():
    friday = exchange_context(datetime(2026, 9, 4, 22, tzinfo=UTC))
    assert friday['next_session']['date'] == '2026-09-08'  # Labor Day skipped
    assert exchange_context(datetime(2026, 9, 7, 15, tzinfo=UTC))['phase'] == 'closed_non_session'
    before = exchange_context(datetime(2026, 3, 6, 15, tzinfo=UTC))
    after = exchange_context(datetime(2026, 3, 9, 15, tzinfo=UTC))
    assert '14:30' in before['current_session']['open']
    assert '13:30' in after['current_session']['open']


def test_early_close_coverage_uses_exchange_calendar():
    now = datetime(2026, 11, 27, 18, 5, tzinfo=UTC)
    session = exchange_context(now)['current_session']
    assert '18:00' in session['close']
    levels = regular_session_levels(bars('2026-11-27T14:30:00+00:00', 42), session, now)
    assert levels['expected_bars'] == 42 and levels['full_session']


def test_twenty_bar_observed_range_is_never_daily_range():
    (context, _, _), _ = build(values=bars()[-20:])
    levels = context['session_levels']['current']
    assert levels['available'] and not levels['full_session']
    assert levels['missing_bars'] == 58 and 'session_high' not in levels
    assert 'not a daily/session range' in levels['reason']
    assert context['research_comparisons']['qualitative_preference'] is None


def test_complete_session_and_causal_atr_hand_computed():
    (context, _, _), _ = build()
    levels = context['session_levels']['current']
    assert levels['full_session'] and levels['session_high'] == 179 and levels['session_low'] == 99
    assert context['indicators']['atr14'] == 3
    assert quantitative_summary(bars(count=13))['atr14'] is None


def test_future_and_forming_mutation_cannot_change_quantitative_results():
    original = bars()
    future = original[-1].model_copy(update={'time': int(NOW.timestamp())+300, 'available_at': int(NOW.timestamp())+600})
    forming = original[-1].model_copy(update={'time': int(NOW.timestamp()), 'available_at': int(NOW.timestamp())+300, 'finalized': False})
    before = quantitative_summary(known_bars(chart(original+[future, forming]), NOW))
    future = future.model_copy(update={'close': 999999, 'high': 999999})
    forming = forming.model_copy(update={'close': 888888, 'high': 888888})
    assert quantitative_summary(known_bars(chart(original+[future, forming]), NOW)) == before


def test_provisional_latest_citation_has_no_future_availability():
    provisional = bars()[-1].model_copy(update={'time': int(NOW.timestamp())-60, 'available_at': int(NOW.timestamp())+240, 'finalized': False, 'close': 500})
    (context, citations, last), _ = build(values=bars()+[provisional])
    assert last.close == 500 and 'provisional' in citations[0].label
    assert citations[0].timestamp <= NOW and citations[0].available_at <= NOW
    assert context['timeframes']['5m']['summary']['last_close'] == 178


def test_stale_data_cannot_rank_a_current_setup():
    (context, _, _), _ = build('best setup tomorrow', stale=True)
    comparisons = context['research_comparisons']
    assert comparisons['qualitative_preference'] is None
    assert all(not scenario['supported'] and 'Stale' in scenario['reason'] for scenario in comparisons['scenarios'])


def selected_signal():
    return Signal(id='signal-test', symbol='SPY', strategy='ema-cross', timeframe=Timeframe.M5, time=bars()[21].time,
                  available_at=bars()[21].available_at, direction='bullish', reference_price=122, stop=120, target=126,
                  feed=Feed.IEX, explanation='Original observed crossover')


def test_signal_confidence_and_later_ambiguous_outcome_are_not_rewritten():
    signal = selected_signal()
    source = app()
    source.state.store.put('outcomes', Outcome(signal_id=signal.id, status='ambiguous', evaluated_at=NOW,
                          bars_observed=1, resolved_at=signal.available_at+300, reason='Both thresholds in one bar.'), signal.id)
    (context, citations, _), _ = build(signal=signal, source=source)
    selected = context['selected_signal']
    assert selected['snapshot']['confidence'] is None
    assert selected['outcome']['status'] == 'ambiguous'
    assert 'not information known at signal time' in selected['outcome_reason']
    assert any(citation.data_id == 'outcome:'+signal.id for citation in citations)


def test_future_evaluated_outcome_is_unavailable():
    signal = selected_signal(); source = app()
    source.state.store.put('outcomes', Outcome(signal_id=signal.id, status='target_first', evaluated_at=NOW+timedelta(days=1), bars_observed=1), signal.id)
    (context, _, _), _ = build(signal=signal, source=source)
    assert context['selected_signal']['outcome'] is None


def test_future_selected_signal_rejected():
    with pytest.raises(ValueError, match='not yet available'):
        build(signal=selected_signal().model_copy(update={'available_at': int(NOW.timestamp())+1}))


def test_iex_features_are_disabled_and_volume_not_sent_as_quant_evidence():
    (context, _, _), _ = build('best setup tomorrow')
    assert all(not capability['enabled'] and capability['reason'] == 'needs SIP data' for capability in context['capabilities'])
    assert all('volume' not in bar for frame in context['timeframes'].values() for bar in frame.get('bars', []))
    assert context['costs']['available']
    assert [case['assumed_full_spread'] for case in context['costs']['cases']] == [0.01, 0.02, 0.05]


def test_missing_secondary_interval_retains_explicit_reason():
    async def fetch(symbol, timeframe, feed, limit):
        if timeframe == Timeframe.D1: raise ValueError('unavailable')
        return chart(timeframe=timeframe)
    context, _, _ = asyncio.run(build_context(app(), fetch, conversation(), 'tomorrow', Timeframe.M5, NOW))
    assert context['timeframes']['1D']['available'] is False
    assert 'unavailable' in context['timeframes']['1D']['reason']


def test_news_conflicts_preserved_future_publications_excluded():
    news = [NewsItem(id=str(index), headline=headline, summary='Source reporting only', source='fixture',
                     url='https://example.com/news', published_at=when, symbols=['SPY'])
            for index, (headline, when) in enumerate([('Bullish outlook', NOW), ('Bearish outlook', NOW), ('Future leak', NOW+timedelta(days=1))])]
    (context, citations, _), _ = build(source=app(news))
    assert {item['headline'] for item in context['news']} == {'Bullish outlook', 'Bearish outlook'}
    assert 'price impact are unverified' in context['news_coverage']
    assert 'Future leak' not in json.dumps(context)
    assert len(json.dumps(context).encode()) <= 25000


def test_context_budget_under_history_allowance():
    (context, _, _), _ = build('compare daily weekly setup tomorrow', signal=selected_signal())
    assert len(json.dumps(context, ensure_ascii=False).encode()) < 25000


def test_no_known_bar_never_fabricates_technical_values():
    future = bars()[0].model_copy(update={'time': int(NOW.timestamp())+1, 'available_at': int(NOW.timestamp())+301})
    with pytest.raises(ValueError, match='No observations'):
        build(values=[future])


QUESTIONS = json.loads((Path(__file__).parent / 'fixtures/chat-evaluation-questions.json').read_text())


@pytest.mark.parametrize('case', QUESTIONS, ids=lambda case: case['case'])
def test_offline_question_evidence_contract(case):
    """Evaluates the supplied evidence, not an invented successful live answer."""
    (context, citations, _), _ = build(case['question'], values=bars()[-20:] if case['case'] == 'missing_history' else None,
                                    stale=case['case'] == 'stale_next_session', signal=selected_signal())
    assert citations and all(citation.provider and citation.observation for citation in citations)
    assert context['as_of'] == NOW.isoformat()
    if case['case'] == 'stale_next_session':
        assert context['calendar']['next_session']['date'] == '2026-09-10'
        assert context['research_comparisons']['qualitative_preference'] is None
    elif case['case'] == 'selected_signal':
        assert context['selected_signal']['snapshot']['reference_price'] == 122
        assert 'never rescored' in context['selected_signal']['meaning']
    elif case['case'] == 'absent_confidence':
        assert context['selected_signal']['snapshot']['confidence'] is None
        assert 'unavailable' in context['evidence_rules']['confidence']
    elif case['case'] == 'conflicting_news':
        assert 'Attribute conflicting reports separately' in context['evidence_rules']['conflicting_news']
    elif case['case'] == 'missing_history':
        assert 'session_high' not in context['session_levels']['current']
    elif case['case'] == 'trader_motive':
        assert 'never infer motive as fact' in context['evidence_rules']['trader_motive']
    assert len(json.dumps(context, ensure_ascii=False).encode()) < 23000


def test_saved_signal_chart_excludes_later_bars():
    signal = selected_signal(); source = app()
    original_get = source.state.store.get
    source.state.store.get = lambda collection, key: chart().model_dump(mode='json') if collection == 'conversation_charts' else original_get(collection, key)
    (context, _, _), _ = build(signal=signal, source=source)
    dated = context['selected_signal']['chart_at_signal_time']
    assert dated['summary']['known_finalized_bars'] == 22
    assert all(bar['available_at'] <= signal.available_at for bar in dated['bars'])
    assert dated['summary']['last_close'] == 122
