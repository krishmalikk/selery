"""Explicit market-data-only connectivity check; never prints credentials."""
import asyncio
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'packages/shared/python'),str(ROOT/'packages/strategies/python')]
from selery_api.config import Config
from selery_api.providers import AlpacaProvider
from selery_shared.models import Feed,Timeframe
from websockets.asyncio.client import connect

async def run():
    config=Config.load();provider=AlpacaProvider(config)
    report={}
    try:
        report['quotes']=len(await provider.quotes(['SPY','QQQ','AAPL','NVDA']))
        report['iex_bars']=len(await provider.bars('SPY',Timeframe.M5,Feed.IEX,100))
        report['news']=len(await provider.news(['SPY','QQQ','AAPL','NVDA']))
        async with connect('wss://stream.data.alpaca.markets/v2/iex',open_timeout=15) as socket:
            await socket.send(json.dumps({'action':'auth','key':config.key,'secret':config.secret}))
            async with asyncio.timeout(20):
                async for message in socket:
                    data=json.loads(message)
                    if any(x.get('T')=='error' for x in data):raise ValueError('Market stream rejected')
                    if any(x.get('msg')=='authenticated' for x in data):report['iex_stream_authenticated']=True;break
    finally:await provider.client.aclose()
    (ROOT/'docs/live-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':asyncio.run(run())
