from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import pytest
from selery_shared.models import Bar,Feed,Signal,Timeframe
from selery_api.outcomes import score_signal,uncovered_session_reason

NY=ZoneInfo('America/New_York')
def stamp(iso):return int(datetime.fromisoformat(iso).replace(tzinfo=NY).timestamp())

@pytest.mark.parametrize('before,after',[
    ('2026-03-06T16:00','2026-03-09T09:30'),
    ('2026-10-30T16:00','2026-11-02T09:30'),
    ('2026-09-08T16:00','2026-09-09T09:30'),
    ('2026-09-08T10:05','2026-09-08T10:05'),
])
def test_known_closed_hours_and_dst_weekends_are_allowed(before,after):
    assert uncovered_session_reason(stamp(before),stamp(after)) is None

@pytest.mark.parametrize('before,after',[
    ('2026-09-08T10:05','2026-09-09T09:30'),
    ('2026-09-08T16:00','2026-09-09T10:00'),
    ('2026-09-08T16:00','2026-09-10T09:30'),
    ('2026-03-06T15:55','2026-03-09T09:30'),
    ('2026-09-08T10:05','2026-09-08T10:10'),
])
def test_missing_session_sections_fail_closed(before,after):
    assert uncovered_session_reason(stamp(before),stamp(after))


def test_holiday_is_unknown_without_calendar_instead_of_assumed_open_or_closed():
    # Good Friday could legitimately explain this missing weekday, but no
    # authoritative calendar has been supplied to establish that explanation.
    reason=uncovered_session_reason(stamp('2026-04-02T16:00'),stamp('2026-04-06T09:30'))
    assert 'holiday or early close' in reason


def test_later_threshold_cannot_override_missing_earlier_day():
    start=stamp('2026-09-08T10:00')
    event=Signal(id='coverage',symbol='SPY',strategy='test',timeframe=Timeframe.M5,time=start,available_at=start+300,
        direction='bullish',reference_price=100,stop=99,target=101,feed=Feed.IEX,explanation='Test observation')
    next_time=stamp('2026-09-09T10:00')
    later=Bar(symbol='SPY',time=next_time,available_at=next_time+300,open=100,high=102,low=100,close=101,feed=Feed.IEX)
    result=score_signal(event,[later],datetime(2026,9,10,tzinfo=timezone.utc))
    assert result.status=='incomplete' and result.resolved_at is None and result.bars_observed==0


def test_missing_daily_session_also_stays_incomplete():
    start=stamp('2026-09-07T00:00')
    event=Signal(id='daily-gap',symbol='SPY',strategy='test',timeframe=Timeframe.D1,time=start,available_at=stamp('2026-09-07T20:00'),
        direction='bullish',reference_price=100,stop=99,target=101,feed=Feed.IEX,explanation='Test observation')
    later=Bar(symbol='SPY',time=stamp('2026-09-09T00:00'),available_at=stamp('2026-09-09T20:00'),open=100,high=102,low=100,close=101,feed=Feed.IEX)
    result=score_signal(event,[later],datetime(2026,9,10,tzinfo=timezone.utc))
    assert result.status=='incomplete'
