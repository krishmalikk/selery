"""Causal chart math, computed exclusively by the Python API."""
from math import sqrt
from .models import Bar, Capability, Feed, IndicatorPoint

VOLUME_FEATURES = ('vwap', 'anchored_vwap', 'obv', 'volume_profile', 'unusual_volume', 'volume_confirmation', 'volume_alpha')

def require_capability(feature: str, feed: Feed):
    if feature in VOLUME_FEATURES and feed != Feed.SIP:
        raise ValueError('needs SIP data')

def capabilities(feed: Feed) -> list[Capability]:
    return [Capability(id=name, label=name.replace('_',' ').upper(), enabled=feed==Feed.SIP,
                       reason=None if feed==Feed.SIP else 'needs SIP data') for name in VOLUME_FEATURES]

def ema(values: list[float], period: int) -> list[float | None]:
    if period < 1: raise ValueError('period must be positive')
    result: list[float | None] = [None] * len(values)
    if len(values) < period: return result
    current = sum(values[:period]) / period
    result[period-1] = current
    alpha=2/(period+1)
    for i in range(period,len(values)):
        current=values[i]*alpha+current*(1-alpha)
        result[i]=current
    return result

def sma(values: list[float], period: int) -> list[float | None]:
    if period < 1: raise ValueError('period must be positive')
    return [None if i+1<period else sum(values[i+1-period:i+1])/period for i in range(len(values))]

def rsi(values: list[float], period: int=14) -> list[float | None]:
    result: list[float | None] = [None]*len(values)
    if len(values)<=period: return result
    changes=[b-a for a,b in zip(values,values[1:])]
    gain=sum(max(c,0) for c in changes[:period])/period
    loss=sum(max(-c,0) for c in changes[:period])/period
    def value(): return 50.0 if gain==loss==0 else 100.0 if loss==0 else 100-100/(1+gain/loss)
    result[period]=value()
    for i in range(period+1,len(values)):
        gain=(gain*(period-1)+max(changes[i-1],0))/period
        loss=(loss*(period-1)+max(-changes[i-1],0))/period
        result[i]=value()
    return result

def atr(bars: list[Bar], period: int=14) -> list[float | None]:
    tr=[b.high-b.low if i==0 else max(b.high-b.low,abs(b.high-bars[i-1].close),abs(b.low-bars[i-1].close)) for i,b in enumerate(bars)]
    out: list[float | None]=[None]*len(bars)
    if len(bars)<period:return out
    value=sum(tr[:period])/period
    out[period-1]=value
    for i in range(period,len(bars)):
        value=(value*(period-1)+tr[i])/period
        out[i]=value
    return out

def chart_indicators(bars: list[Bar], feed: Feed) -> dict[str,list[IndicatorPoint]]:
    closes=[b.close for b in bars]
    arrays={'ema9':ema(closes,9),'ema21':ema(closes,21),'sma50':sma(closes,50),'rsi14':rsi(closes),'atr14':atr(bars)}
    mid=sma(closes,20)
    std=[None if i<19 else sqrt(sum((x-mid[i])**2 for x in closes[i-19:i+1])/20) for i in range(len(bars))]
    arrays['bb_upper']=[None if s is None else mid[i]+2*s for i,s in enumerate(std)]
    arrays['bb_lower']=[None if s is None else mid[i]-2*s for i,s in enumerate(std)]
    fast,slow=ema(closes,12),ema(closes,26)
    arrays['macd']=[None if a is None or b is None else a-b for a,b in zip(fast,slow)]
    if feed==Feed.SIP:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        day=None; weighted=volume=obv=0.0
        vwap=[]; obvs=[]
        for i,bar in enumerate(bars):
            current=datetime.fromtimestamp(bar.time,ZoneInfo('America/New_York')).date()
            if current!=day: day=current; weighted=volume=0.0
            weighted+=(bar.high+bar.low+bar.close)/3*bar.volume;volume+=bar.volume
            vwap.append(weighted/volume if volume else None)
            if i: obv+=bar.volume*(1 if bar.close>bars[i-1].close else -1 if bar.close<bars[i-1].close else 0)
            obvs.append(obv)
        arrays['vwap']=vwap;arrays['obv']=obvs
    if len(bars)>=80:
        import pandas as pd
        import pandas_ta_classic as ta
        high=pd.Series([b.high for b in bars]);low=pd.Series([b.low for b in bars]);close=pd.Series(closes)
        def add(key,series):
            if series is not None:arrays[key]=[None if pd.isna(v) else float(v) for v in series]
        adx=ta.adx(high,low,close,talib=False)
        if adx is not None:add('adx14',adx.iloc[:,0])
        stochastic=ta.stoch(high,low,close,talib=False)
        if stochastic is not None:
            add('stochastic_k',stochastic.iloc[:,0]);add('stochastic_d',stochastic.iloc[:,1])
        sar=ta.psar(high,low,close,talib=False)
        if sar is not None:add('psar',sar.iloc[:,0].combine_first(sar.iloc[:,1]))
        trend=ta.supertrend(high,low,close)
        if trend is not None:add('supertrend',trend.iloc[:,0])
        cloud,_=ta.ichimoku(high,low,close,include_chikou=False,lookahead=False)
        if cloud is not None:
            for col in cloud.columns:add('ichimoku_'+col.lower(),cloud[col])
    result={name:[IndicatorPoint(time=b.time,value=v) for b,v in zip(bars,values)] for name,values in arrays.items()}
    from .structure import structure_levels
    result.update(structure_levels(bars))
    return result
