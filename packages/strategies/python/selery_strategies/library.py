"""Independent, causal price-only research strategies. No execution semantics.

Method references and intentionally limited variants: docs/tracks/F.md.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from math import sqrt
from zoneinfo import ZoneInfo

from selery_shared.indicators import atr, ema, require_capability, rsi, sma
from selery_shared.models import Bar, Feed, Signal, Strategy, StrategyInfo, Timeframe


def validate_bars(bars: list[Bar], feed: Feed | None = None) -> list[Bar]:
    result = [b for b in bars if b.finalized]
    for i, b in enumerate(result):
        if b.close <= 0 or b.low <= 0 or not b.low <= min(b.open, b.close) <= max(b.open, b.close) <= b.high:
            raise ValueError('Invalid OHLC prices')
        if b.available_at < b.time:
            raise ValueError('Bar cannot be available before its observation')
        if feed is not None and b.feed != feed:
            raise ValueError('Dataset feed does not match strategy feed')
        if i and (b.symbol != result[0].symbol or b.feed != result[0].feed or b.time <= result[i-1].time or b.available_at < result[i-1].available_at):
            raise ValueError('Require one symbol/feed, unique chronological bars and causal availability')
    return result


def make_signal(strategy: str, b: Bar, timeframe: Timeframe, direction: int, volatility: float,
                explanation: str, features: dict[str, float] | None = None) -> Signal:
    distance = min(max(volatility * 1.5, b.close * .002), b.close * .3)
    return Signal(id=sha256(f'{b.symbol}:{timeframe}:{b.feed}:{strategy}:1:{b.time}'.encode()).hexdigest()[:24],
        symbol=b.symbol, strategy=strategy, timeframe=timeframe, time=b.time, available_at=b.available_at,
        direction='bullish' if direction > 0 else 'bearish', reference_price=b.close,
        stop=b.close-direction*distance, target=b.close+direction*distance*2, feed=b.feed,
        features=features or {}, explanation=explanation + ' Analytical ATR reference thresholds; confidence unavailable.')


def adx(bars: list[Bar], period: int = 14) -> list[float | None]:
    """Wilder directional movement and average directional index, seeded causally."""
    out: list[float | None] = [None] * len(bars)
    if len(bars) < 2*period: return out
    trs, plus, minus = [], [], []
    for prev, cur in zip(bars, bars[1:]):
        up, down = cur.high-prev.high, prev.low-cur.low
        trs.append(max(cur.high-cur.low, abs(cur.high-prev.close), abs(cur.low-prev.close)))
        plus.append(up if up > down and up > 0 else 0.)
        minus.append(down if down > up and down > 0 else 0.)
    tr, pos, neg = sum(trs[:period]), sum(plus[:period]), sum(minus[:period])
    dx = []
    smooth = None
    for j in range(period-1, len(trs)):
        if j >= period:
            tr = tr-tr/period+trs[j]; pos = pos-pos/period+plus[j]; neg = neg-neg/period+minus[j]
        value = 100*abs(pos-neg)/(pos+neg) if pos+neg else 0.
        dx.append(value)
        if len(dx) == period: smooth = sum(dx)/period
        elif len(dx) > period: smooth = (smooth*(period-1)+value)/period
        if smooth is not None: out[j+1] = smooth
    return out


def psar(bars: list[Bar]) -> list[float | None]:
    out: list[float | None] = [None]*len(bars)
    if len(bars) < 2: return out
    rising = bars[1].close >= bars[0].close
    extreme = max(bars[0].high,bars[1].high) if rising else min(bars[0].low,bars[1].low)
    value = bars[0].low if rising else bars[0].high
    acceleration = .02
    out[1] = value
    for i in range(2,len(bars)):
        value += acceleration*(extreme-value)
        if rising:
            value = min(value,bars[i-1].low,bars[i-2].low)
            if bars[i].low < value:
                rising = False; value = extreme; extreme = bars[i].low; acceleration = .02
            elif bars[i].high > extreme:
                extreme = bars[i].high; acceleration = min(.2,acceleration+.02)
        else:
            value = max(value,bars[i-1].high,bars[i-2].high)
            if bars[i].high > value:
                rising = True; value = extreme; extreme = bars[i].high; acceleration = .02
            elif bars[i].low < extreme:
                extreme = bars[i].low; acceleration = min(.2,acceleration+.02)
        out[i] = value
    return out


class PriceStrategy(Strategy):
    def __init__(self, strategy_id: str, feed: Feed):
        self.id, self.feed = strategy_id, feed

    def evaluate(self, bars: list[Bar], timeframe: Timeframe) -> list[Signal]:
        bars = validate_bars(bars,self.feed)
        if len(bars) < 3: return []
        close = [b.close for b in bars]
        volatility = atr(bars)
        fast, slow = (sma(close,20),sma(close,50)) if self.id == 'sma_cross' else (ema(close,9),ema(close,21))
        macdfast, macdslow = ema(close,12),ema(close,26)
        macd = [a-b for a,b in zip(macdfast[25:],macdslow[25:])]
        macdsignal = [None]*25+ema(macd,9)
        rs, dx, sar = rsi(close), adx(bars), psar(bars)
        mids = sma(close,20)
        upper,lower = [],[]
        for i,m in enumerate(mids):
            std = sqrt(sum((v-m)**2 for v in close[i-19:i+1])/20) if m is not None else None
            upper.append(m+2*std if std is not None else None)
            lower.append(m-2*std if std is not None else None)
        ha_open,ha_close = [],[]
        for i,b in enumerate(bars):
            ha_open.append((ha_open[-1]+ha_close[-1])/2 if i else (b.open+b.close)/2)
            ha_close.append((b.open+b.high+b.low+b.close)/4)
        result = []
        session = None; opening = []; range_high = range_low = None; fired = False
        for i,b in enumerate(bars):
            sign = 0; features = {}; explanation = ''
            if i < 1: continue
            if self.id in ('ema_cross','sma_cross') and slow[i-1] is not None:
                before,now = fast[i-1]-slow[i-1],fast[i]-slow[i]
                sign = 1 if before <= 0 < now else -1 if before >= 0 > now else 0
                features = {'fast':fast[i],'slow':slow[i]}; explanation = 'Finalized moving averages crossed.'
            elif self.id == 'macd' and macdsignal[i-1] is not None:
                before = macdfast[i-1]-macdslow[i-1]-macdsignal[i-1]
                now = macdfast[i]-macdslow[i]-macdsignal[i]
                sign = 1 if before <= 0 < now else -1 if before >= 0 > now else 0
                features = {'macd':macdfast[i]-macdslow[i],'signal':macdsignal[i]}; explanation = 'MACD 12/26 crossed its nine-period EMA.'
            elif self.id == 'rsi_reversion' and dx[i] is not None and dx[i] < 20:
                sign = 1 if rs[i-1] <= 30 < rs[i] else -1 if rs[i-1] >= 70 > rs[i] else 0
                features = {'rsi14':rs[i],'adx14':dx[i]}; explanation = 'RSI re-entered its normal band while ADX was below 20.'
            elif self.id == 'bollinger_fade' and lower[i-1] is not None:
                sign = 1 if close[i-1] < lower[i-1] and close[i] >= lower[i] else -1 if close[i-1] > upper[i-1] and close[i] <= upper[i] else 0
                features = {'lower':lower[i],'upper':upper[i]}; explanation = 'Price closed back inside its 20-period, two-standard-deviation band.'
            elif self.id == 'bollinger_pattern' and i >= 25:
                # Prior local extrema confirmed two bars later; require a present neckline break.
                lows = [j for j in range(max(2,i-40),i-2) if close[j] < min(close[j-2:j]+close[j+1:j+3])]
                highs = [j for j in range(max(2,i-40),i-2) if close[j] > max(close[j-2:j]+close[j+1:j+3])]
                if len(lows) >= 2:
                    a,z = lows[-2:]; neckline = max(close[a:z+1])
                    if lower[a] is not None and close[a] < lower[a] and close[z] > lower[z] and close[i-1] <= neckline < close[i]: sign = 1
                if len(highs) >= 2 and not sign:
                    a,z = highs[-2:]; neckline = min(close[a:z+1])
                    if upper[a] is not None and close[a] > upper[a] and close[z] < upper[z] and close[i-1] >= neckline > close[i]: sign = -1
                explanation = 'Confirmed Bollinger W/M pattern neckline broke on this finalized bar; historical pivots are not signal timestamps.'
            elif self.id in ('opening_range','dual_thrust'):
                if timeframe not in (Timeframe.M1,Timeframe.M5,Timeframe.M15): continue
                local = datetime.fromtimestamp(b.time,ZoneInfo('America/New_York'))
                minute = local.hour*60+local.minute
                if local.weekday() >= 5 or not 570 <= minute < 960: continue
                if local.date() != session:
                    session=local.date(); opening=[]; range_high=range_low=None; fired=False
                if minute < 600:
                    opening.append(b); continue
                if range_high is None and opening and datetime.fromtimestamp(opening[0].time,ZoneInfo('America/New_York')).strftime('%H:%M') == '09:30':
                    range_high=max(x.high for x in opening);range_low=min(x.low for x in opening)
                    if self.id == 'dual_thrust':
                        width=max(range_high-min(x.close for x in opening),max(x.close for x in opening)-range_low)
                        range_high=opening[0].open+.5*width;range_low=opening[0].open-.5*width
                if range_high is not None and not fired:
                    sign=1 if b.close>range_high else -1 if b.close<range_low else 0
                    fired=bool(sign);features={'upper':range_high,'lower':range_low}
                explanation='Finalized US 09:30–10:00 opening-range threshold crossed; one event per session. Dual Thrust variant uses K=0.5 on the opening window.'
            elif self.id == 'psar' and i >= 14 and sar[i-1] is not None:
                sign=1 if close[i-1]<=sar[i-1] and close[i]>sar[i] else -1 if close[i-1]>=sar[i-1] and close[i]<sar[i] else 0
                features={'psar':sar[i],'atr14':volatility[i]};explanation='Parabolic SAR direction reversed; ATR threshold is frozen at observation, not a simulated trailing action.'
            elif self.id == 'heikin_ashi' and i >= 2:
                now=ha_close[i]-ha_open[i];prior=ha_close[i-1]-ha_open[i-1];before=ha_close[i-2]-ha_open[i-2]
                sign=1 if before<=0<prior and now>0 else -1 if before>=0>prior and now<0 else 0
                features={'ha_open':ha_open[i],'ha_close':ha_close[i]};explanation='Two finalized Heikin-Ashi candles confirm a color reversal; reference price is the actual close.'
            if sign and volatility[i] is not None:
                result.append(make_signal(self.id,b,timeframe,sign,volatility[i],explanation,features))
        return result


PRICE_STRATEGIES = {
    'ema_cross': ('EMA crossover','EMA 9/21 research control'),
    'sma_cross': ('SMA crossover','SMA 20/50 research control'),
    'macd': ('MACD oscillator','MACD 12/26/9 finalized crossover'),
    'rsi_reversion': ('RSI mean reversion','RSI 14 re-entry with ADX 14 below 20'),
    'bollinger_fade': ('Bollinger fade','20-period band re-entry'),
    'bollinger_pattern': ('Bollinger W/M','Confirmed pivots and current neckline break'),
    'opening_range': ('US opening range','09:30–10:00 New York window; intraday only'),
    'dual_thrust': ('Dual Thrust opening variant','K=0.5 applied to the cash opening window'),
    'psar': ('Parabolic SAR','0.02 step/0.20 maximum with frozen ATR reference levels'),
    'heikin_ashi': ('Heikin-Ashi momentum','Two closed candles confirm a color reversal'),
}


def strategy_catalog(feed: Feed) -> list[StrategyInfo]:
    return [StrategyInfo(id=k,name=v[0],description=v[1],enabled=True) for k,v in PRICE_STRATEGIES.items()] + [
        StrategyInfo(id='volume_confirmation',name='Volume confirmation filter',description='Optional consolidated-volume filter',
            enabled=feed==Feed.SIP,reason=None if feed==Feed.SIP else 'needs SIP data',requires=['volume_confirmation'])]


def get_strategy(strategy_id: str, feed: Feed = Feed.IEX) -> Strategy:
    if strategy_id == 'volume_confirmation':
        require_capability('volume_confirmation',feed)
        raise ValueError('Volume confirmation is a filter, not a standalone strategy')
    if strategy_id not in PRICE_STRATEGIES: raise ValueError(f'Unknown strategy: {strategy_id}')
    return PriceStrategy(strategy_id,feed)
