import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from uuid import uuid4
from fastapi import FastAPI,Depends,HTTPException,Request,Response,WebSocket,WebSocketDisconnect,Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from selery_shared.models import *
from selery_shared.indicators import chart_indicators,capabilities,require_capability
from selery_strategies.baseline import EmaCross
from .config import Config
from .providers import FixtureProvider,AlpacaProvider,provenance,valid_symbol
from .storage import Store
from .auth import Auth
from .outcomes import score_signal,summarize
from .research import evaluate

WATCHLIST=['SPY','QQQ','AAPL','NVDA']
UTC=timezone.utc

def create_app(config=None,provider=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.config=config or Config.load()
        app.state.provider=provider or (FixtureProvider() if app.state.config.data_mode=='fixtures' else AlpacaProvider(app.state.config))
        app.state.store=Store(app.state.config.database_url)
        from .public_traders import PublicRegistry
        app.state.public_registry=PublicRegistry(app.state.store)
        from .conversations import Conversations
        app.state.conversations=Conversations(app.state.store)
        app.state.auth=Auth(app.state.config,app.state.store)
        from .passkeys import Passkeys
        app.state.passkeys=Passkeys(app.state.store)
        app.state.started_at=int(time.time())
        app.state.subscribers=set()
        app.state.live_quotes={}
        app.state.last_stream_publish=0
        task=asyncio.create_task(observe(app))
        upstream=None
        if app.state.config.data_mode=='live':
            from .live_stream import market_stream
            upstream=asyncio.create_task(market_stream(app,WATCHLIST))
        yield
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass
        if upstream:
            upstream.cancel()
            try:await upstream
            except asyncio.CancelledError:pass
        if hasattr(app.state.provider,'client'):await app.state.provider.client.aclose()
        app.state.store.engine.dispose()

    app=FastAPI(title='SELERY Research API',version='1.0.0',lifespan=lifespan)
    origins=list(config.allowed_origins) if config else __import__('os').getenv('SELERY_ALLOWED_ORIGINS','http://localhost:3000').split(',')
    app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=['GET','POST','PUT'],allow_headers=['Content-Type','Authorization'])

    @app.exception_handler(ValueError)
    async def validation_error(request,exc):return __import__('fastapi').responses.JSONResponse(status_code=422,content={'detail':str(exc)})

    def authorized(request:Request):return request.app.state.auth.require(request)

    from .passkeys import register_routes as register_passkeys
    register_passkeys(app,authorized)

    from .notifications import register_routes
    register_routes(app,authorized)

    @app.get('/health')
    def health():
        try:
            with app.state.store.engine.connect() as connection:connection.exec_driver_sql('SELECT 1')
        except Exception:
            return __import__('fastapi').responses.JSONResponse(status_code=503,content={'status':'unavailable','service':'selery-research'})
        return {'status':'ok','service':'selery-research','version':'0.1.0'}

    class Login(BaseModel):password:str=Field(max_length=1000)

    @app.post('/api/v1/auth/login')
    def login(body:Login,request:Request,response:Response):
        token=app.state.auth.login(body.password,request.client.host if request.client else 'local')
        secure=request.headers.get('x-forwarded-proto',request.url.scheme)=='https'
        response.set_cookie('selery_session',token,max_age=3600,httponly=True,secure=secure,samesite='lax',path='/')
        response.headers['Cache-Control']='no-store'
        return {'token':token,'expires_in':3600}

    @app.post('/api/v1/auth/logout',dependencies=[Depends(authorized)])
    def logout(request:Request,response:Response):
        token=app.state.auth.require(request);app.state.auth.revoked[token]=time.time()+3600
        response.delete_cookie('selery_session',path='/')
        return {'ok':True}

    @app.post('/api/v1/auth/stream-ticket',dependencies=[Depends(authorized)])
    def ticket(request:Request):return {'ticket':app.state.auth.stream_ticket(app.state.auth.require(request))}

    @app.get('/api/v1/watchlist',response_model=WatchlistResponse,dependencies=[Depends(authorized)])
    async def watchlist():
        quotes=await app.state.provider.quotes(WATCHLIST)
        if app.state.config.data_mode=='live':
            for quote in quotes:
                cached=app.state.live_quotes.get(quote.symbol)
                if not cached or cached.provenance.observed_at<quote.provenance.observed_at:app.state.live_quotes[quote.symbol]=quote
        return WatchlistResponse(quotes=quotes,data_mode=app.state.config.data_mode)

    async def get_chart(symbol,timeframe,feed,limit=1000):
        valid_symbol(symbol)
        bars=await app.state.provider.bars(symbol,timeframe,feed,limit)
        if not bars:raise HTTPException(404,'No bars for this symbol and feed')
        finalized=[b for b in bars if b.finalized]
        signals=EmaCross().evaluate(finalized,timeframe)
        # Reuse signal-time confidence, never retrospectively apply today's model.
        for index,signal in enumerate(signals):
            signals[index]=signal.model_copy(update={'confidence_reason':'No calibrated prediction was recorded when this signal became available. Historical signals are not scored retroactively.'})
            snapshot=app.state.store.get('signals',signal.id)
            if snapshot:
                original=Signal.model_validate(snapshot)
                from .model_registry import scope_for
                if scope_for(original)==scope_for(signal):signals[index]=original
        observed=bars[-1].available_at if bars[-1].finalized else int(time.time())
        return ChartResponse(symbol=symbol,timeframe=timeframe,bars=bars,signals=signals,indicators=chart_indicators(bars,feed),capabilities=capabilities(feed),provenance=provenance(feed,observed,app.state.config.data_mode=='fixtures' or observed<time.time()-120, 'alpaca-recording' if app.state.config.data_mode=='fixtures' else 'alpaca'))

    @app.get('/api/v1/chart/{symbol}',response_model=ChartResponse,dependencies=[Depends(authorized)])
    async def chart(symbol:str,timeframe:Timeframe=Timeframe.M5,feed:Feed=Feed.IEX,limit:int=Query(1000,ge=80,le=2000)):return await get_chart(symbol,timeframe,feed,limit)

    @app.get('/api/v1/news',response_model=NewsResponse,dependencies=[Depends(authorized)])
    async def news():
        from .news_pipeline import process_news
        timestamp=datetime.now(UTC)
        analysis=process_news(await app.state.provider.news(WATCHLIST),observed_at=timestamp)
        return NewsResponse(items=analysis.items,retrieved_at=timestamp,stale=app.state.config.data_mode=='fixtures')

    @app.get('/api/v1/providers',dependencies=[Depends(authorized)])
    def providers():
        import os
        from .adapters import provider_catalog
        return provider_catalog(dict(os.environ))

    @app.post('/api/v1/providers/query',dependencies=[Depends(authorized)])
    async def provider_query(body:DataQuery):
        import os
        from .adapters import FinnhubAdapter,AlphaVantageAdapter,TwelveDataAdapter,FredAdapter,SecAdapter,FrenchAdapter,YFinanceAdapter
        registry={'finnhub':lambda:FinnhubAdapter(os.getenv('FINNHUB_API_KEY','')),'alpha_vantage':lambda:AlphaVantageAdapter(os.getenv('ALPHA_VANTAGE_API_KEY','')),'twelve_data':lambda:TwelveDataAdapter(os.getenv('TWELVE_DATA_API_KEY','')),'fred':lambda:FredAdapter(os.getenv('FRED_API_KEY','')),'sec':lambda:SecAdapter(os.getenv('SEC_USER_AGENT','')),'kenneth_french':FrenchAdapter,'yfinance':YFinanceAdapter}
        query=body.model_dump(exclude_none=True,exclude={'provider','dataset','archive'})
        try:batch=await registry[body.provider]().fetch(body.dataset,**query)
        except KeyError as exc:raise HTTPException(422,f'Missing required provider query field: {exc.args[0]}') from None
        result={'provenance':batch.provenance(),'records':batch.records}
        if body.archive:
            from .ingestion import RawArchive,ingest_batch
            from .config import ROOT
            archive=RawArchive(ROOT/'data/raw')
            if batch.records and all(key in batch.records[0] for key in ('open','high','low','close','volume')):
                result['ingestion']=ingest_batch(app.state.store,archive,batch,body.symbol,body.timeframe)
            else:result['archive_id']=archive.put(batch)
        return result

    @app.get('/api/v1/features/catalog',dependencies=[Depends(authorized)])
    def features(feed:Feed=Feed.IEX):
        from selery_strategies.alpha import alpha_catalog
        return alpha_catalog(feed)

    @app.get('/api/v1/strategies',response_model=list[StrategyInfo],dependencies=[Depends(authorized)])
    def strategies():
        try:
            from selery_strategies.library import strategy_catalog
            from selery_strategies.advanced import advanced_catalog
            return strategy_catalog(Feed.IEX)+advanced_catalog(Feed.IEX)
        except ImportError:
            return [StrategyInfo(id='ema_cross',name='EMA 9/21 crossover',description='Causal price crossover control with ATR reference thresholds.',enabled=True)]

    @app.post('/api/v1/research',response_model=ResearchReport,dependencies=[Depends(authorized)])
    async def research(body:ResearchRequest):
        bars=await app.state.provider.bars(body.symbol,body.timeframe,body.feed,2000)
        benchmark=await app.state.provider.bars('SPY',body.timeframe,body.feed,2000)
        strategy=EmaCross()
        if body.strategy!='ema_cross':
            try:
                from selery_strategies.library import get_strategy
                strategy=get_strategy(body.strategy,body.feed)
            except ImportError:raise HTTPException(422,'Strategy is not available')
        report=await asyncio.to_thread(evaluate,body,bars,benchmark,strategy)
        app.state.store.put('reports',report,report.id)
        app.state.store.audit('research_completed',{'id':report.id,'request':body.model_dump(mode='json')})
        return report

    @app.get('/api/v1/research',response_model=list[ResearchReport],dependencies=[Depends(authorized)])
    def reports(limit:int=Query(10,ge=1,le=50),offset:int=Query(0,ge=0)):
        return app.state.store.list('reports',limit,offset)

    @app.get('/api/v1/research/{id}',response_model=ResearchReport,dependencies=[Depends(authorized)])
    def report(id:str):
        item=app.state.store.get('reports',id)
        if not item:raise HTTPException(404,'Research report not found')
        return item

    @app.post('/api/v1/research/size',response_model=SizingResponse,dependencies=[Depends(authorized)])
    def size(body:SizingRequest):
        distance=abs(body.reference_price-body.stop)
        if distance<0.000001:raise HTTPException(422,'Reference price and stop must differ')
        risk=body.research_capital*body.risk_percent/100
        units=int(min(risk/distance,body.research_capital*body.max_allocation_percent/100/body.reference_price))
        return SizingResponse(units=units,risk_budget=risk,analytical_risk=units*distance,notional=units*body.reference_price)

    @app.get('/api/v1/outcomes',response_model=list[OutcomeSummary],dependencies=[Depends(authorized)])
    def outcomes():
        snapshots={s['id']:Signal.model_validate(s) for s in app.state.store.list('signals',10000)}
        groups={}
        for raw in app.state.store.list('outcomes',10000):
            result=Outcome.model_validate(raw);signal=snapshots.get(result.signal_id)
            if signal:groups.setdefault((signal.symbol,signal.strategy,signal.feed,signal.strategy_version,signal.timeframe,signal.horizon_bars),[]).append(result)
        reports=app.state.store.list('reports',200)
        summaries=[]
        for (symbol,strategy,feed,version,timeframe,horizon),items in groups.items():
            match=next((r for r in reports if r['request']['symbol']==symbol and r['request']['strategy']==strategy and r['request']['feed']==feed and r['request']['timeframe']==timeframe and r['request']['horizon_bars']==horizon and version=='1'),None)
            summaries.append(summarize(f'{symbol} · {strategy} · v{version} · {timeframe} · {horizon} bars',feed,items,match['metrics'].get('hit_rate') if match else None))
        return summaries

    @app.get('/api/v1/journal',response_model=list[JournalEntry],dependencies=[Depends(authorized)])
    def journal(limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0)):return app.state.store.list('journal',limit,offset)

    @app.post('/api/v1/journal',response_model=JournalEntry,dependencies=[Depends(authorized)])
    def save_journal(body:JournalEntry):
        valid_symbol(body.symbol)
        old=app.state.store.get('journal',body.id) if body.id else None
        if body.id and not old:raise HTTPException(404,'Journal entry not found')
        if body.chart_snapshot and not body.chart_snapshot.startswith('data:image/png;base64,'):raise HTTPException(422,'Only PNG chart snapshots are accepted')
        entry=body.model_copy(update={'id':body.id or uuid4().hex,'created_at':old['created_at'] if old else datetime.now(UTC)})
        app.state.store.put('journal',entry,entry.id);app.state.store.audit('journal_saved_by_user',{'id':entry.id})
        return entry

    @app.get('/api/v1/alerts',response_model=list[Alert],dependencies=[Depends(authorized)])
    def alerts():return app.state.store.list('alerts')

    @app.post('/api/v1/alerts/{id}/read',dependencies=[Depends(authorized)])
    def read_alert(id:str):
        item=app.state.store.get('alerts',id)
        if not item:raise HTTPException(404,'Alert not found')
        item['read']=True;app.state.store.put('alerts',item,id)
        return {'ok':True}

    @app.get('/api/v1/settings',response_model=Settings,dependencies=[Depends(authorized)])
    def settings():
        from .assistant import LlmConfig
        return Settings(data_mode=app.state.config.data_mode,feed=Feed.IEX,llm_monthly_cap_usd=app.state.config.llm_cap,llm_spent_usd=app.state.store.spend(),llm_enabled=LlmConfig.load().active(app.state.config.llm_cap) and not bool(app.state.store.get('settings','llm-kill-switch')))

    @app.get('/api/v1/jobs',response_model=list[Job],dependencies=[Depends(authorized)])
    def jobs():return app.state.store.list('jobs')

    @app.post('/api/v1/jobs/research',response_model=Job,dependencies=[Depends(authorized)])
    async def enqueue_research(body:ResearchRequest):
        import os
        from arq import create_pool
        from arq.connections import RedisSettings
        url=os.getenv('SELERY_REDIS_URL','')
        if not url:raise HTTPException(422,'Configure Redis and the worker before queueing research jobs.')
        job=Job(id=uuid4().hex,kind='research',status='queued',created_at=datetime.now(UTC))
        app.state.store.put('jobs',job,job.id)
        pool=None
        try:
            pool=await create_pool(RedisSettings.from_dsn(url))
            await pool.enqueue_job('research_job',job.id,body.model_dump(mode='json'))
        except Exception:
            app.state.store.put('jobs',job.model_copy(update={'status':'failed','reason':'Research queue unavailable'}),job.id)
            raise HTTPException(503,'Research queue unavailable') from None
        finally:
            if pool:await pool.aclose()
        return job

    @app.get('/api/v1/models',dependencies=[Depends(authorized)])
    def models():
        from .model_registry import registry_models
        registry=registry_models(app.state.store)
        trained=any(item.get('status')=='champion' for item in registry)
        return {'status':'qualified' if trained else 'untrained','reason':'Confidence requires a qualified, scope-matched model activated before each signal.' if trained else 'No validated model is promoted. Confidence and SHAP remain unavailable. Training is manual.','registry':registry,'validation':'purged walk-forward with embargo; final holdout untouched'}

    @app.post('/api/v1/models/train',dependencies=[Depends(authorized)])
    async def train(body:ResearchRequest):
        from .ml import train_meta
        from .config import ROOT
        from selery_strategies.library import get_strategy
        bars=await app.state.provider.bars(body.symbol,body.timeframe,body.feed,10000)
        strategy=get_strategy(body.strategy,body.feed)
        signals=[signal.model_copy(update={'horizon_bars':body.horizon_bars}) for signal in strategy.evaluate(bars,body.timeframe)]
        result=await asyncio.to_thread(train_meta,signals,bars,app.state.store,ROOT/'data/models')
        return result

    @app.get('/api/v1/models/explain/{signal_id}',dependencies=[Depends(authorized)])
    async def explain_signal(signal_id:str):
        from .ml import predict_signal
        from .config import ROOT
        snapshot=app.state.store.get('signals',signal_id)
        if not snapshot:raise HTTPException(404,'Immutable forward signal not found')
        signal=Signal.model_validate(snapshot)
        bars=await app.state.provider.bars(signal.symbol,signal.timeframe,signal.feed,2000)
        return await asyncio.to_thread(predict_signal,signal,bars,app.state.store,ROOT/'data/models')

    @app.get('/api/v1/domain/SPY',dependencies=[Depends(authorized)])
    def domain():
        from .domain import spy_snapshot
        return spy_snapshot(feed=Feed.IEX)

    @app.post('/api/v1/chat',response_model=ChatResponse,dependencies=[Depends(authorized)])
    async def chat(body:ChatRequest):
        if body.activity_id:
            from .public_traders import activity_chat
            return await activity_chat(app,body)
        valid_symbol(body.symbol)
        chart=await get_chart(body.symbol,Timeframe.M5,Feed.IEX)
        news_items=await app.state.provider.news([body.symbol])
        last=chart.bars[-1]
        message=f'{body.symbol}: latest available reference close is ${last.close:.2f} on IEX. '
        message+='This is recorded/stale data. ' if chart.provenance.stale else ''
        if chart.signals:
            signal=chart.signals[-1];message+=f'The latest EMA crossover observation is {signal.direction}. {signal.explanation} '
        message+='A price move cannot be attributed causally to a headline from timing alone. Volume-based explanations are disabled on IEX. '
        message+='This local data summary does not use an LLM; it cannot answer arbitrary research questions.'
        citations=[Citation(label='IEX reference bar',timestamp=datetime.fromtimestamp(last.available_at,UTC),data_id=f'{body.symbol}:5m:iex:{last.time}')]
        citations.extend(Citation(label=n.headline,timestamp=n.published_at,url=n.url,data_id=n.id) for n in news_items[:3])
        from .assistant import LlmConfig,BoundedAssistant
        llm=LlmConfig.load()
        if llm.active(app.state.config.llm_cap):
            context={'bar':last.model_dump(mode='json'),'signal':chart.signals[-1].model_dump(mode='json') if chart.signals else None,'news':[n.model_dump(mode='json') for n in news_items[:3]],'citations':[c.model_dump(mode='json') for c in citations]}
            return await BoundedAssistant(app.state.store,llm,app.state.config.llm_cap).research(body,context,citations)
        if body.debate:raise HTTPException(422,'LLM debate is disabled until a provider and hard spending cap are configured.')
        return ChatResponse(message=message,citations=citations,mode='local')

    from .public_traders import register_routes as register_public_routes
    register_public_routes(app,authorized,get_chart)
    from .conversations import register_routes as register_conversations
    register_conversations(app,authorized,get_chart)

    @app.middleware('http')
    async def public_cache_policy(request,call_next):
        response=await call_next(request)
        if request.url.path.startswith(('/api/v1/public-traders','/api/v1/conversations')) or request.url.path=='/api/v1/chat':
            response.headers['Cache-Control']='private, no-store'
        return response

    @app.websocket('/api/v1/stream')
    async def stream(websocket:WebSocket):
        session=app.state.auth.consume_ticket(websocket.query_params.get('ticket',''))
        if not session:
            await websocket.close(code=4401);return
        origin=websocket.headers.get('origin')
        if origin and origin not in app.state.config.allowed_origins:
            await websocket.close(code=4403);return
        await websocket.accept();queue=asyncio.Queue(maxsize=10);app.state.subscribers.add(queue)
        try:
            while True:
                try:event=await asyncio.wait_for(queue.get(),timeout=20)
                except TimeoutError:event={'type':'heartbeat','timestamp':datetime.now(UTC).isoformat(),'data':{}}
                if not app.state.auth.verify(session):
                    await websocket.close(code=4401);return
                await websocket.send_json(event)
        except (WebSocketDisconnect,RuntimeError):pass
        finally:app.state.subscribers.discard(queue)

    return app

async def observe(app):
    """Forward-only capture. Fixture browsing never manufactures forward observations."""
    cycles=0
    while True:
        try:
            if app.state.subscribers:
                quotes=await app.state.provider.quotes(WATCHLIST)
                event={'type':'quotes','timestamp':datetime.now(UTC).isoformat(),'data':WatchlistResponse(quotes=quotes,data_mode=app.state.config.data_mode).model_dump(mode='json')}
                for queue in list(app.state.subscribers):
                    if not queue.full():queue.put_nowait(event)
            if app.state.config.data_mode=='live' and cycles%12==0:
                for symbol in WATCHLIST:
                    bars=await app.state.provider.bars(symbol,Timeframe.M5,Feed.IEX)
                    for signal in EmaCross().evaluate(bars,Timeframe.M5):
                        if signal.available_at<app.state.started_at or app.state.store.get('signals',signal.id):continue
                        from .ml import predict_signal
                        from .config import ROOT
                        prediction=await asyncio.to_thread(predict_signal,signal,bars,app.state.store,ROOT/'data/models',include_shap=False)
                        signal=signal.model_copy(update={'confidence':prediction['confidence'],'confidence_reason':prediction['reason']})
                        app.state.store.put('signals',signal,signal.id,immutable=True)
                        app.state.store.audit('signal_observed',{'id':signal.id,'model_id':prediction['model_id']})
                        alert=Alert(id=signal.id,kind='signal',title=f'{symbol} EMA crossover',body=signal.explanation,symbol=symbol,signal_id=signal.id,created_at=datetime.now(UTC))
                        app.state.store.put('alerts',alert,alert.id,immutable=True)
                        from .notifications import deliver_alert
                        await deliver_alert(app.state.store,alert.id)
                    for raw in app.state.store.list('signals',10000):
                        if raw['symbol']!=symbol:continue
                        signal=Signal.model_validate(raw)
                        existing=app.state.store.get('outcomes',signal.id)
                        if existing and existing['status'] not in ('pending','incomplete'):continue
                        app.state.store.put('outcomes',score_signal(signal,bars),signal.id)
            cycles+=1
        except asyncio.CancelledError:raise
        except Exception as exc:
            # Only exception type is retained: upstream bodies may contain sensitive details.
            app.state.store.audit('observer_error',{'type':type(exc).__name__})
        await asyncio.sleep(5)

app=create_app()
