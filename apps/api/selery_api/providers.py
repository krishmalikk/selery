"""Market-data adapters. Alpaca egress is strictly GET plus an allowlisted data path."""
import asyncio
import json
import re
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import httpx
from selery_shared.models import Bar,Feed,NewsItem,Provenance,Quote,Timeframe
from .config import ROOT,Config

UTC=timezone.utc
TF_MAP={'1m':'1Min','5m':'5Min','15m':'15Min','1h':'1Hour','4h':'4Hour','1D':'1Day','1W':'1Week'}
SECONDS={'1m':60,'5m':300,'15m':900,'1h':3600,'4h':14400,'1D':86400,'1W':604800}

def valid_symbol(symbol:str):
    if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,11}',symbol):raise ValueError('Invalid symbol')
    return symbol

def parse_bars(payload,symbol,tf,feed):
    result=[]
    now=int(datetime.now(UTC).timestamp())
    for raw in payload:
        dt=datetime.fromisoformat(raw['t'].replace('Z','+00:00'))
        ts=int(dt.timestamp())
        if tf==Timeframe.D1:
            local=dt.astimezone(ZoneInfo('America/New_York'))
            available=int(local.replace(hour=20,minute=0,second=0).timestamp())
        else:available=ts+SECONDS[tf]
        result.append(Bar(symbol=symbol,time=ts,available_at=available,open=raw['o'],high=raw['h'],low=raw['l'],close=raw['c'],volume=raw['v'],feed=feed,finalized=available<=now))
    return sorted(result,key=lambda b:b.time)

def provenance(feed,observed,stale=False,provider='alpaca'):
    now=datetime.now(UTC)
    return Provenance(provider=provider,feed=feed,observed_at=datetime.fromtimestamp(observed,UTC),available_at=datetime.fromtimestamp(observed,UTC),retrieved_at=now,stale=stale)

def parse_news(payload):
    return [NewsItem(id=str(n['id']),headline=n['headline'],summary=n.get('summary',''),url=n['url'],source=n.get('source','Alpaca'),published_at=n['created_at'],symbols=n.get('symbols',[])) for n in payload]

class FixtureProvider:
    async def bars(self,symbol, timeframe, feed=Feed.IEX, limit=1000):
        valid_symbol(symbol)
        path=ROOT/'packages/fixtures'/f'{symbol}-{TF_MAP[timeframe]}-{feed}.json'
        if not path.exists():raise ValueError(f'No recorded {feed} {timeframe} fixture for {symbol}; no synthetic fallback.')
        payload=json.loads(path.read_text())['payload']['bars']
        return parse_bars(payload,symbol,timeframe,feed)[-limit:]

    async def quotes(self,symbols):
        quotes=[]
        for symbol in symbols:
            bars=await self.bars(symbol,Timeframe.D1)
            latest,previous=bars[-1],bars[-2]
            change=latest.close-previous.close
            quotes.append(Quote(symbol=symbol,price=latest.close,change=change,change_percent=100*change/previous.close,provenance=provenance(Feed.IEX,latest.available_at,True,'alpaca-recording'),sparkline=[b.close for b in bars[-24:]]))
        return quotes

    async def news(self,symbols):
        data=json.loads((ROOT/'packages/fixtures/news.json').read_text())['payload']['news']
        return [n for n in parse_news(data) if set(n.symbols)&set(symbols)]

class AlpacaProvider:
    def __init__(self,config:Config):
        self.config=config
        self.client=httpx.AsyncClient(base_url='https://data.alpaca.markets',headers={'APCA-API-KEY-ID':config.key,'APCA-API-SECRET-KEY':config.secret},timeout=20,follow_redirects=False)
        self._cache={}
        self._lock=asyncio.Lock()

    async def get(self,path,params,ttl=15):
        allowed=re.fullmatch(r'/v2/stocks/[A-Z0-9.\-]+/bars',path) or path in ('/v2/stocks/snapshots','/v1beta1/news')
        if not allowed:raise ValueError('Market-data path is not allowlisted')
        cache_key=(path,json.dumps(params,sort_keys=True))
        async with self._lock:
            now=asyncio.get_running_loop().time()
            if cache_key in self._cache and now-self._cache[cache_key][0]<ttl:return self._cache[cache_key][1]
            for attempt in range(3):
                response=await self.client.get(path,params=params)
                if response.status_code!=429:break
                await asyncio.sleep(min(2**attempt,4))
            if response.status_code!=200:raise ValueError(f'Alpaca market data unavailable (HTTP {response.status_code}).')
            payload=response.json()
            self._cache[cache_key]=(now,payload)
            return payload

    async def bars(self,symbol,timeframe,feed=Feed.IEX,limit=1000):
        valid_symbol(symbol)
        if feed not in (Feed.IEX,Feed.SIP):raise ValueError('Unsupported Alpaca feed')
        end=datetime.now(UTC)-timedelta(minutes=16 if feed==Feed.SIP else 0)
        days={'1m':7,'5m':30,'15m':60,'1h':180,'4h':365,'1D':730,'1W':1825}[timeframe]
        data=await self.get(f'/v2/stocks/{symbol}/bars',{'feed':str(feed),'timeframe':TF_MAP[timeframe],'start':(end-timedelta(days=days)).isoformat(),'end':end.isoformat(),'limit':min(limit,10000),'adjustment':'raw','sort':'desc'},30)
        return parse_bars(data.get('bars',[]),symbol,timeframe,feed)

    async def quotes(self,symbols):
        for s in symbols:valid_symbol(s)
        data=await self.get('/v2/stocks/snapshots',{'symbols':','.join(symbols),'feed':'iex'},3)
        result=[]
        for symbol in symbols:
            snapshot=data.get(symbol,{})
            latest=snapshot.get('latestTrade') or {}
            if not latest:continue
            previous=(snapshot.get('prevDailyBar') or {}).get('c')
            quote=snapshot.get('latestQuote') or {}
            dt=datetime.fromisoformat(latest['t'].replace('Z','+00:00'))
            price=latest['p'];change=price-previous if previous else None
            result.append(Quote(symbol=symbol,price=price,change=change,change_percent=100*change/previous if previous else None,bid=quote.get('bp'),ask=quote.get('ap'),provenance=provenance(Feed.IEX,dt.timestamp(),(datetime.now(UTC)-dt).total_seconds()>120)))
        return result

    async def news(self,symbols):
        data=await self.get('/v1beta1/news',{'symbols':','.join(symbols),'limit':30,'include_content':'false'},60)
        return parse_news(data.get('news',[]))
