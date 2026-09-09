from datetime import datetime,timezone
from selery_shared.models import Bar,Signal,Outcome,OutcomeSummary,Feed

def score_signal(signal:Signal,bars:list[Bar],now:datetime|None=None)->Outcome:
    """Observe post-signal bars, without inventing a within-bar price path."""
    now=now or datetime.now(timezone.utc)
    observed=sorted({b.time:b for b in bars if b.finalized and b.time>=signal.available_at and b.feed==signal.feed and b.symbol==signal.symbol and b.available_at<=int(now.timestamp())}.values(),key=lambda b:b.time)
    window=observed[:signal.horizon_bars]
    favorable=adverse=0.0
    for index,bar in enumerate(window):
        bullish=signal.direction=='bullish'
        favorable=max(favorable,100*((bar.high-signal.reference_price) if bullish else (signal.reference_price-bar.low))/signal.reference_price)
        adverse=min(adverse,100*((bar.low-signal.reference_price) if bullish else (signal.reference_price-bar.high))/signal.reference_price)
        target=bar.high>=signal.target if bullish else bar.low<=signal.target
        stop=bar.low<=signal.stop if bullish else bar.high>=signal.stop
        if target or stop:
            status='ambiguous' if target and stop else 'target_first' if target else 'stop_first'
            return Outcome(signal_id=signal.id,status=status,evaluated_at=now,bars_observed=index+1,resolved_at=bar.available_at,max_favorable_percent=favorable,max_adverse_percent=adverse,reason='Both thresholds occurred within one bar; sequence is unknown.' if status=='ambiguous' else None)
    status='neither' if len(window)==signal.horizon_bars else 'pending'
    return Outcome(signal_id=signal.id,status=status,evaluated_at=now,bars_observed=len(window),max_favorable_percent=favorable if window else None,max_adverse_percent=adverse if window else None,reason='Horizon counts subsequent observed finalized bars; exchange gaps are not imputed.' if status=='pending' else None)

def summarize(strategy,feed,outcomes,historical=None):
    counts={key:sum(o.status==key for o in outcomes) for key in ('target_first','stop_first','neither','ambiguous')}
    denominator=counts['target_first']+counts['stop_first']+counts['neither']
    return OutcomeSummary(strategy=strategy,feed=feed,matured=sum(counts.values()),**counts,hit_rate=counts['target_first']/denominator if denominator else None,historical_hit_rate=historical,comparison_reason=None if historical is not None else 'A matching feed/version/horizon historical cohort is not available.')
