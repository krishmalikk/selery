from datetime import datetime,timedelta,timezone
from decimal import Decimal
import numpy as np
import pytest
from selery_shared.models import Bar,Feed,Signal,Timeframe,ResearchRequest
from selery_shared.costs import CostAssumptions,calculate_costs
from selery_api.research import exposure_study,evaluate
from selery_api.research_stats import descriptive_stats,index_curve,block_bootstrap_ci,circular_shift_pvalue,deflated_sharpe,regime_stats


def bars(prices,start=datetime(2025,6,2,tzinfo=timezone.utc)):
    return [Bar(symbol='SPY',time=int((start+timedelta(days=i)).timestamp()),available_at=int((start+timedelta(days=i,hours=20)).timestamp()),open=p,close=p,high=p+1,low=p-1,feed=Feed.IEX) for i,p in enumerate(prices)]


def event(data,index=0,sign='bullish',name='test'):
    b=data[index]
    return Signal(id=name,symbol='SPY',strategy='test',timeframe=Timeframe.D1,time=b.time,available_at=b.available_at,
        direction=sign,reference_price=b.close,stop=b.close*.95,target=b.close*1.1,feed=Feed.IEX,explanation='Deterministic test observation')


ZERO=CostAssumptions(full_spread=0,slippage_bps=0,annual_borrow_rate=0)


def test_calendar_exposure_includes_flat_intervals_and_discards_overlap():
    data=bars([100,102,101,104,105,106]);signals=[event(data,0),event(data,1,name='overlap')]
    result=exposure_study(data,signals,2,ZERO)
    assert result.gross==pytest.approx([.02,-.01,0,0,0])
    assert result.exposure==[1,1,0,0,0]
    assert result.completed==1 and result.discarded_overlap==1 and result.transitions==2
    assert len(result.net)==len(data)-1


def test_delayed_signal_does_not_take_earlier_price_change():
    data=bars([100,101,104,105]);s=event(data)
    s=s.model_copy(update={'available_at':data[1].available_at+1})
    result=exposure_study(data,[s],1,ZERO)
    assert result.exposure==[0,0,1]
    assert result.gross==[0,0,.01]


def test_suffix_does_not_erase_unmatured_horizon():
    data=bars([100,101,102,103,104,105]);signals=[event(data)]
    full=exposure_study(data,signals,4)
    prefix=exposure_study(data[:3],signals,4)
    assert prefix.gross==full.gross[:2] and prefix.net==full.net[:2]
    assert prefix.started==1 and prefix.completed==0


def test_regulatory_dates_differ_at_horizon_ends():
    data=bars([100,100],datetime(2025,5,13,tzinfo=timezone.utc))
    long=exposure_study(data,[event(data)],1,ZERO)
    short=exposure_study(data,[event(data,sign='bearish')],1,ZERO)
    # SEC changed from $27.80/million to zero May 14; short sale-side allowance
    # uses May 13 while long sale-side allowance uses May 14.
    assert short.costs[0]-long.costs[0]==pytest.approx(.0000278)


def test_paired_cost_sum_matches_shared_cost_formula():
    data=bars([100,101,102,103]);a=CostAssumptions()
    result=exposure_study(data,[event(data,sign='bearish')],3,a)
    expected=calculate_costs(100,1,3,a,is_short=True,as_of=datetime(2025,6,2).date())
    assert sum(result.costs)==pytest.approx(float(expected.total)/100)


def test_unknown_fee_date_preserves_gross_but_marks_net_missing():
    data=bars([100,101,102],datetime(2027,1,4,tzinfo=timezone.utc))
    result=exposure_study(data,[event(data)],1)
    assert result.gross==[.01,0]
    assert result.net==[None,None] and result.limitations


def test_stats_hand_computed_drawdown_and_no_fake_infinity():
    result=descriptive_stats([.1,-.2,.1,0])
    assert index_curve([.1,-.2,.1,0])==pytest.approx([1,1.1,.9,1,1])
    assert result['max_drawdown']==pytest.approx((.9/1.1-1)*100)
    assert result['longest_underwater_bars']==3 and result['underwater_fraction']==.75
    assert result['profit_factor']==1 and result['sharpe'] is None
    assert descriptive_stats([.1,.1])['profit_factor'] is None
    assert descriptive_stats([-2])['max_drawdown'] is None


def test_annualization_requires_full_year_and_correct_spacing_opt_in():
    r=np.tile([.01,-.005],126)
    stats=descriptive_stats(r,periods_per_year=252)
    assert stats['sharpe']==pytest.approx(np.mean(r)/np.std(r,ddof=1)*np.sqrt(252))
    assert descriptive_stats(r[:251],periods_per_year=252)['sharpe'] is None
    assert descriptive_stats(r)['sharpe'] is None


def test_bootstrap_and_shuffle_deterministic_with_sample_thresholds():
    r=np.tile([.01,-.005,.002],40)
    assert block_bootstrap_ci(r)==block_bootstrap_ci(r)
    assert block_bootstrap_ci(r[:20]) is None
    exposure=np.tile([1,0,-1],40)
    p=circular_shift_pvalue(exposure,r,np.zeros(120))
    assert 0<p<=1 and p==circular_shift_pvalue(exposure,r,np.zeros(120))


def test_deflated_sharpe_requires_complete_registry():
    r=np.random.default_rng(12).normal(.001,.02,300)
    assert deflated_sharpe(r,[.1,.2])[0] is None
    value,reason=deflated_sharpe(r,[.1,.2,.3],registry_complete=True)
    assert 0<=value<=1 and reason is None
    assert deflated_sharpe(r,[.1,.1],registry_complete=True)[0] is None


def test_regime_minimum_history_and_finite_validation():
    assert regime_stats([.01]*10,[100]*11)[0]=={}
    with pytest.raises(ValueError):descriptive_stats([float('nan')])


def test_report_matches_full_bar_grid_and_rejects_missing_benchmark():
    class Fixed:
        def evaluate(self,rows,timeframe):return [event(rows)]
    data=bars([100,101,102,101,103])
    request=ResearchRequest(horizon_bars=2)
    result=evaluate(request,data,data,strategy=Fixed())
    assert [x.time for x in result.series]==[b.time for b in data]
    assert [x.time for x in result.benchmark]==[b.time for b in data]
    assert result.metrics['benchmark_return_percent']==pytest.approx(3)
    assert result.metrics['sharpe'] is None
    missing=evaluate(request,data,data[:-1],strategy=Fixed())
    assert missing.metrics['benchmark_return_percent'] is None
    assert any('no forward fills' in text for text in missing.limitations)
