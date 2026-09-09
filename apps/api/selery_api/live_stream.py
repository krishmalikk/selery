"""One server-side IEX market-data stream, shared by authenticated clients."""
import asyncio
import json
from datetime import datetime,timezone
from websockets.asyncio.client import connect
from selery_shared.models import Feed,Quote,WatchlistResponse
from .providers import provenance

async def publish(app,event):
    for queue in list(app.state.subscribers):
        if queue.full():
            try:queue.get_nowait()
            except asyncio.QueueEmpty:pass
        queue.put_nowait(event)

async def market_stream(app,symbols):
    delay=1
    while True:
        try:
            async with connect('wss://stream.data.alpaca.markets/v2/iex',open_timeout=20,ping_interval=20,max_size=2**20) as socket:
                await socket.send(json.dumps({'action':'auth','key':app.state.config.key,'secret':app.state.config.secret}))
                subscribed=False
                async for message in socket:
                    for item in json.loads(message):
                        kind=item.get('T')
                        if kind=='error':raise ValueError('Market stream rejected')
                        if kind=='success' and item.get('msg')=='authenticated' and not subscribed:
                            await socket.send(json.dumps({'action':'subscribe','trades':symbols,'bars':symbols}));subscribed=True;delay=1
                        elif kind=='t' and item.get('S') in symbols:
                            symbol=item['S'];ts=datetime.fromisoformat(item['t'].replace('Z','+00:00')).timestamp()
                            previous=app.state.live_quotes.get(symbol)
                            if previous and previous.provenance.observed_at.timestamp()>ts:continue
                            base=previous.price-previous.change if previous and previous.change is not None else None
                            price=float(item['p']);change=price-base if base else None
                            app.state.live_quotes[symbol]=Quote(symbol=symbol,price=price,change=change,change_percent=change/base*100 if base else None,provenance=provenance(Feed.IEX,ts),sparkline=previous.sparkline if previous else [])
                            now=asyncio.get_running_loop().time()
                            if now-app.state.last_stream_publish>=0.5:
                                app.state.last_stream_publish=now
                                await publish(app,{'type':'quotes','timestamp':datetime.now(timezone.utc).isoformat(),'data':WatchlistResponse(quotes=list(app.state.live_quotes.values()),data_mode='live').model_dump(mode='json')})
                        elif kind=='b':
                            await publish(app,{'type':'chart','timestamp':datetime.now(timezone.utc).isoformat(),'data':{'symbol':item.get('S'),'timeframe':'1m','feed':'iex'}})
        except asyncio.CancelledError:raise
        except Exception as exc:app.state.store.audit('market_stream_reconnect',{'type':type(exc).__name__,'retry_seconds':delay})
        await asyncio.sleep(delay);delay=min(delay*2,60)
