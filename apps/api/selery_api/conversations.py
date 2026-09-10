"""Private stock-scoped threads with durable turns and bounded conversational context."""
import asyncio
import json
from datetime import datetime,timezone
from uuid import uuid4

import httpx
from fastapi import Depends,HTTPException,Query
from sqlalchemy import select,delete,insert,update,func
from selery_shared.models import (Conversation,ConversationCreate,ConversationMessage,
    ConversationDetail,ConversationTurn,Citation,ChatResponse,Timeframe,Feed)
from .assistant import BoundedAssistant,LlmConfig
from .providers import valid_symbol
from .storage import tables,serial

UTC=timezone.utc

class Conversations:
    def __init__(self,store):
        self.store=store
        self.busy=set()  # Single API process, like the existing auth/observer.
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

    def listing(self,limit,offset):
        table=tables['conversations']
        with self.store.engine.connect() as conn:
            rows=conn.execute(select(table.c.payload).order_by(table.c.payload['updated_at'].as_string().desc(),table.c.id).limit(limit).offset(offset))
            return [Conversation.model_validate(row[0]) for row in rows]

    def detail(self,id):
        conversation=self.get(id);table=tables['conversation_messages']
        with self.store.engine.connect() as conn:
            rows=conn.execute(select(table.c.payload).where(table.c.payload['conversation_id'].as_string()==id).order_by(table.c.created_at,table.c.id).limit(200))
            messages=[ConversationMessage.model_validate(row[0]) for row in rows]
        return ConversationDetail(conversation=conversation,messages=messages)

    def create(self,symbol):
        now=datetime.now(UTC)
        item=Conversation(id=uuid4().hex,symbol=symbol,title=f'{symbol} conversation',created_at=now,updated_at=now)
        with self.store.engine.begin() as conn:
            if conn.scalar(select(func.count()).select_from(tables['conversations']))>=500:
                raise HTTPException(422,'Conversation limit reached. Delete an old conversation before creating another.')
            conn.execute(insert(tables['conversations']).values(id=item.id,created_at=now,payload=serial(item)))
        return item

    def remove(self,id):
        self.get(id)
        if id in self.busy: raise HTTPException(409,'Wait for the current reply before deleting this conversation')
        with self.store.engine.begin() as conn:
            conn.execute(delete(tables['conversation_messages']).where(tables['conversation_messages'].c.payload['conversation_id'].as_string()==id))
            conn.execute(delete(tables['conversations']).where(tables['conversations'].c.id==id))

    def finish(self,conversation,user,answer=None,error=None):
        now=datetime.now(UTC)
        user=user.model_copy(update={'status':'failed' if error else 'complete','error':error})
        with self.store.engine.begin() as conn:
            table=tables['conversation_messages']
            conn.execute(update(table).where(table.c.id==user.id).values(payload=serial(user)))
            if answer:
                message=ConversationMessage(id=user.id+':answer',conversation_id=conversation.id,role='assistant',
                    message=answer.message,created_at=now,citations=answer.citations,mode=answer.mode,cost_usd=answer.cost_usd)
                conn.execute(insert(table).values(id=message.id,created_at=now,payload=serial(message)))
            value=conversation.model_copy(update={'updated_at':now})
            conn.execute(update(tables['conversations']).where(tables['conversations'].c.id==conversation.id).values(payload=serial(value)))

def recent_history(messages):
    # Include only complete user/assistant pairs, newest ten pairs, <=16KB.
    # Failed/pending requests are not replayed; old answers remain historical text.
    pairs=[]
    for index in range(len(messages)-1):
        user,answer=messages[index:index+2]
        if user.role=='user' and user.status=='complete' and answer.role=='assistant' and answer.id==user.id+':answer':
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
    def listing(limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
        return registry().listing(limit,offset)

    @app.post('/api/v1/conversations',response_model=Conversation,dependencies=[Depends(authorized)])
    async def create(body:ConversationCreate):
        symbol=valid_symbol(body.symbol.strip().upper())
        # Confirm chart coverage before making a stock conversation. No LLM call.
        await get_chart(symbol,Timeframe.M5,Feed.IEX,80)
        return registry().create(symbol)

    @app.get('/api/v1/conversations/{id}',response_model=ConversationDetail,dependencies=[Depends(authorized)])
    def detail(id:str): return registry().detail(id)

    @app.post('/api/v1/conversations/{id}/delete',dependencies=[Depends(authorized)])
    async def remove(id:str): registry().remove(id); return {'ok':True}

    @app.post('/api/v1/conversations/{id}/messages',response_model=ConversationDetail,dependencies=[Depends(authorized)])
    async def send(id:str,body:ConversationTurn):
        reg=registry();conversation=reg.get(id)
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
        user=ConversationMessage(id=request_id,conversation_id=id,role='user',message=text,created_at=datetime.now(UTC),status='pending')
        try:
            app.state.store.put('conversation_messages',user,user.id,immutable=True)
            chart=await get_chart(conversation.symbol,body.timeframe,Feed.IEX,200)
            last=chart.bars[-1]
            citations=[Citation(label='IEX only reference bar'+(' · provisional' if not last.finalized else ''),
                timestamp=datetime.fromtimestamp(last.available_at,UTC) if last.finalized else chart.provenance.retrieved_at,
                data_id=f'{conversation.symbol}:{body.timeframe.value}:iex:{last.time}')]
            news=[]
            try:
                news=(await app.state.provider.news([conversation.symbol]))[:3]
            except (httpx.HTTPError,ValueError,HTTPException): pass
            citations.extend(Citation(label=n.headline[:240],timestamp=n.published_at,url=n.url,data_id=n.id) for n in news)
            llm=LlmConfig.load()
            if llm.active(app.state.config.llm_cap):
                context={'symbol':conversation.symbol,'timeframe':body.timeframe.value,'provenance':chart.provenance.model_dump(mode='json'),
                    'bars':[b.model_dump(mode='json') for b in chart.bars[-20:]],
                    'indicators':{name:[point.model_dump(mode='json') for point in values[-3:]] for name,values in chart.indicators.items()},
                    'capabilities':[cap.model_dump(mode='json') for cap in chart.capabilities],
                    'limitations':'Only the newest 20 bars and newest Python-calculated indicator points are supplied. Do not invent missing historical or volume-based metrics. Unfinalized bars are provisional.',
                    'latest_signal':chart.signals[-1].model_dump(mode='json') if chart.signals else None,
                    'news':[{'id':n.id,'headline':n.headline[:240],'summary':n.summary[:500],'url':n.url,'published_at':n.published_at.isoformat()} for n in news],
                    'news_available':bool(news),'citations':[c.model_dump(mode='json') for c in citations]}
                answer=await BoundedAssistant(app.state.store,llm,app.state.config.llm_cap).converse(conversation.symbol,text,recent_history(detail.messages),context,citations)
            else:
                answer=ChatResponse(message=f'I can show {conversation.symbol} market context, but the AI model is disabled. The latest observed IEX price is ${last.close:.2f}'+(' (provisional; this bar is still forming)' if not last.finalized else '')+(' (stale).' if chart.provenance.stale else '.')+' Enable a funded model to get conversational answers to your questions.',citations=citations,mode='local')
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
        finally: reg.busy.discard(id)
