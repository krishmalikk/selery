"""Signal-event studies. The return series is an analytical exposure model, never fills."""
from datetime import datetime,timezone,date
from uuid import uuid4
import numpy as np
from selery_shared.models import ResearchRequest,ResearchReport,IndicatorPoint
from selery_shared.costs import CostAssumptions,calculate_costs
from selery_strategies.baseline import EmaCross
from .outcomes import score_signal

def evaluate(request:ResearchRequest,bars,benchmark_bars,strategy=None)->ResearchReport:
    strategy=strategy or EmaCross()
    signals=strategy.evaluate(bars,request.timeframe)
    signals=[s.model_copy(update={'horizon_bars':request.horizon_bars}) for s in signals]
    now=datetime.now(timezone.utc)
    outcomes=[score_signal(s,bars,now) for s in signals]
    resolved=[o for o in outcomes if o.status in ('target_first','stop_first','neither')]
    metrics={'hit_rate':sum(o.status=='target_first' for o in resolved)/len(resolved) if resolved else None,'sample_size':float(len(resolved)),'sharpe':None,'sortino':None,'calmar':None,'max_drawdown':None,'deflated_sharpe':None,'overfitting_risk':None,'frictionless_return_percent':None,'costed_return_percent':None,'benchmark_return_percent':None}
    assumptions=['Research event study, not realized performance.','Signals are observed at finalized bar availability; reference close is not an executable price.','Fixed one-unit analytical exposure; overlapping signals are excluded from the return series.','SPY full spread assumption is $0.02; costs include slippage, impact, commission and dated regulatory allowances.','Threshold hit rate uses complete unambiguous events including neither; ambiguous events are reported separately.','Raw prices; corporate-action-adjusted total returns are not available in this study.']
    limitations=['Historical and forward signal hit rates are not calibrated probabilities.','IEX prices represent one venue; IEX volume-dependent research is disabled.','Regime and publication-date studies require longer point-in-time coverage.','Deflated Sharpe needs an adequate non-overlapping sample and complete parameter-trial registry.']
    series=[];benchmark=[];gross=net=1.0;free_after=-1;returns=[]
    for signal in signals:
        future=[b for b in bars if b.finalized and b.time>=signal.available_at][:request.horizon_bars]
        if len(future)<request.horizon_bars or signal.available_at<=free_after:continue
        end=future[-1]
        direction=1 if signal.direction=='bullish' else -1
        change=direction*(end.close/signal.reference_price-1)
        try:
            costs=calculate_costs(signal.reference_price,1,max(0,(end.available_at-signal.available_at)/86400),CostAssumptions(),is_short=direction<0,as_of=datetime.fromtimestamp(end.available_at,timezone.utc).date())
        except ValueError:
            limitations.append('An event falls outside the verified fee schedule and was excluded from costed statistics.');continue
        cost=float(costs.total)/signal.reference_price
        gross*=1+change;net*=1+change-cost;returns.append(change-cost)
        series.append(IndicatorPoint(time=end.time,value=(net-1)*100));free_after=end.available_at
    if series:
        metrics['frictionless_return_percent']=(gross-1)*100;metrics['costed_return_percent']=(net-1)*100
        values=np.array([1]+[1+p.value/100 for p in series]);dd=values/np.maximum.accumulate(values)-1
        metrics['max_drawdown']=float(dd.min()*100)
        metrics['cvar_95']=float(np.mean(np.sort(returns)[:max(1,int(len(returns)*0.05))])*100)
        metrics['event_count_nonoverlap']=float(len(returns))
        if len(returns)>=10:
            rng=np.random.default_rng(42)
            samples=np.mean(rng.choice(returns,size=(1000,len(returns)),replace=True),axis=1)
            metrics['mean_event_return_ci_low']=float(np.percentile(samples,2.5)*100);metrics['mean_event_return_ci_high']=float(np.percentile(samples,97.5)*100)
    common=[b for b in benchmark_bars if bars and bars[0].time<=b.time<=bars[-1].time]
    if len(common)>1:
        benchmark=[IndicatorPoint(time=b.time,value=(b.close/common[0].close-1)*100) for b in common]
        metrics['benchmark_return_percent']=benchmark[-1].value
    limitations.append('Annualized Sharpe/Sortino/Calmar are unavailable: event horizons are irregular, not a calendar-aligned exposure return series.')
    return ResearchReport(id=uuid4().hex,created_at=now,request=request,signal_count=len(signals),outcomes=outcomes,metrics=metrics,assumptions=assumptions,limitations=list(dict.fromkeys(limitations)),series=series,benchmark=benchmark)
