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
    assert rows[2].reason=='needs SIP data'
    b=panel['SPY'][-1]
    assert rows[1].values['SPY']==pytest.approx((b.close-b.open)/(b.high-b.low+.001))


def test_alpha_future_suffix_and_finite_or_null():
    panel={s:history(s,feed=Feed.SIP) for s in ('SPY','QQQ','DIA')}
    time=panel['SPY'][220].available_at
    full=alpha_features(panel,Feed.SIP,time,adjusted=True)
    cut=alpha_features({s:b[:221] for s,b in panel.items()},Feed.SIP,time,adjusted=True)
    assert full==cut
    assert all(set(r.values)=={'SPY','QQQ','DIA'} or not r.enabled and r.reason for r in full)
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


def sourced_context(panel):
    from selery_strategies.alpha import AlphaObservation
    # Explicitly synthetic test observations, never provider substitutes.
    return [AlphaObservation(s,b.time,b.available_at,b.feed,'synthetic test',vwap=(b.open+b.close)/2,
        dollar_volume=b.volume*(b.open+b.close)/2,market_cap=(100+i)*1e6,
        sector='A' if s in ('SPY','QQQ') else 'B',industry='A',subindustry='A')
        for s,seq in panel.items() for i,b in enumerate(seq)]


def test_every_nonbinary_formula_callable_with_explicit_context():
    from selery_strategies.alpha import BINARY
    panel={s:history(s,n=280,feed=Feed.SIP) for s in ('SPY','QQQ','DIA')}
    results=alpha_features(panel,Feed.SIP,panel['SPY'][-1].available_at,adjusted=True,observations=sourced_context(panel))
    assert len(results)==101-len(BINARY)==87
    assert all(r.enabled for r in results)
    assert all(set(r.values)==set(panel) for r in results)
    assert all('binary' in r.reason for r in alpha_catalog(Feed.SIP) if not r.enabled)


def test_vwap_dollar_volume_and_classification_are_not_fabricated():
    panel={s:history(s,feed=Feed.SIP) for s in ('SPY','QQQ')}
    result=alpha_features(panel,Feed.SIP,panel['SPY'][-1].available_at,adjusted=True,numbers=[5,7,48,56])
    assert all(not r.enabled and 'Missing point-in-time inputs' in r.reason for r in result)
    context=sourced_context(panel)
    computed=alpha_features(panel,Feed.SIP,panel['SPY'][-1].available_at,adjusted=True,numbers=[41],observations=context)
    b=panel['SPY'][-1]
    assert computed[0].values['SPY']==pytest.approx((b.high*b.low)**.5-(b.open+b.close)/2)


def test_all_contextual_alphas_future_suffix_invariance():
    panel={s:history(s,feed=Feed.SIP) for s in ('SPY','QQQ','DIA')};context=sourced_context(panel)
    cutoff=panel['SPY'][265].available_at
    full=alpha_features(panel,Feed.SIP,cutoff,adjusted=True,observations=context)
    prefix=alpha_features({s:rows[:266] for s,rows in panel.items()},Feed.SIP,cutoff,adjusted=True,observations=[o for o in context if o.available_at<=cutoff])
    assert full==prefix


def test_ic_decay_only_matured_point_in_time_labels():
    from selery_strategies.alpha import AlphaResult,information_coefficient_decay
    panel={s:history(s,n=30) for s in ('SPY','QQQ','DIA')}
    point=panel['SPY'][20]
    future={s:seq[21].close/seq[20].close-1 for s,seq in panel.items()}
    snapshot=AlphaResult('alpha_test',True,values=future,available_at=point.available_at,feed='iex',observed_at=point.time)
    before=information_coefficient_decay([snapshot],panel,point.available_at,horizons=(1,5))
    assert all(r['mean_rank_ic'] is None for r in before['horizons'])
    after=information_coefficient_decay([snapshot],panel,panel['SPY'][21].available_at,horizons=(1,5))
    assert after['horizons'][0]['mean_rank_ic']==pytest.approx(1)
    assert after['horizons'][1]['mean_rank_ic'] is None
    with pytest.raises(ValueError,match='Duplicate'):information_coefficient_decay([snapshot,snapshot],panel,panel['SPY'][-1].available_at)


def test_alpha_primitives_have_correct_axes_ties_and_fractional_windows():
    import pandas as pd
    from selery_strategies.alpha import rank,ts_rank,decay,neutral,delay
    frame=pd.DataFrame({'A':[1.,3.,2.],'B':[1.,5.,9.],'C':[3.,7.,8.]})
    assert rank(frame).iloc[0].tolist()==pytest.approx([.5,.5,1.])
    assert ts_rank(frame,3).iloc[-1].tolist()==pytest.approx([2.,3.,3.])
    assert decay(frame,3.8).iloc[-1]['A']==pytest.approx((1+6+6)/6)
    assert delay(frame,1.9).iloc[-1]['B']==5
    group=pd.DataFrame({'A':['x']*3,'B':['x']*3,'C':['y']*3})
    assert neutral(frame,group).iloc[-1].tolist()==pytest.approx([-3.5,3.5,0])
