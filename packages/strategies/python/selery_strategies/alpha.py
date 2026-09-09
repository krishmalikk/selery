"""Original implementations of an explicitly reported subset of Alpha101 formulas.

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

IMPLEMENTED = frozenset([1,2,3,4,6,7,8,9,10,12,13,14,15,16,17,18,19,20,21,22,23,24,26,28,30,33,34,35,37,38,40,43,44,45,46,49,51,53,54,55,60,101])
PRICE_ONLY = frozenset([1,4,8,9,10,18,19,20,23,24,33,34,37,38,46,49,51,53,54,101])

@dataclass
class AlphaResult:
    id: str
    enabled: bool
    reason: str | None = None
    values: dict[str,float | None] = field(default_factory=dict)
    available_at: int | None = None
    feed: str | None = None
    version: str = '1'


def alpha_catalog(feed: Feed) -> list[AlphaResult]:
    return [AlphaResult(f'alpha_{i:03}',i in IMPLEMENTED and (i in PRICE_ONLY or feed==Feed.SIP),
        'Formula not implemented; coverage is explicitly partial' if i not in IMPLEMENTED else
        'needs SIP data' if i not in PRICE_ONLY and feed!=Feed.SIP else None,feed=feed.value) for i in range(1,102)]


def rank(x):return x.rank(axis=1,pct=True,method='average',na_option='keep')
def delay(x,n):return x.shift(n)
def delta(x,n):return x-x.shift(n)
def ts_sum(x,n):return x.rolling(n,min_periods=n).sum()
def mean(x,n):return x.rolling(n,min_periods=n).mean()
def std(x,n):return x.rolling(n,min_periods=n).std(ddof=0)
def low(x,n):return x.rolling(n,min_periods=n).min()
def high(x,n):return x.rolling(n,min_periods=n).max()
def corr(x,y,n):return x.rolling(n,min_periods=n).corr(y).replace([np.inf,-np.inf],np.nan)
def cov(x,y,n):return x.rolling(n,min_periods=n).cov(y)
def ts_rank(x,n):return x.rolling(n,min_periods=n).apply(lambda w:pd.Series(w).rank(method='average').iloc[-1],raw=True)
def argmax(x,n):return x.rolling(n,min_periods=n).apply(lambda w:float(np.argmax(w)+1),raw=True)
def scale(x):return x.div(x.abs().sum(axis=1).replace(0,np.nan),axis=0)
def div(x,y):return x/y.replace(0,np.nan)
def choose(mask,a,b):return a.where(mask,b)


def compute_formula(number: int,o,h,l,c,v):
    r=div(c,delay(c,1))-1;adv=mean(v,20);d=delta(c,1)
    if number==1:
        selected=choose(r<0,std(r,20),c).where(r.notna())
        return rank(argmax(np.sign(selected)*selected**2,5))-.5
    if number==2:return -corr(rank(delta(np.log(v.where(v>0)),2)),rank(div(c-o,o)),6)
    if number==3:return -corr(rank(o),rank(v),10)
    if number==4:return -ts_rank(rank(l),9)
    if number==6:return -corr(o,v,10)
    if number==7:return choose(adv<v,-ts_rank(abs(delta(c,7)),60)*np.sign(delta(c,7)),v*0-1).where(adv.notna())
    if number==8:return -rank(delta(ts_sum(o,5)*ts_sum(r,5),10))
    if number in (9,10):
        n=5 if number==9 else 4
        value=choose((low(d,n)>0)|(high(d,n)<0),d,-d).where(low(d,n).notna())
        return value if number==9 else rank(value)
    if number==12:return np.sign(delta(v,1))*(-d)
    if number==13:return -rank(cov(rank(c),rank(v),5))
    if number==14:return -rank(delta(r,3))*corr(o,v,10)
    if number==15:return -ts_sum(rank(corr(rank(h),rank(v),3)),3)
    if number==16:return -rank(cov(rank(h),rank(v),5))
    if number==17:return -rank(ts_rank(c,10))*rank(delta(d,1))*rank(ts_rank(div(v,adv),5))
    if number==18:return -rank(std(abs(c-o),5)+(c-o)+corr(c,o,10))
    if number==19:return -np.sign(c-delay(c,7)+delta(c,7))*(1+rank(1+ts_sum(r,250)))
    if number==20:return -rank(o-delay(h,1))*rank(o-delay(c,1))*rank(o-delay(l,1))
    if number==21:
        mid=mean(c,8);s=std(c,8);short=mean(c,2)
        return choose(mid+s<short,c*0-1,choose(short<mid-s,c*0+1,choose(div(v,adv)>=1,c*0+1,c*0-1))).where(adv.notna())
    if number==22:return -delta(corr(h,v,5),5)*rank(std(c,20))
    if number==23:return choose(mean(h,20)<h,-delta(h,2),h*0).where(mean(h,20).notna())
    if number==24:return choose(div(delta(mean(c,100),100),delay(c,100))<=.05,-(c-low(c,100)),-delta(c,3)).where(delay(mean(c,100),100).notna())
    if number==26:return -high(corr(ts_rank(v,5),ts_rank(h,5),5),3)
    if number==28:return scale(corr(adv,l,5)+(h+l)/2-c)
    if number==30:return div((1-rank(np.sign(d)+np.sign(delay(d,1))+np.sign(delay(d,2))))*ts_sum(v,5),ts_sum(v,20))
    if number==33:return rank(o/c-1)
    if number==34:return rank(1-rank(div(std(r,2),std(r,5)))+1-rank(d))
    if number==35:return ts_rank(v,32)*(1-ts_rank(c+h-l,16))*(1-ts_rank(r,32))
    if number==37:return rank(corr(delay(o-c,1),c,200))+rank(o-c)
    if number==38:return -rank(ts_rank(c,10))*rank(c/o)
    if number==40:return -rank(std(h,10))*corr(h,v,10)
    if number==43:return ts_rank(div(v,adv),20)*ts_rank(-delta(c,7),8)
    if number==44:return -corr(h,rank(v),5)
    if number==45:return -rank(mean(delay(c,5),20))*corr(c,v,2)*rank(corr(ts_sum(c,5),ts_sum(c,20),2))
    if number in (46,49,51):
        slope=(delay(c,20)-delay(c,10))/10-(delay(c,10)-c)/10
        value=choose(slope<(-.1 if number==49 else -.05),c*0+1,-d) if number!=46 else choose(slope>.25,c*0-1,choose(slope<0,c*0+1,-d))
        return value.where(slope.notna())
    if number==53:return -delta(div((c-l)-(h-c),c-l),9)
    if number==54:return -div((l-c)*o**5,(l-h)*c**5)
    if number==55:return -corr(rank(div(c-low(l,12),high(h,12)-low(l,12))),rank(v),6)
    if number==60:return -(2*scale(rank(div((c-l)-(h-c),h-l)*v))-scale(rank(argmax(c,10))))
    if number==101:return (c-o)/(h-l+.001)
    raise ValueError('Formula not implemented')


def alpha_features(panel: dict[str,list[Bar]],feed: Feed,as_of: int,*,adjusted: bool=False,
                   numbers: list[int] | None=None) -> list[AlphaResult]:
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
    for number in requested:
        info=metadata[number]
        if not info.enabled:result.append(info);continue
        if number not in PRICE_ONLY:require_capability('volume_alpha',feed)
        computed=compute_formula(number,*frames).replace([np.inf,-np.inf],np.nan)
        last=computed.iloc[-1]
        values={s:None if pd.isna(v) else float(v) for s,v in last.items()}
        info.values=values;info.available_at=max(seq[-1].available_at for seq in eligible.values())
        if all(v is None for v in values.values()):info.reason='Insufficient warm-up or degenerate inputs; no imputation applied'
        result.append(info)
    return result
