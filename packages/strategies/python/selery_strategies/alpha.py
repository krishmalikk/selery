"""Original implementations of all 87 nonbinary Alpha101 formulas.

Features, not binary recommendations. Ranks are cross-sectional, never future-time ranks.
Reference: Kakushadze (2015), Appendix A, https://arxiv.org/abs/1601.00991.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from selery_shared.indicators import require_capability
from selery_shared.models import Bar,Feed
from .library import validate_bars

# Pure logical/two-valued formulas are deliberately excluded from the feature library.
BINARY = frozenset([21,27,61,62,64,65,68,74,75,79,81,86,95,99])
IMPLEMENTED = frozenset(range(1,102))-BINARY
PRICE_ONLY = frozenset([1,4,8,9,10,18,19,20,23,24,29,33,34,37,38,46,48,49,51,53,54,56,101])
VWAP_REQUIRED = frozenset([5,11,25,32,36,41,42,47,50,57,58,59,63,66,67,69,70,71,72,73,76,77,78,83,84,87,89,91,93,94,96,97,98])
DOLLAR_REQUIRED = frozenset([7,17,25,28,31,36,39,43,47,52,63,67,69,70,71,72,76,77,78,80,85,87,88,89,90,91,92,93,94,96,97,98,100])
GROUP_REQUIRED = {48:('subindustry',),58:('sector',),59:('industry',),63:('industry',),67:('sector','subindustry'),69:('industry',),70:('industry',),76:('sector',),80:('industry',),82:('sector',),87:('industry',),89:('industry',),90:('subindustry',),91:('industry',),93:('industry',),97:('industry',),100:('subindustry',)}

@dataclass(frozen=True)
class AlphaObservation:
    symbol: str
    time: int
    available_at: int
    feed: Feed
    source: str
    vwap: float | None = None
    dollar_volume: float | None = None
    market_cap: float | None = None
    sector: str | None = None
    industry: str | None = None
    subindustry: str | None = None

@dataclass
class AlphaResult:
    id: str
    enabled: bool
    reason: str | None = None
    values: dict[str,float | None] = field(default_factory=dict)
    available_at: int | None = None
    feed: str | None = None
    version: str = '2'
    observed_at: int | None = None
    requires: list[str] = field(default_factory=list)


def requirements(number: int) -> list[str]:
    values=[]
    if number in VWAP_REQUIRED:values.append('daily_vwap')
    if number in DOLLAR_REQUIRED:values.append('daily_dollar_volume')
    if number==56:values.append('market_cap')
    values.extend(GROUP_REQUIRED.get(number,()))
    return values


def alpha_catalog(feed: Feed) -> list[AlphaResult]:
    return [AlphaResult(f'alpha_{i:03}',i in IMPLEMENTED and (i in PRICE_ONLY or feed==Feed.SIP),
        'Pure binary formula excluded from numeric feature library' if i in BINARY else
        'needs SIP data' if i not in PRICE_ONLY and feed!=Feed.SIP else None,feed=feed.value,requires=requirements(i)) for i in range(1,102)]


def rank(x):return x.rank(axis=1,pct=True,method='average',na_option='keep')
def delay(x,n):return x.shift(int(n))
def delta(x,n):return x-x.shift(int(n))
def ts_sum(x,n):return x.rolling(int(n),min_periods=int(n)).sum()
def mean(x,n):return x.rolling(int(n),min_periods=int(n)).mean()
def std(x,n):return x.rolling(int(n),min_periods=int(n)).std(ddof=0)
def low(x,n):return x.rolling(int(n),min_periods=int(n)).min()
def high(x,n):return x.rolling(int(n),min_periods=int(n)).max()
def corr(x,y,n):return x.rolling(int(n),min_periods=int(n)).corr(y).replace([np.inf,-np.inf],np.nan)
def cov(x,y,n):return x.rolling(int(n),min_periods=int(n)).cov(y)
def ts_rank(x,n):return x.rolling(int(n),min_periods=int(n)).apply(lambda w:pd.Series(w).rank(method='average').iloc[-1],raw=True)
def argmax(x,n):return x.rolling(int(n),min_periods=int(n)).apply(lambda w:float(np.argmax(w)+1),raw=True)
def scale(x):return x.div(x.abs().sum(axis=1).replace(0,np.nan),axis=0)
def div(x,y):return x/y.replace(0,np.nan)
def choose(mask,a,b):return a.where(mask,b)


def decay(x,n):
    n=int(n);weights=np.arange(1,n+1,dtype=float);weights/=weights.sum()
    return x.rolling(n,min_periods=n).apply(lambda row:np.dot(row,weights),raw=True)
def product(x,n):return x.rolling(int(n),min_periods=int(n)).apply(np.prod,raw=True)
def argmin(x,n):return x.rolling(int(n),min_periods=int(n)).apply(lambda row:float(np.argmin(row)+1),raw=True)
def neutral(x,groups):
    result=x.copy()*np.nan
    for time in x.index:
        labels=groups.loc[time];values=x.loc[time]
        for group in labels.dropna().unique():
            members=labels==group
            result.loc[time,members]=values[members]-values[members].mean()
    return result


def compute_formula(number: int,o,h,l,c,v,w=None,dollars=None,cap=None,groups=None):
    r=div(c,delay(c,1))-1;adv=mean(dollars,20) if dollars is not None else v*np.nan;d=delta(c,1)
    av=lambda n:mean(dollars,int(n))
    neu=lambda x,kind:neutral(x,groups[kind])
    if number==1:
        selected=choose(r<0,std(r,20),c).where(r.notna())
        return rank(argmax(np.sign(selected)*selected**2,5))-.5
    if number==2:return -corr(rank(delta(np.log(v.where(v>0)),2)),rank(div(c-o,o)),6)
    if number==3:return -corr(rank(o),rank(v),10)
    if number==4:return -ts_rank(rank(l),9)
    if number==5:return rank(o-mean(w,10))*(-abs(rank(c-w)))
    if number==6:return -corr(o,v,10)
    if number==7:return choose(adv<v,-ts_rank(abs(delta(c,7)),60)*np.sign(delta(c,7)),v*0-1).where(adv.notna())
    if number==8:return -rank(delta(ts_sum(o,5)*ts_sum(r,5),10))
    if number in (9,10):
        n=5 if number==9 else 4
        value=choose((low(d,n)>0)|(high(d,n)<0),d,-d).where(low(d,n).notna())
        return value if number==9 else rank(value)
    if number==11:return (rank(high(w-c,3))+rank(low(w-c,3)))*rank(delta(v,3))
    if number==12:return np.sign(delta(v,1))*(-d)
    if number==13:return -rank(cov(rank(c),rank(v),5))
    if number==14:return -rank(delta(r,3))*corr(o,v,10)
    if number==15:return -ts_sum(rank(corr(rank(h),rank(v),3)),3)
    if number==16:return -rank(cov(rank(h),rank(v),5))
    if number==17:return -rank(ts_rank(c,10))*rank(delta(d,1))*rank(ts_rank(div(v,adv),5))
    if number==18:return -rank(std(abs(c-o),5)+(c-o)+corr(c,o,10))
    if number==19:return -np.sign(c-delay(c,7)+delta(c,7))*(1+rank(1+ts_sum(r,250)))
    if number==20:return -rank(o-delay(h,1))*rank(o-delay(c,1))*rank(o-delay(l,1))
    if number==22:return -delta(corr(h,v,5),5)*rank(std(c,20))
    if number==23:return choose(mean(h,20)<h,-delta(h,2),h*0).where(mean(h,20).notna())
    if number==24:return choose(div(delta(mean(c,100),100),delay(c,100))<=.05,-(c-low(c,100)),-delta(c,3)).where(delay(mean(c,100),100).notna())
    if number==25:return rank(-r*adv*w*(h-c))
    if number==26:return -high(corr(ts_rank(v,5),ts_rank(h,5),5),3)
    if number==28:return scale(corr(adv,l,5)+(h+l)/2-c)
    if number==29:return low(product(rank(rank(scale(np.log(ts_sum(low(rank(rank(-rank(delta(c-1,5)))),2),1))))),1),5)+ts_rank(delay(-r,6),5)
    if number==30:return div((1-rank(np.sign(d)+np.sign(delay(d,1))+np.sign(delay(d,2))))*ts_sum(v,5),ts_sum(v,20))
    if number==31:return rank(rank(rank(decay(-rank(rank(delta(c,10))),10))))+rank(-delta(c,3))+np.sign(scale(corr(adv,l,12)))
    if number==32:return scale(mean(c,7)-c)+20*scale(corr(w,delay(c,5),230))
    if number==33:return rank(o/c-1)
    if number==34:return rank(1-rank(div(std(r,2),std(r,5)))+1-rank(d))
    if number==35:return ts_rank(v,32)*(1-ts_rank(c+h-l,16))*(1-ts_rank(r,32))
    if number==36:return 2.21*rank(corr(c-o,delay(v,1),15))+.7*rank(o-c)+.73*rank(ts_rank(delay(-r,6),5))+rank(abs(corr(w,adv,6)))+.6*rank((mean(c,200)-o)*(c-o))
    if number==37:return rank(corr(delay(o-c,1),c,200))+rank(o-c)
    if number==38:return -rank(ts_rank(c,10))*rank(c/o)
    if number==39:return -rank(delta(c,7)*(1-rank(decay(div(v,adv),9))))*(1+rank(ts_sum(r,250)))
    if number==40:return -rank(std(h,10))*corr(h,v,10)
    if number==41:return np.sqrt(h*l)-w
    if number==42:return div(rank(w-c),rank(w+c))
    if number==43:return ts_rank(div(v,adv),20)*ts_rank(-delta(c,7),8)
    if number==44:return -corr(h,rank(v),5)
    if number==45:return -rank(mean(delay(c,5),20))*corr(c,v,2)*rank(corr(ts_sum(c,5),ts_sum(c,20),2))
    if number==47:return div(rank(1/c)*v,adv)*div(h*rank(h-c),mean(h,5))-rank(delta(w,5))
    if number==48:return div(neu(div(corr(d,delta(delay(c,1),1),250)*d,c),'subindustry'),ts_sum((d/delay(c,1))**2,250))
    if number==50:return -high(rank(corr(rank(v),rank(w),5)),5)
    if number in (46,49,51):
        slope=(delay(c,20)-delay(c,10))/10-(delay(c,10)-c)/10
        value=choose(slope<(-.1 if number==49 else -.05),c*0+1,-d) if number!=46 else choose(slope>.25,c*0-1,choose(slope<0,c*0+1,-d))
        return value.where(slope.notna())
    if number==52:return (-low(l,5)+delay(low(l,5),5))*rank((ts_sum(r,240)-ts_sum(r,20))/220)*ts_rank(v,5)
    if number==53:return -delta(div((c-l)-(h-c),c-l),9)
    if number==54:return -div((l-c)*o**5,(l-h)*c**5)
    if number==55:return -corr(rank(div(c-low(l,12),high(h,12)-low(l,12))),rank(v),6)
    if number==56:return -rank(div(ts_sum(r,10),ts_sum(ts_sum(r,2),3)))*rank(r*cap)
    if number==57:return -div(c-w,decay(rank(argmax(c,30)),2))
    if number==58:return -ts_rank(decay(corr(neu(w,'sector'),v,3.92795),7.89291),5.50322)
    if number==59:return -ts_rank(decay(corr(neu(w,'industry'),v,4.25197),16.2289),8.19648)
    if number==60:return -(2*scale(rank(div((c-l)-(h-c),h-l)*v))-scale(rank(argmax(c,10))))
    if number==63:return -(rank(decay(delta(neu(c,'industry'),2.25164),8.22237))-rank(decay(corr(w*.318108+o*.681892,ts_sum(av(180),37.2467),13.557),12.2883)))
    if number==66:return -(rank(decay(delta(w,3.51013),7.23052))+ts_rank(decay(div(l-w,o-(h+l)/2),11.4157),6.72611))
    if number==67:return -(rank(h-low(h,2.14593))**rank(corr(neu(w,'sector'),neu(adv,'subindustry'),6.02936)))
    if number==69:return -(rank(high(delta(neu(w,'industry'),2.72412),4.79344))**ts_rank(corr(c*.490655+w*.509345,adv,4.92416),9.0615))
    if number==70:return -(rank(delta(w,1.29456))**ts_rank(corr(neu(c,'industry'),av(50),17.8256),17.9171))
    if number==71:return np.maximum(ts_rank(decay(corr(ts_rank(c,3.43976),ts_rank(av(180),12.0647),18.0175),4.20501),15.6948),ts_rank(decay(rank(l+o-2*w)**2,16.4662),4.4388))
    if number==72:return div(rank(decay(corr((h+l)/2,av(40),8.93345),10.1519)),rank(decay(corr(ts_rank(w,3.72469),ts_rank(v,18.5188),6.86671),2.95011)))
    if number==73:return -np.maximum(rank(decay(delta(w,4.72775),2.91864)),ts_rank(decay(-div(delta(o*.147155+l*.852845,2.03608),o*.147155+l*.852845),3.33829),16.7411))
    if number==76:return -np.maximum(rank(decay(delta(w,1.24383),11.8259)),ts_rank(decay(ts_rank(corr(neu(l,'sector'),av(81),8.14941),19.569),17.1543),19.383))
    if number==77:return np.minimum(rank(decay((h+l)/2-w,20.0451)),rank(decay(corr((h+l)/2,av(40),3.1614),5.64125)))
    if number==78:return rank(corr(ts_sum(l*.352233+w*.647767,19.7428),ts_sum(av(40),19.7428),6.83313))**rank(corr(rank(w),rank(v),5.77492))
    if number==80:return -(rank(np.sign(delta(neu(o*.868128+h*.131872,'industry'),4.04545)))**ts_rank(corr(h,av(10),5.11456),5.53756))
    if number==82:return -np.minimum(rank(decay(delta(o,1.46063),14.8717)),ts_rank(decay(corr(neu(v,'sector'),o,17.4842),6.92131),13.4283))
    if number==83:return div(rank(delay(div(h-l,mean(c,5)),2))*rank(rank(v)),div(div(h-l,mean(c,5)),w-c))
    if number==84:return ts_rank(w-high(w,15.3217),20.7127)**delta(c,4.96796)
    if number==85:return rank(corr(h*.876703+c*.123297,av(30),9.61331))**rank(corr(ts_rank((h+l)/2,3.70596),ts_rank(v,10.1595),7.11408))
    if number==87:return -np.maximum(rank(decay(delta(c*.369701+w*.630299,1.91233),2.65461)),ts_rank(decay(abs(corr(neu(av(81),'industry'),c,13.4132)),4.89768),14.4535))
    if number==88:return np.minimum(rank(decay(rank(o)+rank(l)-rank(h)-rank(c),8.06882)),ts_rank(decay(corr(ts_rank(c,8.44728),ts_rank(av(60),20.6966),8.01266),6.65053),2.61957))
    if number==89:return ts_rank(decay(corr(l,av(10),6.94279),5.51607),3.79744)-ts_rank(decay(delta(neu(w,'industry'),3.48158),10.1466),15.3012)
    if number==90:return -(rank(c-high(c,4.66719))**ts_rank(corr(neu(av(40),'subindustry'),l,5.38375),3.21856))
    if number==91:return -(ts_rank(decay(decay(corr(neu(c,'industry'),v,9.74928),16.398),3.83219),4.8667)-rank(decay(corr(w,av(30),4.01303),2.6809)))
    if number==92:return np.minimum(ts_rank(decay(((h+l)/2+c<l+o).astype(float),14.7221),18.8683),ts_rank(decay(corr(rank(l),rank(av(30)),7.58555),6.94024),6.80584))
    if number==93:return div(ts_rank(decay(corr(neu(w,'industry'),av(81),17.4193),19.848),7.54455),rank(decay(delta(c*.524434+w*.475566,2.77377),16.2664)))
    if number==94:return -(rank(w-low(w,11.5783))**ts_rank(corr(ts_rank(w,19.6462),ts_rank(av(60),4.02992),18.0926),2.70756))
    if number==96:return -np.maximum(ts_rank(decay(corr(rank(w),rank(v),3.83878),4.16783),8.38151),ts_rank(decay(argmax(corr(ts_rank(c,7.45404),ts_rank(av(60),4.13242),3.65459),12.6556),14.0365),13.4143))
    if number==97:return -(rank(decay(delta(neu(l*.721001+w*.278999,'industry'),3.3705),20.4523))-ts_rank(decay(ts_rank(corr(ts_rank(l,7.87871),ts_rank(av(60),17.255),4.97547),18.5925),15.7152),6.71659))
    if number==98:return rank(decay(corr(w,ts_sum(av(5),26.4719),4.58418),7.18088))-rank(decay(ts_rank(argmin(corr(rank(o),rank(av(15)),20.8187),8.62571),6.95668),8.07206))
    if number==100:return -(1.5*scale(neu(neu(rank(div((c-l)-(h-c),h-l)*v),'subindustry'),'subindustry'))-scale(neu(corr(c,rank(adv),5)-rank(argmin(c,30)),'subindustry')))*div(v,adv)
    if number==101:return (c-o)/(h-l+.001)
    raise ValueError('Formula not implemented')


def alpha_features(panel: dict[str,list[Bar]],feed: Feed,as_of: int,*,adjusted: bool=False,
                   numbers: list[int] | None=None, observations: list[AlphaObservation] | None=None) -> list[AlphaResult]:
    requested=numbers or sorted(IMPLEMENTED)
    if any(n<1 or n>101 for n in requested):raise ValueError('Alpha number must be between 1 and 101')
    metadata={i+1:x for i,x in enumerate(alpha_catalog(feed))}
    result=[]
    if not adjusted:
        return [AlphaResult(f'alpha_{i:03}',False,'Explicit adjusted daily dataset declaration required',feed=feed.value) for i in requested]
    eligible={s:[b for b in validate_bars(seq,feed) if b.available_at<=as_of] for s,seq in panel.items()}
    if len(eligible)<2 or any(not seq for seq in eligible.values()):
        return [AlphaResult(f'alpha_{i:03}',False,'At least two aligned universe members are required',feed=feed.value) for i in requested]
    reference=[b.time for b in next(iter(eligible.values()))]
    if any([b.time for b in seq]!=reference for seq in eligible.values()):raise ValueError('Alpha panel must have aligned timestamps; no implicit forward fills')
    frames=[pd.DataFrame({s:[getattr(b,name) for b in seq] for s,seq in eligible.items()},index=reference,dtype=float) for name in ('open','high','low','close','volume')]
    supplied=observations or []
    lookup={}
    for item in supplied:
        if not item.source or item.available_at<item.time:raise ValueError('Alpha context requires source and causal availability')
        if item.feed!=feed:raise ValueError('Alpha context feed mismatch')
        if any(value is not None and value<=0 for value in (item.vwap,item.market_cap)):raise ValueError('VWAP and market cap must be positive when supplied')
        if any(value is not None and (not np.isfinite(value) or value<0) for value in (item.vwap,item.dollar_volume,item.market_cap)):raise ValueError('Alpha context values must be finite and nonnegative')
        if item.available_at<=as_of:
            key=(item.symbol,item.time)
            if key in lookup and lookup[key]!=item:raise ValueError('Conflicting alpha context observations')
            lookup[key]=item
    numeric={}
    for name in ('vwap','dollar_volume','market_cap'):
        numeric[name]=pd.DataFrame({symbol:[getattr(lookup[(symbol,b.time)],name) if (symbol,b.time) in lookup and lookup[(symbol,b.time)].available_at<=b.available_at else np.nan for b in seq] for symbol,seq in eligible.items()},index=reference,dtype=float)
    classifications={}
    for name in ('sector','industry','subindustry'):
        classifications[name]=pd.DataFrame({symbol:[getattr(lookup[(symbol,b.time)],name) if (symbol,b.time) in lookup and lookup[(symbol,b.time)].available_at<=b.available_at else None for b in seq] for symbol,seq in eligible.items()},index=reference)
    for frame in numeric.values():frame.loc[frame.isna().any(axis=1),:]=np.nan
    for frame in classifications.values():frame.loc[frame.isna().any(axis=1),:]=None
    for number in requested:
        info=metadata[number]
        if not info.enabled:result.append(info);continue
        if number not in PRICE_ONLY:require_capability('volume_alpha',feed)
        missing=[]
        for required in info.requires:
            key={'daily_vwap':'vwap','daily_dollar_volume':'dollar_volume'}.get(required,required)
            frame=numeric.get(key) if key in numeric else classifications[key]
            if frame.iloc[-1].isna().any():missing.append(required)
        if missing:
            info.enabled=False;info.reason='Missing point-in-time inputs: '+', '.join(missing);result.append(info);continue
        with np.errstate(divide='ignore',invalid='ignore',over='ignore'):
            computed=compute_formula(number,*frames,numeric['vwap'],numeric['dollar_volume'],numeric['market_cap'],classifications).replace([np.inf,-np.inf],np.nan)
        last=computed.iloc[-1]
        values={s:None if pd.isna(v) else float(v) for s,v in last.items()}
        info.values=values;info.observed_at=reference[-1];info.available_at=max(seq[-1].available_at for seq in eligible.values())
        if all(v is None for v in values.values()):info.reason='Insufficient warm-up or degenerate inputs; no imputation applied'
        result.append(info)
    return result


def information_coefficient_decay(snapshots: list[AlphaResult],panel: dict[str,list[Bar]],as_of: int,
                                  horizons: tuple[int,...]=(1,5,20)) -> dict:
    """Cross-sectional Spearman IC using only fully matured future labels.

    Snapshots are immutable point-in-time feature values, never recomputed from
    a later restated universe. Returns are descriptive price labels, not actions.
    """
    if any(h<1 for h in horizons):raise ValueError('IC horizons must be positive')
    if len({s.id for s in snapshots})>1:raise ValueError('IC decay compares one formula at a time')
    if len({s.version for s in snapshots})>1:raise ValueError('IC decay cannot mix formula versions')
    data={s:validate_bars(rows) for s,rows in panel.items()}
    results={h:[] for h in horizons};missing={h:0 for h in horizons};counts={h:0 for h in horizons}
    seen=set()
    for snapshot in snapshots:
        if not snapshot.enabled or snapshot.available_at is None or snapshot.observed_at is None:continue
        key=(snapshot.id,snapshot.version,snapshot.observed_at)
        if key in seen:raise ValueError('Duplicate IC snapshot would overweight a cohort')
        seen.add(key)
        if snapshot.available_at>as_of:continue
        if snapshot.available_at<snapshot.observed_at:raise ValueError('Feature cannot predate observation')
        for horizon in horizons:
            values=[];targets=[]
            for symbol,value in snapshot.values.items():
                if value is None:continue
                if not np.isfinite(value):raise ValueError('IC features must be finite')
                rows=data.get(symbol,[])
                if any(b.feed.value!=snapshot.feed for b in rows):raise ValueError('IC dataset feed mismatch')
                reference=next((b for b in rows if b.time==snapshot.observed_at and b.available_at<=snapshot.available_at),None)
                future=[b for b in rows if b.time>=snapshot.available_at and b.time>snapshot.observed_at and b.available_at<=as_of]
                if reference is None or len(future)<horizon:missing[horizon]+=1;continue
                values.append(value);targets.append(future[horizon-1].close/reference.close-1)
            if len(values)<3:continue
            x=pd.Series(values).rank(method='average').to_numpy();y=pd.Series(targets).rank(method='average').to_numpy()
            if np.std(x)==0 or np.std(y)==0:continue
            results[horizon].append(float(np.corrcoef(x,y)[0,1]));counts[horizon]+=len(values)
    return {'formula':snapshots[0].id if snapshots else None,'as_of':as_of,
        'horizons':[{'bars':h,'mean_rank_ic':float(np.mean(results[h])) if results[h] else None,
            'cohorts':len(results[h]),'matured_labels':counts[h],'unavailable_labels':missing[h],
            'reason':None if results[h] else 'At least three finite distinct member ranks and fully matured labels per cohort are required'} for h in horizons],
        'limitations':['Descriptive cross-sectional rank association; overlapping labels are dependent, so no independence-based significance is claimed.',
            'Caller supplies immutable historical membership and adjusted daily prices; unobserved sessions are not imputed.']}
