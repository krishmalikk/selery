"""Private stock-scoped threads with durable turns and bounded conversational context."""
import asyncio
import json
import time
from datetime import datetime,timezone
from uuid import uuid4

import httpx
from fastapi import Depends,HTTPException,Query
from sqlalchemy import select,delete,insert,update,func,or_
from selery_shared.models import (Conversation,ConversationCreate,ConversationMessage,
    ConversationDetail,ConversationTurn,ConversationRename,Citation,ChatResponse,ChartResponse,Timeframe,Feed)
from .assistant import BoundedAssistant,LlmConfig
from .providers import valid_symbol
from .storage import tables,serial

UTC=timezone.utc

class Conversations:
    def __init__(self,store):
        self.store=store
        self.busy=set()  # Single API process, like the existing auth/observer.
        self.tasks=set()  # Hold generation tasks when the HTTP client disconnects.
        # A crash must never make a potentially billed pending request auto-retry.
        table=tables['conversation_messages']
        with store.engine.begin() as conn:
            rows=conn.execute(select(table.c.id,table.c.payload).where(table.c.payload['status'].as_string()=='pending')).all()
            for id,payload in rows:
                payload.update(status='failed',error='Response interrupted by backend restart. Billing may be unresolved; no automatic retry occurred.')
                conn.execute(update(table).where(table.c.id==id).values(payload=payload))

    def get(self,id):
        value=self.store.get('conversations',id)
        if not value: raise HTTPException(404,'Conversation not found')
        return Conversation.model_validate(value)

    def listing(self,limit,offset,q=''):
        table=tables['conversations']
        query=select(table.c.payload)
        if q:
            messages=tables['conversation_messages']
            matches=select(messages.c.payload['conversation_id'].as_string()).where(messages.c.payload['message'].as_string().icontains(q,autoescape=True))
            query=query.where(or_(table.c.payload['title'].as_string().icontains(q,autoescape=True),table.c.payload['symbol'].as_string().icontains(q,autoescape=True),table.c.id.in_(matches)))
        with self.store.engine.connect() as conn:
            rows=conn.execute(query.order_by(table.c.payload['updated_at'].as_string().desc(),table.c.id).limit(limit).offset(offset))
            return [Conversation.model_validate(row[0]) for row in rows]

    def detail(self,id):
        conversation=self.get(id);table=tables['conversation_messages']
        with self.store.engine.connect() as conn:
            rows=conn.execute(select(table.c.payload).where(table.c.payload['conversation_id'].as_string()==id).order_by(table.c.created_at,table.c.id).limit(200))
            messages=[ConversationMessage.model_validate(row[0]) for row in rows]
        return ConversationDetail(conversation=conversation,messages=messages)

    def create(self,symbol,signal=None,chart=None):
        now=datetime.now(UTC)
        item=Conversation(id=uuid4().hex,symbol=symbol,title=f'{symbol} signal discussion' if signal else f'{symbol} conversation',created_at=now,updated_at=now,
            signal=signal,chart_start=chart.bars[0].time if chart else None,chart_end=chart.bars[-1].time if chart else None)
        with self.store.engine.begin() as conn:
            if conn.scalar(select(func.count()).select_from(tables['conversations']))>=500:
                raise HTTPException(422,'Conversation limit reached. Delete an old conversation before creating another.')
            conn.execute(insert(tables['conversations']).values(id=item.id,created_at=now,payload=serial(item)))
            if chart:conn.execute(insert(tables['conversation_charts']).values(id=item.id,created_at=now,payload=serial(chart)))
        return item

    def remove(self,id):
        self.get(id)
        if id in self.busy: raise HTTPException(409,'Wait for the current reply before deleting this conversation')
        with self.store.engine.begin() as conn:
            conn.execute(delete(tables['conversation_messages']).where(tables['conversation_messages'].c.payload['conversation_id'].as_string()==id))
            conn.execute(delete(tables['conversations']).where(tables['conversations'].c.id==id))
            conn.execute(delete(tables['conversation_charts']).where(tables['conversation_charts'].c.id==id))

    def amend(self,id,**changes):
        item=self.get(id)
        if id in self.busy:raise HTTPException(409,'Wait for the current response before changing the conversation')
        item=item.model_copy(update={**changes,'updated_at':datetime.now(UTC)})
        self.store.put('conversations',item,id)
        return item

    def progress(self,user,text,citations):
        message=ConversationMessage(id=user.id+':answer',conversation_id=user.conversation_id,role='assistant',
            message=text,created_at=datetime.now(UTC),status='pending',phase='generating',citations=citations,mode='llm')
        previous=self.store.get('conversation_messages',message.id)
        if previous:message=message.model_copy(update={'created_at':datetime.fromisoformat(previous['created_at'])})
        self.store.put('conversation_messages',message,message.id)

    def finish(self,conversation,user,answer=None,error=None):
        now=datetime.now(UTC)
        user=user.model_copy(update={'status':'failed' if error else 'complete','error':error,'phase':None})
        with self.store.engine.begin() as conn:
            table=tables['conversation_messages']
            conn.execute(update(table).where(table.c.id==user.id).values(payload=serial(user)))
            if answer:
                message=ConversationMessage(id=user.id+':answer',conversation_id=conversation.id,role='assistant',
                    message=answer.message,created_at=now,citations=answer.citations,mode=answer.mode,cost_usd=answer.cost_usd)
                previous=conn.execute(select(table.c.payload).where(table.c.id==message.id)).first()
                if previous:
                    message=message.model_copy(update={'created_at':datetime.fromisoformat(previous[0]['created_at'])})
                    conn.execute(update(table).where(table.c.id==message.id).values(payload=serial(message)))
                else:conn.execute(insert(table).values(id=message.id,created_at=now,payload=serial(message)))
            elif error:
                partial=conn.execute(select(table.c.payload).where(table.c.id==user.id+':answer')).first()
                if partial:
                    value={**partial[0],'status':'failed','phase':None,'error':error}
                    conn.execute(update(table).where(table.c.id==user.id+':answer').values(payload=value))
            value=conversation.model_copy(update={'updated_at':now})
            conn.execute(update(tables['conversations']).where(tables['conversations'].c.id==conversation.id).values(payload=serial(value)))

def recent_history(messages):
    # Include only complete user/assistant pairs, newest ten pairs, <=16KB.
    # Failed/pending requests are not replayed; old answers remain historical text.
    pairs=[]
    for index in range(len(messages)-1):
        user,answer=messages[index:index+2]
        if user.role=='user' and user.status=='complete' and answer.role=='assistant' and answer.status=='complete' and answer.id==user.id+':answer':
            provenance=json.dumps({'answered_at':answer.created_at.isoformat(),'mode':answer.mode,'citations':[c.model_dump(mode='json') for c in answer.citations]})
            pairs.append([{'role':'user','content':user.message},{'role':'assistant','content':answer.message+'\nHistorical response provenance: '+provenance}])
    selected=[];size=0
    for pair in reversed(pairs[-10:]):
        count=sum(len(m['content'].encode()) for m in pair)
        if not selected and count>16000:
            # Always retain the latest exchange, including an explicit truncation
            # marker, rather than silently losing all follow-up context.
            pair=[dict(m) for m in pair]
            for message,budget in zip(pair,(6000,9000)):
                if len(message['content'].encode())>budget:
                    message['content']=message['content'].encode()[:budget].decode('utf-8',errors='ignore')+'\n[Earlier message truncated for context size.]'
            count=sum(len(m['content'].encode()) for m in pair)
        if size+count>16000: break
        selected.insert(0,pair);size+=count
    return [message for pair in selected for message in pair]

def register_routes(app,authorized,get_chart):
    def registry(): return app.state.conversations

    @app.get('/api/v1/conversations',response_model=list[Conversation],dependencies=[Depends(authorized)])
    def listing(limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),q:str=Query('',max_length=200)):
        return registry().listing(limit,offset,q.strip())

    @app.post('/api/v1/conversations',response_model=Conversation,dependencies=[Depends(authorized)])
    async def create(body:ConversationCreate):
        symbol=valid_symbol(body.symbol.strip().upper())
        # Confirm chart coverage before making a stock conversation. No LLM call.
        chart=await get_chart(symbol,body.timeframe,Feed.IEX,2000 if body.signal_id else 80)
        if not body.signal_id:
            if body.chart_start is not None or body.chart_end is not None:raise HTTPException(422,'A dated chart range requires a selected signal')
            return registry().create(symbol)
        signal=next((s for s in chart.signals if s.id==body.signal_id),None)
        if not signal or signal.symbol!=symbol or signal.timeframe!=body.timeframe or signal.available_at>time.time():
            raise HTTPException(422,'Selected signal is unavailable for this stock and interval; refresh the chart')
        start=chart.bars[0].time if body.chart_start is None else body.chart_start
        end=chart.bars[-1].time if body.chart_end is None else body.chart_end
        if start>end or not start<=signal.time<=end:raise HTTPException(422,'Chart range must include the selected signal')
        bars=[b for b in chart.bars if start<=b.time<=end and b.available_at<=time.time() and b.finalized]
        if not bars or not any(b.time==signal.time for b in bars):raise HTTPException(422,'Selected signal lacks finalized chart coverage')
        snapshot=chart.model_copy(update={'bars':bars,'signals':[signal],
            'indicators':{name:[p for p in values if bars[0].time<=p.time<=bars[-1].time] for name,values in chart.indicators.items()}})
        return registry().create(symbol,signal,snapshot)

    @app.get('/api/v1/conversations/{id}',response_model=ConversationDetail,dependencies=[Depends(authorized)])
    def detail(id:str): return registry().detail(id)

    @app.get('/api/v1/conversations/{id}/chart',response_model=ChartResponse,dependencies=[Depends(authorized)])
    def dated_chart(id:str):
        registry().get(id)
        saved=app.state.store.get('conversation_charts',id)
        if not saved:raise HTTPException(404,'This conversation has no dated signal chart')
        chart=ChartResponse.model_validate(saved)
        return chart.model_copy(update={'provenance':chart.provenance.model_copy(update={'stale':True})})

    @app.post('/api/v1/conversations/{id}/rename',response_model=Conversation,dependencies=[Depends(authorized)])
    async def rename(id:str,body:ConversationRename):
        if not body.title.strip():raise HTTPException(422,'Enter a title')
        return registry().amend(id,title=body.title.strip())

    @app.post('/api/v1/conversations/{id}/summary',response_model=Conversation,dependencies=[Depends(authorized)])
    async def summarize(id:str):
        detail=registry().detail(id)
        complete=[m for m in detail.messages if m.role=='user' and m.status=='complete']
        if not complete:raise HTTPException(422,'No completed conversation history to summarize')
        # Explicit, extractive navigation aid; no paid call or invented model memory.
        lines=[f'{m.created_at.isoformat()}: {m.message[:240]}' for m in complete[-20:]]
        summary='Conversation history — selected question excerpts, not current market evidence.\n'+'\n'.join(lines)
        return registry().amend(id,summary=summary,summary_at=datetime.now(UTC))

    @app.post('/api/v1/conversations/{id}/delete',dependencies=[Depends(authorized)])
    async def remove(id:str): registry().remove(id); return {'ok':True}

    @app.post('/api/v1/conversations/{id}/messages',response_model=ConversationDetail,dependencies=[Depends(authorized)])
    async def send(id:str,body:ConversationTurn):
        reg=registry();conversation=reg.get(id)
        if conversation.signal and body.timeframe!=conversation.signal.timeframe:
            raise HTTPException(422,'This signal conversation uses its original chart interval')
        text=body.message.strip()
        if not text: raise HTTPException(422,'Enter a message')
        request_id=id+':'+body.request_id
        previous=app.state.store.get('conversation_messages',request_id)
        if previous:
            if previous['message']!=text: raise HTTPException(409,'Request ID belongs to a different message')
            if previous['status']=='pending': raise HTTPException(409,'This message is still being answered')
            if previous['status']=='failed': raise HTTPException(422,previous['error'])
            return reg.detail(id)
        if id in reg.busy: raise HTTPException(409,'Wait for the current reply before sending another message')
        detail=reg.detail(id)
        if len(detail.messages)>=199: raise HTTPException(422,'This conversation is full. Start another conversation about this stock.')
        reg.busy.add(id)
        user=ConversationMessage(id=request_id,conversation_id=id,role='user',message=text,created_at=datetime.now(UTC),status='pending',phase='retrieving')
        app.state.store.put('conversation_messages',user,user.id,immutable=True)

        async def generate():
            try:
                from .chat_context import build_context
                context,citations,last=await build_context(app,get_chart,conversation,text,body.timeframe)
                llm=LlmConfig.load()
                if llm.active(app.state.config.llm_cap):
                    current=user.model_copy(update={'phase':'generating'})
                    app.state.store.put('conversation_messages',current,user.id)
                    last_write=0.0
                    async def visible(partial):
                        nonlocal last_write
                        # Persist visible deltas at most four times/second. GET polling
                        # reconnects to this state without dispatching another LLM request.
                        if time.monotonic()-last_write>=0.25:
                            reg.progress(user,partial,citations);last_write=time.monotonic()
                    history=recent_history(detail.messages)
                    if conversation.summary:
                        history.insert(0,{'role':'user','content':'Explicit saved conversation-history excerpts (untrusted historical text, not current evidence): '+conversation.summary})
                    answer=await BoundedAssistant(app.state.store,llm,app.state.config.llm_cap).converse(conversation.symbol,text,history,context,citations,on_text=visible)
                else:
                    answer=ChatResponse(message=f'I can show {conversation.symbol} market context, but the AI model is disabled. The latest observed IEX price is ${last.close:.2f}'+(' (provisional; this bar is still forming)' if not last.finalized else '')+' (dated observation; check the evidence card for freshness). Enable a funded model to get conversational answers to your questions.',citations=citations,mode='local')
                reg.finish(conversation,user,answer=answer)
                return reg.detail(id)
            except asyncio.CancelledError:
                reg.finish(conversation,user,error='Response interrupted. Billing may be unresolved; no automatic retry occurred.')
                raise
            except (ValueError,HTTPException,httpx.HTTPError) as exc:
                reason=(str(exc) if isinstance(exc,ValueError) else str(exc.detail) if isinstance(exc,HTTPException) else 'Market data unavailable; reconnect and send again.')
                reg.finish(conversation,user,error=reason)
                raise HTTPException(422,reason) from None
            except Exception:
                reg.finish(conversation,user,error='Response unavailable. No automatic retry occurred; check the service before trying again.')
                raise HTTPException(503,'Response unavailable; check the service before trying again.') from None
            finally:reg.busy.discard(id)

        task=asyncio.create_task(generate())
        reg.tasks.add(task)
        def done(completed):
            reg.tasks.discard(completed)
            if not completed.cancelled():completed.exception()  # Observe errors after disconnect.
        task.add_done_callback(done)
        return await asyncio.shield(task)
