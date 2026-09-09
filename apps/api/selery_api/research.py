"""Bar-aligned one-reference-unit signal research, without execution state."""
from __future__ import annotations
from dataclasses import dataclass,field,replace
from datetime import datetime,timezone
from decimal import Decimal
import numpy as np
from uuid import uuid4
from zoneinfo import ZoneInfo
from selery_shared.models import Bar,Signal,ResearchRequest,ResearchReport,IndicatorPoint,Timeframe
from selery_shared.costs import CostAssumptions,calculate_costs
from selery_strategies.baseline import EmaCross
from .outcomes import score_signal
from .research_stats import descriptive_stats,block_bootstrap_ci,circular_shift_pvalue,deflated_sharpe,regime_stats


@dataclass
class ExposureStudy:
    bars: list[Bar]
    gross: list[float]=field(default_factory=list)
    net: list[float | None]=field(default_factory=list)
    exposure: list[float]=field(default_factory=list)
    costs: list[float | None]=field(default_factory=list)
    started: int=0
    completed: int=0
    discarded_overlap: int=0
    transitions: int=0
    limitations: list[str]=field(default_factory=list)


def finalized_bars(bars):
    rows=[b for b in bars if b.finalized]
    for i,b in enumerate(rows):
        if b.close<=0 or b.available_at<b.time:raise ValueError('Prices and availability must be valid')
        if i and (b.time<=rows[i-1].time or b.available_at<rows[i-1].available_at or b.feed!=rows[0].feed or b.symbol!=rows[0].symbol):
            raise ValueError('Research requires one symbol/feed and unique chronological bars with causal availability')
    return rows


def exposure_study(bars:list[Bar],signals:list[Signal],horizon:int,assumptions:CostAssumptions|None=None) -> ExposureStudy:
    """At every prior close select earliest newly known signal if inactive.

    Arrivals while active are discarded. Every bar interval exists, including
    flat and unfinished-horizon intervals. Threshold outcomes remain separate.
    """
    if horizon<1:raise ValueError('Horizon must be positive')
    rows=finalized_bars(bars);study=ExposureStudy(rows);assumptions=assumptions or CostAssumptions()
    if len(rows)<2:return study
    baseline=rows[0].close
    unique={}
    for signal in signals:
        if signal.reference_price<=0:raise ValueError('Signal reference price must be positive')
        if signal.id in unique and unique[signal.id]!=signal:raise ValueError('Conflicting immutable signal snapshots')
        unique[signal.id]=signal
    queue=sorted(unique.values(),key=lambda s:(s.available_at,s.time,s.id))
    if any(s.symbol!=rows[0].symbol or s.feed!=rows[0].feed or s.available_at<s.time for s in queue):raise ValueError('Signal provenance does not match the research dataset')
    pending=0;active=None;remaining=0;net_known=True
    def endpoint_cost(event,at,start):
        nonlocal net_known
        try:
            fee=calculate_costs(event.reference_price,1,0,assumptions,is_short=False,as_of=datetime.fromtimestamp(at,ZoneInfo('America/New_York')).date())
        except ValueError:
            net_known=False;study.limitations.append('Costed index unavailable from the first observation outside the verified regulatory fee schedule; gross observations remain available.');return 0.
        fixed=(fee.commission+fee.spread+fee.slippage+fee.market_impact)/2
        sale=(event.direction=='bearish') if start else (event.direction=='bullish')
        return float(fixed+(fee.sec+fee.taf if sale else Decimal(0)))/baseline
    for prior,current in zip(rows,rows[1:]):
        arrived=[]
        while pending<len(queue) and queue[pending].available_at<=prior.available_at and queue[pending].time<=prior.time:
            item=queue[pending];pending+=1
            if item.time<=prior.time:arrived.append(item)
        cost=0.
        if active is not None:study.discarded_overlap+=len(arrived)
        elif arrived:
            active=arrived[0];remaining=horizon;study.started+=1;study.transitions+=1
            study.discarded_overlap+=len(arrived)-1
            cost+=endpoint_cost(active,prior.available_at,True)
        direction=0 if active is None else 1 if active.direction=='bullish' else -1
        change=direction*(current.close-prior.close)/baseline
        if active is not None:
            if direction<0:
                days=(current.available_at-prior.available_at)/86400
                cost+=active.reference_price*float(assumptions.annual_borrow_rate)*days/365/baseline
            remaining-=1
            if remaining==0:
                cost+=endpoint_cost(active,current.available_at,False)
                active=None;study.completed+=1;study.transitions+=1
        study.exposure.append(float(direction));study.gross.append(change)
        study.costs.append(cost if net_known else None);study.net.append(change-cost if net_known else None)
    return study


def evaluate(request:ResearchRequest,bars,benchmark_bars,strategy=None,*,trial_sharpes=None,trial_registry_complete=False,publication_time=None)->ResearchReport:
    strategy=strategy or EmaCross();rows=finalized_bars(bars)
    if any(b.feed!=request.feed or b.symbol!=request.symbol for b in rows):raise ValueError('Research request and dataset provenance must match')
    signals=[s.model_copy(update={'horizon_bars':request.horizon_bars}) for s in strategy.evaluate(rows,request.timeframe)]
    now=datetime.now(timezone.utc);outcomes=[score_signal(s,rows,now) for s in signals]
    resolved=[o for o in outcomes if o.status in ('target_first','stop_first','neither')]
    assumptions=CostAssumptions(spread_label='Assumed SPY full spread' if request.symbol=='SPY' else 'Explicit $0.02 SPY spread proxy for this instrument; not an observed instrument spread')
    study=exposure_study(rows,signals,request.horizon_bars,assumptions)
    metrics={'hit_rate':sum(o.status=='target_first' for o in resolved)/len(resolved) if resolved else None,'sample_size':float(len(resolved)),
        'deflated_sharpe':None,'overfitting_risk':None,'benchmark_return_percent':None,'benchmark_sharpe':None,'excess_return_percent':None,'sharpe_difference':None,
        'frictionless_return_percent':float(sum(study.gross)*100) if study.gross else None,'costed_return_percent':None,
        'event_count_nonoverlap':float(study.completed),'events_started':float(study.started),'overlapping_events_discarded':float(study.discarded_overlap),
        'interval_count':float(len(study.gross)),'exposure_coverage':float(np.mean(np.abs(study.exposure))) if study.exposure else None,
        'analytical_turnover_units':float(study.transitions),'turnover_units_per_interval':study.transitions/len(study.gross) if study.gross else None}
    notes=['One-unit price-change index normalized by the first study close, additive rather than compounded account returns.',
        'Each finalized bar interval is represented; flat intervals contribute zero. Signals become eligible only after their recorded availability.',
        'Earliest available signal wins; arrivals during its fixed observed-bar horizon are discarded. No future horizon-completeness filter is applied.',
        'Costed index allocates half spread/commission/slippage/impact at each horizon endpoint, sale-side fees on their actual dated side, and elapsed ACT/365 short borrow.',
        assumptions.spread_label+'; spread sensitivities are $0.01, $0.02 and $0.05; slippage is an assumed 1 bp per endpoint.',
        'Reference close changes and thresholds are analytical observations, not obtainable transaction prices. No reinvestment or account balance exists.',
        'Sharpe and Sortino use zero hurdle and 252 daily intervals/year; Calmar uses annualized arithmetic reference return divided by maximum index drawdown, not CAGR.',
        'Profit factor and expectancy describe calendar intervals, not executed trades. Threshold hit rate excludes ambiguity and uses complete events including neither.',
        'Raw closes lack corporate-action total-return adjustment; split/dividend effects can distort all price-based research.']
    limitations=list(study.limitations)+['Historical and forward hit rates are not calibrated confidence.','IEX prices represent one venue; volume-dependent studies require SIP.','Observed-bar alignment does not prove a complete exchange calendar. Missing sessions are not imputed.']
    daily=request.timeframe==Timeframe.D1
    # Daily frequency is only credible with unique local dates and plausible gaps.
    dates=[datetime.fromtimestamp(b.time,timezone.utc).date() for b in rows]
    calendar_ok=daily and len(set(dates))==len(dates) and all(d.weekday()<5 for d in dates) and all(0<(b-a).days<=4 for a,b in zip(dates,dates[1:]))
    annual=252 if calendar_ok else None
    net_available=bool(study.net) and all(x is not None for x in study.net)
    stats=descriptive_stats(study.net,periods_per_year=annual) if net_available else descriptive_stats([])
    metrics.update(stats)
    if not annual or len(study.net)<252:limitations.append('Annualized ratios unavailable until at least 252 daily intervals with plausible session spacing; intraday annualization is intentionally unspecified.')
    if net_available:
        metrics['costed_return_percent']=float(sum(study.net)*100)
        if min(1+np.cumsum(study.net))<=0:limitations.append('Nonpositive analytical index: percentage drawdown and annualized ratios are undefined.')
        ci=block_bootstrap_ci(study.net)
        metrics['mean_interval_return_ci_low']=ci[0] if ci else None;metrics['mean_interval_return_ci_high']=ci[1] if ci else None
        if ci is None:limitations.append('Block-bootstrap interval unavailable: at least 60 intervals required.')
        raw=np.diff([b.close for b in rows])/rows[0].close
        metrics['circular_shift_pvalue']=circular_shift_pvalue(study.exposure,raw,study.costs)
        limitations.append('Circular-shift null is a descriptive alignment check with fixed cost allowances; it is not a multiple-testing-adjusted significance result.')
        dsr,reason=deflated_sharpe(study.net,trial_sharpes,registry_complete=trial_registry_complete)
        metrics['deflated_sharpe']=dsr
        if reason:limitations.append('Deflated Sharpe unavailable: '+reason+'.')
        if daily:
            regimes,reason=regime_stats(study.net,[b.close for b in rows]);metrics.update(regimes);limitations.append(reason+'.')
        if publication_time is not None:
            post=[r for r,b in zip(study.net,rows[1:]) if b.time>=publication_time]
            metrics['post_publication_intervals']=float(len(post));metrics['post_publication_mean_percent']=float(np.mean(post)*100) if len(post)>=60 else None
            if len(post)<60:limitations.append('Post-publication comparison requires at least 60 intervals after the supplied publication timestamp.')
        else:limitations.append('Publication-date comparison unavailable: no verified strategy publication timestamp supplied.')
        for spread in ('0.01','0.05'):
            sensitivity=exposure_study(rows,signals,request.horizon_bars,replace(assumptions,full_spread=Decimal(spread)))
            metrics['costed_return_spread_'+spread.replace('.','_')+'_percent']=float(sum(sensitivity.net)*100) if all(x is not None for x in sensitivity.net) else None
    series=[];cumulative=0.;known=True
    if rows:series.append(IndicatorPoint(time=rows[0].time,value=0))
    for b,r in zip(rows[1:],study.net):
        if r is None:known=False
        if known:cumulative+=r
        series.append(IndicatorPoint(time=b.time,value=cumulative*100 if known else None))
    benchmark=[];bench={b.time:b for b in finalized_bars(benchmark_bars) if b.symbol=='SPY' and b.feed==request.feed}
    if rows and all(b.time in bench and bench[b.time].available_at<=b.available_at for b in rows):
        prices=[bench[b.time].close for b in rows];baseline=prices[0]
        benchmark=[IndicatorPoint(time=b.time,value=(p/baseline-1)*100) for b,p in zip(rows,prices)]
        metrics['benchmark_return_percent']=benchmark[-1].value
        bm=descriptive_stats(np.diff(prices)/baseline,periods_per_year=annual)
        metrics['benchmark_sharpe']=bm['sharpe']
        if net_available:metrics['excess_return_percent']=metrics['costed_return_percent']-metrics['benchmark_return_percent']
        if bm['sharpe'] is not None and metrics['sharpe'] is not None:metrics['sharpe_difference']=metrics['sharpe']-bm['sharpe']
        notes.append('SPY benchmark uses exactly matched observations, the same feed and fixed-reference normalization; benchmark costs are excluded.')
    else:limitations.append('SPY comparison unavailable: require every study timestamp on the same feed with known benchmark availability; no forward fills.')
    limitations.append('Overfitting probability unavailable without a complete trial matrix and independent holdout; selecting favorable studies remains a material risk.')
    return ResearchReport(id=uuid4().hex,created_at=now,request=request,signal_count=len(signals),outcomes=outcomes,metrics=metrics,assumptions=notes,limitations=list(dict.fromkeys(limitations)),series=series,benchmark=benchmark)
