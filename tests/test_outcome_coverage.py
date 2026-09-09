from datetime import datetime,timezone
from selery_api.outcomes import score_signal
from selery_shared.models import Bar,Feed,Signal,Timeframe

def test_missing_regular_session_bar_does_not_become_favorable_outcome():
    time=int(datetime(2026,9,8,15,0,tzinfo=timezone.utc).timestamp())
    signal=Signal(id='coverage',symbol='SPY',strategy='test',timeframe=Timeframe.M5,time=time-300,available_at=time,direction='bullish',reference_price=100,stop=95,target=105,feed=Feed.IEX,explanation='test')
    gap=Bar(symbol='SPY',time=time+300,available_at=time+600,open=100,high=110,low=99,close=108,feed=Feed.IEX)
    assert score_signal(signal,[gap]).status=='incomplete'

def test_duplicate_bar_does_not_count_twice_toward_horizon():
    signal=Signal(id='duplicate',symbol='SPY',strategy='test',timeframe=Timeframe.M5,time=0,available_at=300,direction='bullish',reference_price=100,stop=90,target=110,feed=Feed.IEX,explanation='test',horizon_bars=2)
    bar=Bar(symbol='SPY',time=300,available_at=600,open=100,high=101,low=99,close=100,feed=Feed.IEX)
    outcome=score_signal(signal,[bar,bar])
    assert outcome.status=='pending' and outcome.bars_observed==1
