"""Point-in-time multiasset research. Missing inputs are explicit, never inferred."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from zoneinfo import ZoneInfo
import numpy as np
from selery_shared.indicators import atr
from selery_shared.models import Bar, Feed, Signal, StrategyInfo, Timeframe
from .library import make_signal, validate_bars


@dataclass(frozen=True)
class Observation:
    symbol: str
    observed_at: int
    available_at: int
    values: dict[str,float]
    source: str
    feed: Feed


@dataclass
class Context:
    """Provider adapters must supply point-in-time membership and adjusted daily bars."""
    series: dict[str,list[Bar]] = field(default_factory=dict)
    observations: list[Observation] = field(default_factory=list)
    universe: tuple[str,...] = ()
    universe_available_at: int | None = None
    adjusted_daily: bool = False
    calendar: list[int] = field(default_factory=list)
    calendar_available_at: int | None = None


@dataclass
class Evaluation:
    enabled: bool
    reason: str | None = None
    code: str | None = None
    signals: list[Signal] = field(default_factory=list)
    features: dict[str,float] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)


def unavailable(code: str, reason: str) -> Evaluation:
    return Evaluation(False,reason,code)


ADVANCED = {
    'pairs': ('Pairs cointegration',['aligned_adjusted_daily_bars','point_in_time_universe']),
    'momentum_12_1': ('Cross-sectional 12–1 momentum',['253_adjusted_daily_bars','point_in_time_universe']),
    'factor_tilts': ('Fundamental factor tilts',['point_in_time_fundamentals','point_in_time_universe']),
    'earnings_drift': ('Post-earnings drift',['point_in_time_earnings_surprise']),
    'volatility_gate': ('Volatility regime gate',['vix_term_structure','252_iv_observations']),
    'seasonality': ('Seasonal research',['exchange_calendar','historical_daily_bars']),
}


def advanced_catalog(feed: Feed) -> list[StrategyInfo]:
    return [StrategyInfo(id=k,name=v[0],description='Requires explicit point-in-time research context',enabled=False,
        reason='Required point-in-time inputs have not been supplied',requires=v[1]) for k,v in ADVANCED.items()]


def known_observations(ctx: Context,as_of: int,feed: Feed) -> list[Observation]:
    for row in ctx.observations:
        if not row.source or row.available_at < row.observed_at or not all(isfinite(x) for x in row.values.values()):
            raise ValueError('Observations require finite values, source and causal availability')
    return sorted([o for o in ctx.observations if o.available_at<=as_of and o.observed_at<=as_of and o.feed==feed],key=lambda o:(o.observed_at,o.available_at))


def evaluate_advanced(strategy_id: str,bars: list[Bar],timeframe: Timeframe,ctx: Context | None=None) -> Evaluation:
    if strategy_id not in ADVANCED: raise ValueError('Unknown advanced strategy')
    if not bars: return unavailable('missing_bars','No finalized bars supplied')
    data=validate_bars(bars)
    if not data:return unavailable('missing_bars','No finalized bars supplied')
    b=data[-1];as_of=b.available_at;ctx=ctx or Context()
    if timeframe!=Timeframe.D1:return unavailable('unsupported_timeframe','Advanced studies require finalized daily bars')
    known=known_observations(ctx,as_of,b.feed)
    def signal(sign: int,features: dict[str,float],reason: str):
        volatility=atr(data)[-1]
        if volatility is None:return unavailable('warmup','At least 14 bars are required for reference thresholds')
        return Evaluation(True,signals=[make_signal(strategy_id,b,timeframe,sign,volatility,reason,features)],features=features)
    def panel():
        if not ctx.adjusted_daily:return None
        if not ctx.universe or ctx.universe_available_at is None or ctx.universe_available_at>as_of:return None
        result={}
        for symbol in ctx.universe:
            series=validate_bars(ctx.series.get(symbol,[]),b.feed)
            result[symbol]=[x for x in series if x.available_at<=as_of and x.time<=b.time]
        return result
    if strategy_id=='pairs':
        rows=panel()
        if rows is None or len(rows)!=2 or b.symbol not in rows:
            return unavailable('missing_inputs','Two-symbol point-in-time universe and adjusted daily histories are required')
        other=next(s for s in rows if s!=b.symbol)
        a={x.time:x for x in rows[b.symbol]};z={x.time:x for x in rows[other]}
        dates=sorted(a.keys()&z.keys())[-253:]
        if len(dates)<253 or dates[-1]!=b.time:return unavailable('insufficient_history','253 aligned daily observations ending at the current bar are required')
        try:from statsmodels.tsa.stattools import coint
        except ImportError:return unavailable('missing_dependency','Install the audited statsmodels dependency for Engle–Granger testing')
        x=np.log([z[t].close for t in dates]);y=np.log([a[t].close for t in dates])
        if np.std(x[:-1])<1e-12 or np.std(y[:-1])<1e-12:return unavailable('degenerate_data','Constant pair history cannot establish cointegration')
        beta,intercept=np.polyfit(x[:-1],y[:-1],1)
        residual=y[:-1]-(intercept+beta*x[:-1]);std=float(np.std(residual,ddof=1))
        if std<1e-10:return unavailable('degenerate_data','Near-identical pair history cannot establish a reliable residual scale')
        _,p,_=coint(y[:-1],x[:-1],trend='c',maxlag=5,autolag='aic')
        if not isfinite(float(p)):return unavailable('invalid_test','Cointegration test did not produce a finite p-value')
        zscore=float((y[-1]-intercept-beta*x[-1]-np.mean(residual))/std)
        f={'cointegration_p':float(p),'residual_z':zscore,'hedge_coefficient':float(beta)}
        if p>=.05:return Evaluation(False,'Rolling Engle–Granger test does not reject no cointegration','broken_relationship',features=f)
        if abs(zscore)<2:return Evaluation(True,features=f,diagnostics=['No residual excursion above two standard deviations'])
        return signal(-1 if zscore>0 else 1,f,'Rolling prior-252-day Engle–Granger relationship with current residual excursion; this is a single-symbol research event, not a paired exposure.')
    if strategy_id=='momentum_12_1':
        rows=panel()
        if rows is None or len(rows)<3:return unavailable('missing_inputs','At least three point-in-time universe members and adjusted daily histories are required')
        month=datetime.fromtimestamp(b.time,ZoneInfo('America/New_York')).strftime('%Y-%m')
        if len(data)<2 or datetime.fromtimestamp(data[-2].time,ZoneInfo('America/New_York')).strftime('%Y-%m')==month:
            return Evaluation(True,diagnostics=['Monthly observation occurs only on the first available session of a new month'])
        aligned={s:[x for x in seq if x.time<b.time] for s,seq in rows.items()}
        if b.symbol not in aligned or any(len(seq)<253 for seq in aligned.values()):return unavailable('insufficient_history','253 prior sessions per member required; no short-history substitutions')
        times=[x.time for x in aligned[b.symbol][-253:]]
        if any([x.time for x in seq[-253:]]!=times for seq in aligned.values()):return unavailable('unaligned_data','Universe daily histories must share the same sessions')
        scores={s:seq[-22].close/seq[-253].close-1 for s,seq in aligned.items()}
        score=scores[b.symbol];rank=(sum(v<score for v in scores.values())+.5*sum(v==score for v in scores.values()))/len(scores)
        f={'momentum_12_1':score,'cross_section_rank':rank}
        if .3<rank<.7:return Evaluation(True,features=f)
        return signal(1 if rank>=.7 else -1,f,'Prior-month 12–1 total-return momentum rank in a supplied historical universe. Survivorship depends on membership inputs.')
    if strategy_id=='factor_tilts':
        if not ctx.universe or ctx.universe_available_at is None or ctx.universe_available_at>as_of:return unavailable('missing_universe','Point-in-time membership is required')
        required=('book_to_market','market_cap','profitability','momentum_12_1','realized_volatility')
        snapshots={}
        for o in known:
            if all(k in o.values for k in required) and as_of-o.observed_at<=180*86400:snapshots[o.symbol]=o
        if b.symbol not in ctx.universe:return unavailable('missing_symbol','Target symbol is not in the supplied universe')
        if len(ctx.universe)<3 or any(s not in snapshots for s in ctx.universe):return unavailable('missing_fundamentals','Dated book-to-market, capitalization, profitability, momentum and volatility needed for every member')
        ranks=[];features={}
        for key in required:
            values=[snapshots[s].values[key] for s in ctx.universe];v=snapshots[b.symbol].values[key] if b.symbol in snapshots else None
            if v is None:return unavailable('missing_symbol','Target symbol is not in the supplied universe')
            rank=(sum(x<v for x in values)+.5*sum(x==v for x in values))/len(values)
            if key in ('market_cap','realized_volatility'):rank=1-rank
            features[key+'_rank']=rank;ranks.append(rank)
        score=sum(ranks)/len(ranks);features['composite_rank']=score
        if .35<score<.65:return Evaluation(True,features=features)
        return signal(1 if score>=.65 else -1,features,'Equal-weight value, size, quality, momentum and low-volatility descriptor ranks; a factor-tilt variant, not a replication of published Fama–French factor returns.')
    if strategy_id=='earnings_drift':
        events=[o for o in known if o.symbol==b.symbol and 'standardized_surprise' in o.values and 0<=as_of-o.available_at<=5*86400]
        if not events:return unavailable('missing_earnings','A timestamped standardized earnings surprise from the past five calendar days is required')
        o=events[-1]
        # Emit once on the first finalized daily bar available after the announcement.
        if len(data)>1 and data[-2].available_at>=o.available_at:return Evaluation(True,diagnostics=['Announcement already observed on an earlier bar'])
        surprise=o.values['standardized_surprise']
        if abs(surprise)<1:return Evaluation(True,features={'standardized_surprise':surprise})
        return signal(1 if surprise>0 else -1,{'standardized_surprise':surprise},'First finalized daily observation after a published standardized earnings surprise; five-day freshness limit.')
    if strategy_id=='volatility_gate':
        term=[o for o in known if all(k in o.values for k in ('vix_spot','vix_3m')) and as_of-o.observed_at<=86400]
        iv=[o for o in known if o.symbol==b.symbol and 'iv' in o.values]
        unique={datetime.fromtimestamp(o.observed_at,ZoneInfo('America/New_York')).date():o for o in iv};iv=[unique[t] for t in sorted(unique)][-252:]
        if not term or len(iv)<252 or as_of-iv[-1].observed_at>86400:return unavailable('missing_volatility','Fresh VIX term structure and 252 unique daily IV observations are required')
        values=[o.values['iv'] for o in iv]
        if min(values)<=0 or max(values)==min(values) or term[-1].values['vix_3m']<=0:return unavailable('degenerate_data','Positive varying IV and positive VIX term values are required')
        rank=(values[-1]-min(values))/(max(values)-min(values));ratio=term[-1].values['vix_spot']/term[-1].values['vix_3m']
        enabled=ratio<1 and rank<.8
        return Evaluation(enabled,None if enabled else 'Stress regime: backwardation or IV rank at least 80%',None if enabled else 'regime_blocked',features={'iv_rank':rank,'vix_term_ratio':ratio},diagnostics=['Gate only; does not independently infer direction'])
    if not ctx.calendar or ctx.calendar_available_at is None or ctx.calendar_available_at>as_of:
        return unavailable('missing_calendar','Versioned exchange-session calendar with known availability is required')
    if len(data)<253:return unavailable('insufficient_history','At least 253 finalized daily observations required')
    cohorts=seasonal_cohorts(data,ctx)
    if not cohorts.enabled:return cohorts
    # Pre-register priority rather than selecting the most favorable historical cohort.
    for name in ('fomc_pre','fomc_post','turn_of_month','weekday'):
        if not cohorts.features.get(name+'_active',0):continue
        count=cohorts.features[name+'_n'];mean=cohorts.features[name+'_mean'];se=cohorts.features[name+'_se']
        if count>=30 and abs(mean)>2*se:
            result=signal(1 if mean>0 else -1,cohorts.features,
                f'Prior matured next-session {name} cohort exceeds two standard errors; exploratory association, not corrected for multiple trials.')
            result.diagnostics=cohorts.diagnostics
            return result
    return cohorts


def seasonal_cohorts(data: list[Bar],ctx: Context) -> Evaluation:
    """Next-session returns conditioned on information at the preceding close.

    FOMC observations store a scheduled `fomc_time` in values and the release date
    in observed_at/available_at. Future meetings may be known before they occur.
    """
    last=data[-1];local=lambda t:datetime.fromtimestamp(t,ZoneInfo('America/New_York')).date()
    days=sorted(set(local(t) for t in ctx.calendar));index={d:i for i,d in enumerate(days)}
    months={}
    for day in days:months.setdefault((day.year,day.month),[]).append(day)
    if local(last.time) not in index:return unavailable('invalid_calendar','Current observation absent from supplied session calendar')
    if days[-1].strftime('%Y-%m')<=local(last.time).strftime('%Y-%m'):
        return unavailable('incomplete_calendar','Calendar must extend into next month to identify the true last session')
    def phases(bar: Bar):
        day=local(bar.time)
        if day not in index:return None
        i=index[day];month=months[(day.year,day.month)]
        turn=day in month[:3] or day==month[-1]
        meetings={local(int(o.values['fomc_time'])) for o in known_observations(ctx,bar.available_at,bar.feed) if 'fomc_time' in o.values}
        pre=i+1<len(days) and days[i+1] in meetings
        post=i>0 and days[i-1] in meetings
        return {'weekday':day.weekday(),'turn_of_month':turn,'fomc_pre':pre,'fomc_post':post}
    current=phases(last);samples={name:[] for name in ('weekday','turn_of_month','fomc_pre','fomc_post')}
    # Every target return has matured by the current observation, and its label
    # uses only the event schedule available at the preceding observation.
    for prior,nxt in zip(data[:-1],data[1:]):
        if nxt.available_at>last.available_at:continue
        phase=phases(prior)
        if phase is None or index.get(local(nxt.time))!=index[local(prior.time)]+1:continue
        value=nxt.close/prior.close-1
        if phase['weekday']==current['weekday']:samples['weekday'].append(value)
        for name in ('turn_of_month','fomc_pre','fomc_post'):
            if phase[name]:samples[name].append(value)
    features={};diagnostics=[]
    for name,values in samples.items():
        features[name+'_active']=1. if name=='weekday' else float(current[name])
        features[name+'_n']=float(len(values))
        features[name+'_mean']=float(np.mean(values)) if values else 0.
        features[name+'_se']=float(np.std(values,ddof=1)/np.sqrt(len(values))) if len(values)>1 else 0.
        if len(values)<30:diagnostics.append(f'{name}: unavailable inference; {len(values)} matured observations, minimum 30')
    if not any('fomc_time' in o.values for o in known_observations(ctx,last.available_at,last.feed)):
        diagnostics.append('FOMC cohort unavailable: no point-in-time meeting schedule supplied')
    diagnostics.append('Cohort means are descriptive and unadjusted for multiple testing; zero-valued empty-cohort summaries must not be interpreted as estimates')
    return Evaluation(True,features=features,diagnostics=diagnostics)



def apply_volatility_gate(signals: list[Signal],bars: list[Bar],timeframe: Timeframe,ctx: Context) -> Evaluation:
    """Gate each historical event using only context available at that event.

    Missing context blocks the gated study rather than silently enabling signals.
    """
    accepted=[];blocked=0
    for event in signals:
        past=[b for b in bars if b.time<=event.time and b.available_at<=event.available_at]
        result=evaluate_advanced('volatility_gate',past,timeframe,ctx)
        if result.code not in (None,'regime_blocked'):
            return unavailable(result.code or 'missing_inputs',result.reason or 'Volatility context unavailable')
        if result.enabled:accepted.append(event)
        else:blocked+=1
    return Evaluation(True,signals=accepted,features={'blocked_by_regime':float(blocked)},diagnostics=['Every signal evaluated against its own available timestamp'])
