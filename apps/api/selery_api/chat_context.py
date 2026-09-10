"""Bounded, causal evidence for stock chat. No model calls or mutations."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import httpx
from fastapi import HTTPException
from selery_shared.costs import CostAssumptions, spread_sensitivity
from selery_shared.indicators import atr, ema, rsi
from selery_shared.models import ChartResponse, Citation, Feed, Outcome, Timeframe

UTC = timezone.utc
NY = ZoneInfo('America/New_York')
CONTEXT_VERSION = 'stock-context-2'


def exchange_context(now):
    """Exchange sessions, including holidays/early closes, in UTC and New York."""
    day = now.astimezone(NY).date()
    calendar = xcals.get_calendar('XNYS')
    def session(value):
        return {'date': str(value.date()), 'open': calendar.session_open(value).isoformat(),
                'close': calendar.session_close(value).isoformat()}
    try:
        today = calendar.date_to_session(day, direction='none') if calendar.is_session(day) else None
        next_day = calendar.date_to_session(day + timedelta(days=1), direction='next')
        previous = calendar.date_to_session(day - timedelta(days=1), direction='previous')
        phase = 'closed_non_session'
        if today is not None:
            opening, closing = calendar.session_open(today), calendar.session_close(today)
            phase = 'premarket' if now < opening else 'regular' if now < closing else 'postmarket'
        return {'calendar': 'XNYS', 'calendar_package_version': xcals.__version__, 'timezone': str(NY),
                'as_of': now.isoformat(), 'local_time': now.astimezone(NY).isoformat(), 'phase': phase,
                'current_session': session(today) if today is not None else None,
                'previous_session': session(previous), 'next_session': session(next_day),
                'extended_hours_coverage': 'Unavailable; no complete premarket or postmarket coverage is asserted.'}
    except (ValueError, KeyError):
        return {'calendar': 'XNYS', 'as_of': now.isoformat(), 'timezone': str(NY),
                'reason': 'Requested date is outside the installed exchange calendar coverage.'}


def known_bars(chart, now):
    """Do not let future bars, forming bars, or duplicated timestamps enter math."""
    cutoff = int(now.timestamp())
    return sorted({bar.time: bar for bar in chart.bars if bar.symbol == chart.symbol and
                   bar.feed == chart.provenance.feed and bar.finalized and
                   bar.time <= bar.available_at <= cutoff}.values(), key=lambda bar: bar.time)


def regular_session_levels(bars, session, now):
    if not session:
        return {'available': False, 'reason': 'No regular session on this calendar date.'}
    opening = int(datetime.fromisoformat(session['open']).timestamp())
    closing = int(datetime.fromisoformat(session['close']).timestamp())
    cutoff = min(closing, int(now.timestamp()))
    # Only complete, aligned five-minute bars may establish session coverage.
    eligible = [bar for bar in bars if opening <= bar.time < closing and bar.available_at <= cutoff
                and bar.available_at - bar.time == 300 and (bar.time - opening) % 300 == 0]
    expected = set(range(opening, max(opening, cutoff - 299), 300))
    seen = {bar.time for bar in eligible}
    coverage = bool(expected) and expected <= seen
    result = {'session': session['date'], 'available': bool(eligible), 'complete_to_as_of': coverage,
              'full_session': coverage and cutoff >= closing, 'expected_bars': len(expected),
              'observed_bars': len(seen), 'missing_bars': len(expected - seen)}
    if not eligible:
        return {**result, 'reason': 'No finalized regular-session 5m observations supplied.'}
    eligible.sort(key=lambda bar: bar.time)
    result.update(observed_range_high=max(bar.high for bar in eligible), observed_range_low=min(bar.low for bar in eligible),
                  last_observed_close=eligible[-1].close, as_of=datetime.fromtimestamp(eligible[-1].available_at, UTC).isoformat())
    if coverage:
        result.update(session_open=eligible[0].open, session_high=result['observed_range_high'], session_low=result['observed_range_low'])
    else:
        result['reason'] = 'Incomplete five-minute coverage. Observed range is not a daily/session range.'
    return result


def quantitative_summary(bars):
    closes = [bar.close for bar in bars]
    result = {'known_finalized_bars': len(bars), 'ema9': None, 'ema21': None, 'rsi14': None, 'atr14': None,
              'atr_method': 'Causal Wilder ATR(14), seeded with the first 14 true ranges in the supplied window.'}
    if not bars:
        return {**result, 'reason': 'No finalized observations known by the requested as-of time.'}
    result.update(ema9=ema(closes, 9)[-1], ema21=ema(closes, 21)[-1], rsi14=rsi(closes)[-1], atr14=atr(bars)[-1],
                  last_close=closes[-1], as_of=datetime.fromtimestamp(bars[-1].available_at, UTC).isoformat())
    if len(bars) < 21:
        result['reason'] = 'Some indicators are unavailable because their warm-up is incomplete.'
    result['coverage_note'] = 'Computed over supplied bars only; missing bars are not imputed and corporate-action adjustment is unverified.'
    return result


def requested_timeframes(message, selected):
    selected = Timeframe(selected)
    wide = any(term in message.lower() for term in ('tomorrow', 'next session', 'next-session', 'week', 'daily', 'swing', 'compare', 'comparison', 'plan', 'best', 'setup'))
    return list(dict.fromkeys([selected, Timeframe.M5] + ([Timeframe.H1, Timeframe.D1] if wide else [])))


def scenario_context(summary, levels, stale, signal):
    reference = levels.get('current') if levels.get('current', {}).get('complete_to_as_of') else levels.get('previous', {})
    supported = bool(reference.get('complete_to_as_of'))
    high, low = reference.get('session_high'), reference.get('session_low')
    common = {'calibrated_probability': None, 'historical_hit_rate': None,
              'target': None, 'target_reason': 'No validated analytical target supplied for this scenario.'}
    scenarios = []
    for direction in ('bullish', 'bearish'):
        matching = signal if signal and signal.direction == direction else None
        scenarios.append({**common, 'direction': direction, 'supported': supported and not stale,
                          'confirmation': f'A new finalized regular-session bar closes {"above" if direction == "bullish" else "below"} the supplied {reference.get("session", "session")} {"high" if direction == "bullish" else "low"}.' if supported else None,
                          'confirmation_level': high if direction == 'bullish' else low,
                          'invalidation_level': low if direction == 'bullish' else high,
                          'invalidation': 'A finalized close beyond the opposite reference-session boundary invalidates this conditional range scenario.' if supported else None,
                          'target': matching.target if matching else None,
                          'target_reason': 'Original selected signal analytical target; this is historical signal-time context, not a newly validated target.' if matching else common['target_reason'],
                          'reason': 'Stale observations cannot establish a current setup.' if stale else None if supported else 'Complete reference-session coverage is unavailable.'})
    preferred = None
    fast, slow = summary.get('ema9'), summary.get('ema21')
    if supported and not stale and fast is not None and slow is not None and fast != slow:
        preferred = 'bullish' if fast > slow else 'bearish'
    return {'scenarios': scenarios, 'qualitative_preference': preferred,
            'preference_basis': 'EMA9 versus EMA21 alignment only, conditional on a confirmed session boundary; not a calibrated probability or best-trade ranking.' if preferred else 'No adequately supported current preference.',
            'execution': 'Analytical scenarios only; no execution or portfolio performance.'}


async def build_context(app, get_chart, conversation, message, timeframe, now=None):
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError('Chat context requires a timezone-aware as-of timestamp')
    now = now.astimezone(UTC)
    frames = requested_timeframes(message, timeframe)
    async def retrieve(frame):
        return await get_chart(conversation.symbol, frame, Feed.IEX, 240 if frame == Timeframe.M5 else 120)
    results = await asyncio.gather(*(retrieve(frame) for frame in frames), return_exceptions=True)
    primary = results[0]
    if isinstance(primary, BaseException):
        raise primary
    # A provisional observation is display context only. Never put a future
    # finalized bar into either the latest-price citation or calculations.
    observed = [bar for bar in primary.bars if bar.time <= now.timestamp() and (not bar.finalized or bar.available_at <= now.timestamp())]
    if not observed:
        raise ValueError('No observations available by the requested as-of time')
    last = max(observed, key=lambda bar: bar.time)
    citations = []
    context = {'version': CONTEXT_VERSION, 'symbol': conversation.symbol, 'timeframe': Timeframe(timeframe).value,
               'as_of': now.isoformat(), 'calendar': exchange_context(now), 'timeframes': {},
               'evidence_rules': {'confidence': 'Only an original calibrated signal-time score may be stated numerically. Missing confidence is unavailable.',
                                  'conflicting_news': 'Attribute conflicting reports separately; supplied reporting cannot establish a true motive or guaranteed impact.',
                                  'trader_motive': 'Unavailable unless the trader explicitly states it in a supplied attributable source; never infer motive as fact.',
                                  'citations': 'Only supplied IDs support claims. A citation does not turn a conditional scenario into a prediction.'},
               'limitations': ['IEX only; volume is not consolidated. No VWAP, OBV, volume confirmation or consolidated-liquidity inference.',
                               'No complete premarket or postmarket coverage. Corporate-action adjustment is unverified.',
                               'News reporting is evidence of a report, not proof of price impact or a trader motive.',
                               'Context contains bounded recent observations, not the entire chart or cursor position.'],
               'chart_selection': {'start': getattr(conversation, 'chart_start', None), 'end': getattr(conversation, 'chart_end', None),
                                   'meaning': 'Dated chart selection, not a claim that every historical bar is available.'}}
    frame_bars = {}
    for frame, chart in zip(frames, results):
        if isinstance(chart, BaseException):
            context['timeframes'][frame.value] = {'available': False, 'reason': 'Market data for this interval is unavailable.'}
            continue
        bars = known_bars(chart, now)
        frame_bars[frame] = bars
        summary = quantitative_summary(bars)
        context['timeframes'][frame.value] = {'available': bool(bars), 'provenance': chart.provenance.model_dump(mode='json'),
                                             'summary': summary, 'bars': [bar.model_dump(mode='json', exclude={'volume'}) for bar in bars[-12:]]}
        evidence = last if frame == Timeframe(timeframe) else bars[-1] if bars else None
        if evidence:
            available = datetime.fromtimestamp(evidence.available_at, UTC) if evidence.finalized else min(now, chart.provenance.retrieved_at)
            citations.append(Citation(label=f'{conversation.symbol} {frame.value} IEX only reference bar'+(' · provisional' if not evidence.finalized else ''),
                                      timestamp=available, available_at=available, provider=chart.provenance.provider, feed=Feed.IEX,
                                      data_id=f'{conversation.symbol}:{frame.value}:iex:{evidence.time}',
                                      observation=f'Open {evidence.open}; high {evidence.high}; low {evidence.low}; close {evidence.close}. '+('Finalized.' if evidence.finalized else 'Provisional; excluded from calculations.')))
    calendar = context['calendar']
    levels = {name: regular_session_levels(frame_bars.get(Timeframe.M5, []), calendar.get(f'{name}_session'), now) for name in ('current', 'previous')}
    context['session_levels'] = levels
    summary = context['timeframes'][Timeframe(timeframe).value]['summary']
    for frame, bars in frame_bars.items():
        if not bars:
            continue
        frame_summary = context['timeframes'][frame.value]['summary']
        calculation_id = f'calculation:{conversation.symbol}:{frame.value}:iex:{bars[-1].available_at}:{CONTEXT_VERSION}'
        context['timeframes'][frame.value]['calculation_citation_id'] = calculation_id
        observation = {key: frame_summary[key] for key in ('known_finalized_bars', 'ema9', 'ema21', 'rsi14', 'atr14')}
        if frame == Timeframe.M5:
            observation['regular_session_levels'] = levels
        citations.append(Citation(label=f'Python {frame.value} finalized-bar calculations', provider='selery', feed=Feed.IEX,
                                  timestamp=now, available_at=now, data_id=calculation_id,
                                  observation=json.dumps(observation, separators=(',', ':'))))
    signal = getattr(conversation, 'signal', None)
    context['selected_signal'] = None
    if signal:
        signal_data = signal.model_dump(mode='json')
        signal_data['explanation'] = signal_data['explanation'][:1500]
        signal_data['features'] = dict(list(signal_data['features'].items())[:30])
        context['selected_signal'] = {'snapshot': signal_data, 'meaning': 'Immutable original signal-time record; never rescored using a later model.',
                                      'outcome': None, 'outcome_reason': 'No matching outcome available by this answer as-of timestamp.',
                                      'chart_at_signal_time': None,
                                      'feed_compatibility': 'Matching IEX context.' if signal.feed == Feed.IEX else 'Selected signal uses a different feed from the current IEX chart; do not equate volume features or cohorts.'}
        if signal.symbol != conversation.symbol or signal.available_at > now.timestamp():
            raise ValueError('Selected signal does not match this stock or is not yet available')
        citations.append(Citation(label='Original signal-time research snapshot', timestamp=datetime.fromtimestamp(signal.available_at, UTC),
                                  available_at=datetime.fromtimestamp(signal.available_at, UTC), data_id=signal.id, provider='selery', feed=signal.feed,
                                  observation=f'{signal.direction}; reference {signal.reference_price}; analytical stop {signal.stop}; target {signal.target}; horizon {signal.horizon_bars} {signal.timeframe.value} bars. Confidence '+(str(signal.confidence) if signal.confidence is not None else 'unavailable: '+str(signal.confidence_reason))))
        try:
            saved_chart = app.state.store.get('conversation_charts', conversation.id)
        except KeyError:
            saved_chart = None  # Older databases have no chart snapshot collection.
        if saved_chart:
            original_chart = ChartResponse.model_validate(saved_chart)
            if original_chart.symbol == signal.symbol and original_chart.timeframe == signal.timeframe and original_chart.provenance.feed == signal.feed:
                original_bars = known_bars(original_chart, datetime.fromtimestamp(signal.available_at, UTC))
                context['selected_signal']['chart_at_signal_time'] = {
                    'as_of': datetime.fromtimestamp(signal.available_at, UTC).isoformat(),
                    'summary': quantitative_summary(original_bars),
                    'bars': [bar.model_dump(mode='json', exclude={'volume'}) for bar in original_bars[-6:]],
                    'meaning': 'Saved dated chart filtered to finalized observations available at signal time; later bars excluded.'}
        raw = app.state.store.get('outcomes', signal.id)
        if raw:
            outcome = Outcome.model_validate(raw)
            if outcome.signal_id == signal.id and signal.available_at <= outcome.evaluated_at.timestamp() <= now.timestamp() and (outcome.resolved_at is None or signal.available_at <= outcome.resolved_at <= now.timestamp()):
                context['selected_signal'].update(outcome=outcome.model_dump(mode='json'), outcome_reason='Later observed outcome, not information known at signal time. Ambiguous and incomplete outcomes remain unresolved.')
                citations.append(Citation(label='Later observed signal outcome', timestamp=outcome.evaluated_at, available_at=outcome.evaluated_at,
                                          provider='selery', feed=signal.feed, data_id='outcome:'+signal.id, observation=f'{outcome.status}; {outcome.bars_observed} bars observed. {outcome.reason or ""}'[:1500]))
    context['research_comparisons'] = scenario_context(summary, levels, primary.provenance.stale, signal)
    context['costs'] = {'available': False, 'reason': 'Symbol-specific spread, size and holding assumptions are not supplied. No consolidated liquidity is inferred from IEX.'}
    if conversation.symbol == 'SPY' and summary.get('last_close'):
        try:
            cases = spread_sensitivity(summary['last_close'], 1, 1, CostAssumptions(), as_of=now.date())
            context['costs'] = {'available': True, 'version': cases[0].version, 'reference_shares': 1, 'holding_days': 1,
                                'assumptions': 'Illustrative long-only paired-horizon per-share allowance. Full spread $0.01/$0.02/$0.05 assumed, not observed; commission $0; slippage 1bp per endpoint; impact $0. No implied actual size or liquidity.',
                                'as_of': now.date().isoformat(), 'cases': [{'assumed_full_spread': float(cost.assumptions.full_spread), 'total_usd_per_reference_share': float(cost.total), 'cost_bps': float(cost.cost_bps)} for cost in cases]}
        except ValueError as error:
            context['costs']['reason'] = str(error)
    news = []
    try:
        supplied = await app.state.provider.news([conversation.symbol])
        news = sorted((item for item in supplied if item.published_at <= now), key=lambda item: item.published_at, reverse=True)[:3]
    except (httpx.HTTPError, HTTPException, ValueError):
        pass
    context['news'] = [{'id': item.id, 'headline': item.headline[:240], 'summary': item.summary[:500], 'url': item.url[:1500], 'source': item.source[:120], 'published_at': item.published_at.isoformat()} for item in news]
    context['news_available'] = bool(news)
    context['news_coverage'] = 'At most three published reports; completeness, agreement and price impact are unverified. Publication time is not SELERY observation time.'
    citations.extend(Citation(label=item.headline[:240], timestamp=item.published_at, available_at=now, url=item.url[:1500], data_id=item.id,
                              provider=item.source[:120], observation=item.summary[:500]) for item in news)
    # Legacy top-level fields retained for consumers; indicators are recomputed
    # from known bars rather than trusting a chart that may include future data.
    context['provenance'] = primary.provenance.model_dump(mode='json')
    context['indicators'] = {key: value for key, value in summary.items() if key in ('ema9', 'ema21', 'rsi14', 'atr14')}
    context['capabilities'] = [cap.model_dump(mode='json') for cap in primary.capabilities]
    context['citations'] = [citation.model_dump(mode='json') for citation in citations]
    # Bound less essential detail first; never truncate a serialized JSON object.
    if len(json.dumps(context, ensure_ascii=False).encode()) > 23000:
        for detail in context['timeframes'].values():
            if 'bars' in detail: detail['bars'] = detail['bars'][-3:]
    if len(json.dumps(context, ensure_ascii=False).encode()) > 23000:
        raise ValueError('Research evidence exceeds the safe context budget; narrow this question.')
    return context, citations, last
