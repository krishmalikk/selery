import pytest
from selery_shared.models import Bar,Feed
from selery_shared.indicators import chart_indicators
from selery_shared.structure import structure_levels

def make_bars(n):
    return [Bar(symbol='SPY',time=1788791400+i*300,available_at=1788791700+i*300,open=100+i*.1,high=102+i*.1,low=98+i*.1,close=100+i*.1+(i%5)*.1,feed=Feed.IEX) for i in range(n)]

def test_extended_indicator_future_invariance():
    prefix=chart_indicators(make_bars(100),Feed.IEX)
    full=chart_indicators(make_bars(120),Feed.IEX)
    for key,points in prefix.items():
        for a,b in zip(points,full[key][:100]):
            assert a.time==b.time
            if a.value is None:assert b.value is None
            else:assert a.value==pytest.approx(b.value)

def test_pivot_not_backdated():
    bars=make_bars(10);bars[4].low=1
    result=structure_levels(bars,3)['support']
    assert result[4].value is None
    assert result[7].value==1
