from datetime import datetime,timedelta,timezone
from math import sin
import pytest
from selery_shared.models import Bar,Feed,Timeframe
from selery_strategies.advanced import Context,Observation,ADVANCED,evaluate_advanced
from selery_strategies.alpha import IMPLEMENTED,PRICE_ONLY,alpha_catalog,alpha_features
from selery_strategies.library import get_strategy


def history(symbol='SPY',n=280,feed=Feed.IEX):
    dates=[];day=datetime(2023,1,2,tzinfo=timezone.utc)
    while len(dates)<n:
        if day.weekday()<5:dates.append(int(day.timestamp()))
        day+=timedelta(days=1)
    phase=0 if symbol=='SPY' else 1 if symbol=='QQQ' else 2
    return [Bar(symbol=symbol,time=t,available_at=t+80000,open=100+i*.07+sin(i*.3+phase),
        high=102+i*.07+sin(i*.3+phase),low=98+i*.07+sin(i*.3+phase),
        close=100+i*.07+sin(i*.3+phase)+sin(i*.17),volume=1000+i*3+100*sin(i*.2+phase),feed=feed) for i,t in enumerate(dates)]

@pytest.mark.parametrize('name',ADVANCED)
def test_advanced_inputs_fail_explicitly(name):
    result=evaluate_advanced(name,history(),Timeframe.D1)
    assert not result.enabled and result.reason and result.code


def test_earnings_observation_not_known_early():
    data=history();last=data[-1]
    event=Observation('SPY',last.time,last.available_at+1,{'standardized_surprise':2},'test',Feed.IEX)
    assert not evaluate_advanced('earnings_drift',data,Timeframe.D1,Context(observations=[event])).enabled
    known=Observation('SPY',last.time,last.available_at-1,{'standardized_surprise':2},'test',Feed.IEX)
    result=evaluate_advanced('earnings_drift',data,Timeframe.D1,Context(observations=[known]))
    assert result.enabled and len(result.signals)==1
    assert result.signals[0].available_at==last.available_at


def test_factor_missing_member_cannot_sneak_into_rank():
    data=history();last=data[-1]
    o=Observation('SPY',last.time,last.available_at,{'book_to_market':1,'market_cap':100,'profitability':.2,'momentum_12_1':.1,'realized_volatility':.2},'test',Feed.IEX)
    ctx=Context(universe=('SPY','QQQ','DIA'),universe_available_at=1,observations=[o])
    assert evaluate_advanced('factor_tilts',data,Timeframe.D1,ctx).code=='missing_fundamentals'


def test_alpha_coverage_and_volume_guard():
    assert len(alpha_catalog(Feed.IEX))==101
    assert sum(x.enabled for x in alpha_catalog(Feed.SIP))==len(IMPLEMENTED)
    assert sum(x.enabled for x in alpha_catalog(Feed.IEX))==len(PRICE_ONLY)
    panel={s:history(s) for s in ('SPY','QQQ')}
    rows=alpha_features(panel,Feed.IEX,panel['SPY'][-1].available_at,adjusted=True,numbers=[6,101,100])
    assert rows[0].reason=='needs SIP data'
    assert rows[2].reason.startswith('Formula not implemented')
    b=panel['SPY'][-1]
    assert rows[1].values['SPY']==pytest.approx((b.close-b.open)/(b.high-b.low+.001))


def test_alpha_future_suffix_and_finite_or_null():
    panel={s:history(s,feed=Feed.SIP) for s in ('SPY','QQQ','DIA')}
    time=panel['SPY'][220].available_at
    full=alpha_features(panel,Feed.SIP,time,adjusted=True)
    cut=alpha_features({s:b[:221] for s,b in panel.items()},Feed.SIP,time,adjusted=True)
    assert full==cut
    assert all(set(r.values)=={'SPY','QQQ','DIA'} for r in full)
    assert any(r.values['SPY'] is not None for r in full)


def test_alpha_does_not_forward_fill_missing_dates():
    panel={'SPY':history(),'QQQ':history('QQQ')[1:]}
    with pytest.raises(ValueError,match='aligned'):alpha_features(panel,Feed.IEX,panel['SPY'][-1].available_at,adjusted=True)


def test_alpha_price_features_ignore_volume_mutation():
    panel={s:history(s) for s in ('SPY','QQQ')};time=panel['SPY'][-1].available_at
    original=alpha_features(panel,Feed.IEX,time,adjusted=True,numbers=sorted(PRICE_ONLY))
    changed=alpha_features({s:[b.model_copy(update={'volume':999999}) for b in rows] for s,rows in panel.items()},Feed.IEX,time,adjusted=True,numbers=sorted(PRICE_ONLY))
    assert original==changed

@pytest.mark.parametrize('month,day,utc_hour',[(3,6,14),(3,9,13),(11,2,14)])
def test_opening_range_new_york_dst(month,day,utc_hour):
    # Warm up on prior data and make the local 10:00 bar cross the 09:30 window.
    start=datetime(2026,month,day,utc_hour,30,tzinfo=timezone.utc)
    data=[]
    for i in range(-20,10):
        t=int((start+timedelta(minutes=5*i)).timestamp());p=103 if i>=6 else 100
        data.append(Bar(symbol='SPY',time=t,available_at=t+300,open=p,close=p,high=p+.5,low=p-.5,feed=Feed.IEX))
    signals=get_strategy('opening_range').evaluate(data,Timeframe.M5)
    assert len(signals)==1 and signals[0].time==int((start+timedelta(minutes=30)).timestamp())


def test_pairs_degenerate_relationship_is_unavailable():
    panel={s:[b.model_copy(update={'open':100,'close':100,'high':101,'low':99}) for b in history(s)] for s in ('SPY','QQQ')}
    ctx=Context(series=panel,universe=('SPY','QQQ'),universe_available_at=1,adjusted_daily=True)
    result=evaluate_advanced('pairs',panel['SPY'],Timeframe.D1,ctx)
    assert result.code in ('missing_dependency','degenerate_data')


def test_seasonal_calendar_future_schedule_cannot_leak():
    from selery_strategies.advanced import seasonal_cohorts
    data=history(n=280);calendar=[b.time for b in history(n=330)]
    last=data[-1]
    event=Observation('FOMC',last.time,last.available_at+1,{'fomc_time':float(calendar[280])},'test',Feed.IEX)
    ctx=Context(calendar=calendar,calendar_available_at=1,observations=[event])
    result=seasonal_cohorts(data,ctx)
    assert result.enabled and result.features['fomc_pre_active']==0
    ctx.observations=[Observation('FOMC',last.time,last.available_at,{'fomc_time':float(calendar[280])},'test',Feed.IEX)]
    known=seasonal_cohorts(data,ctx)
    assert known.features['fomc_pre_active']==1
    assert known.features['fomc_pre_n']==0
    assert any('minimum 30' in text for text in known.diagnostics)
