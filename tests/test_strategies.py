from math import sin
import pytest
from selery_shared.models import Bar,Feed,Timeframe
from selery_strategies.library import PRICE_STRATEGIES, adx, get_strategy, strategy_catalog


def bars(n=240):
    return [Bar(symbol='SPY',time=1700000000+i*86400,available_at=1700000000+(i+1)*86400,
        open=100+5*sin(i/6),close=100+5*sin(i/6)+.1,high=101+5*sin(i/6),low=99+5*sin(i/6),feed=Feed.IEX) for i in range(n)]

@pytest.mark.parametrize('name',PRICE_STRATEGIES)
def test_strategy_is_causal_and_finalized(name):
    data=bars(); strategy=get_strategy(name,Feed.IEX)
    prefix=strategy.evaluate(data[:140],Timeframe.D1)
    full=strategy.evaluate(data,Timeframe.D1)
    assert [s for s in full if s.time<=data[139].time]==prefix
    assert strategy.evaluate(data[:140]+[b.model_copy(update={'finalized':False}) for b in data[140:]],Timeframe.D1)==prefix
    for signal in full:
        assert signal.confidence is None and signal.available_at>=signal.time
        assert signal.stop>0 and signal.target>0
        assert signal.reference_price==next(b.close for b in data if b.time==signal.time)

@pytest.mark.parametrize('name',['ema_cross','sma_cross','macd','heikin_ashi','psar'])
def test_oscillating_fixture_has_events(name):
    assert get_strategy(name).evaluate(bars(),Timeframe.D1)


def test_feed_guard_and_catalog():
    assert not next(x for x in strategy_catalog(Feed.IEX) if x.id=='volume_confirmation').enabled
    with pytest.raises(ValueError,match='needs SIP data'):get_strategy('volume_confirmation',Feed.IEX)
    with pytest.raises(ValueError,match='feed'):get_strategy('ema_cross',Feed.SIP).evaluate(bars(),Timeframe.D1)


def test_invalid_order_and_availability_fail_closed():
    data=bars()
    with pytest.raises(ValueError):get_strategy('macd').evaluate(data[::-1],Timeframe.D1)
    with pytest.raises(ValueError):get_strategy('macd').evaluate(data+[data[-1]],Timeframe.D1)
    data[20]=data[20].model_copy(update={'available_at':data[20].time-1})
    with pytest.raises(ValueError):get_strategy('macd').evaluate(data,Timeframe.D1)


def test_adx_flat_warmup():
    data=[b.model_copy(update={'open':100,'close':100,'high':100,'low':100}) for b in bars(50)]
    values=adx(data)
    assert values[:27]==[None]*27
    assert values[27:]==[0]*23
