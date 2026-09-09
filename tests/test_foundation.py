from datetime import datetime,timezone
import pytest
from selery_shared.models import Bar,Feed,Timeframe
from selery_shared.indicators import ema,rsi,require_capability,chart_indicators,VOLUME_FEATURES
from selery_strategies.baseline import EmaCross
from selery_api.config import Config
from selery_api.providers import FixtureProvider

def bars(values):
    return [Bar(symbol='SPY',time=i*300,available_at=(i+1)*300,open=x,high=x+1,low=x-1,close=x,feed=Feed.IEX) for i,x in enumerate(values)]

def test_math_warmup_and_flat_rsi():
    assert ema([1,2,3,4],3)==[None,None,2,3]
    assert rsi([5]*20)[14:]==[50]*6

def test_iex_gates_every_volume_feature():
    for feature in VOLUME_FEATURES:
        with pytest.raises(ValueError,match='needs SIP data'):require_capability(feature,Feed.IEX)
    assert 'vwap' not in chart_indicators(bars([100]*30),Feed.IEX)

def test_future_changes_do_not_rewrite_signals():
    values=[100+i for i in range(30)]+[130-i*2 for i in range(30)]+[70+i*3 for i in range(30)]
    strategy=EmaCross()
    prefix=strategy.evaluate(bars(values[:60]),Timeframe.M5)
    full=strategy.evaluate(bars(values),Timeframe.M5)
    assert prefix==[s for s in full if s.time<60*300]
    unfinished=bars(values)
    unfinished[-1].finalized=False
    assert strategy.evaluate(unfinished,Timeframe.M5)==strategy.evaluate(unfinished[:-1],Timeframe.M5)

def test_live_host_rejected_before_credentials(monkeypatch):
    monkeypatch.setenv('ALPACA_ENDPOINT','https://api.alpaca.markets')
    with pytest.raises(RuntimeError,match='paper host'):Config.load()

@pytest.mark.asyncio
async def test_recorded_feeds_are_separate():
    provider=FixtureProvider()
    iex=await provider.bars('SPY',Timeframe.D1,Feed.IEX)
    sip=await provider.bars('SPY',Timeframe.D1,Feed.SIP)
    assert iex[-1].feed==Feed.IEX and sip[-1].feed==Feed.SIP
    assert iex[-1].volume!=sip[-1].volume
    assert all(b.available_at>b.time for b in iex)
