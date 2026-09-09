"""Manual research jobs. No scheduled training or paid LLM tasks."""
import os
from datetime import datetime,timezone
from arq.connections import RedisSettings
from .config import Config
from .storage import Store
from .providers import FixtureProvider,AlpacaProvider
from .research import evaluate
from selery_shared.models import ResearchRequest

async def startup(ctx):
    config=Config.load();ctx['store']=Store(config.database_url)
    ctx['provider']=FixtureProvider() if config.data_mode=='fixtures' else AlpacaProvider(config)

async def research_job(ctx,job_id,payload):
    store=ctx['store'];provider=ctx['provider'];body=ResearchRequest.model_validate(payload)
    job={'id':job_id,'kind':'research','status':'running','created_at':datetime.now(timezone.utc).isoformat(),'result_id':None,'reason':None}
    store.put('jobs',job,job_id)
    try:
        from selery_strategies.library import get_strategy
        strategy=get_strategy(body.strategy,body.feed)
        bars=await provider.bars(body.symbol,body.timeframe,body.feed,2000)
        benchmark=await provider.bars('SPY',body.timeframe,body.feed,2000)
        report=evaluate(body,bars,benchmark,strategy)
        store.put('reports',report,report.id)
        job.update(status='completed',result_id=report.id)
    except Exception as exc:job.update(status='failed',reason=type(exc).__name__)
    store.put('jobs',job,job_id)
    return job

async def shutdown(ctx):
    if hasattr(ctx['provider'],'client'):await ctx['provider'].client.aclose()
    ctx['store'].engine.dispose()

class WorkerSettings:
    functions=[research_job]
    on_startup=startup
    on_shutdown=shutdown
    redis_settings=RedisSettings.from_dsn(os.getenv('SELERY_REDIS_URL','redis://localhost:6379'))
    max_jobs=1
    job_timeout=600
    cron_jobs=[]
