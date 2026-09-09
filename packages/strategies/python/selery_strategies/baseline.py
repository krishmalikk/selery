"""Original causal EMA crossover, a research control rather than a recommendation."""
import hashlib
from selery_shared.models import Bar,Signal,Strategy,Timeframe
from selery_shared.indicators import ema,atr

class EmaCross(Strategy):
    id='ema_cross'
    def evaluate(self,bars:list[Bar],timeframe:Timeframe)->list[Signal]:
        bars=[b for b in bars if b.finalized]
        close=[b.close for b in bars]
        fast,slow,volatility=ema(close,9),ema(close,21),atr(bars)
        result=[]
        for i in range(21,len(bars)):
            previous=fast[i-1]-slow[i-1];current=fast[i]-slow[i]
            if not ((previous<=0<current) or (previous>=0>current)):continue
            bar=bars[i];sign=1 if current>0 else -1
            distance=max(volatility[i] or bar.close*0.01,bar.close*0.002)*1.5
            sid=hashlib.sha256(f'{bar.symbol}:{timeframe}:{bar.feed}:{self.id}:1:{bar.time}'.encode()).hexdigest()[:24]
            result.append(Signal(id=sid,symbol=bar.symbol,strategy=self.id,timeframe=timeframe,time=bar.time,available_at=bar.available_at,direction='bullish' if sign>0 else 'bearish',reference_price=bar.close,stop=bar.close-sign*distance,target=bar.close+sign*distance*2,feed=bar.feed,features={'ema9':fast[i],'ema21':slow[i],'atr14':volatility[i] or 0},explanation='EMA 9 crossed '+('above' if sign>0 else 'below')+' EMA 21 on a finalized bar. Reference thresholds use 1.5× ATR and a 2:1 distance ratio; no calibrated confidence.'))
        return result
