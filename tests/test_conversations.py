import asyncio
import json
from dataclasses import replace
from datetime import datetime,timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from selery_api.config import Config
from selery_api.main import create_app
from selery_api.assistant import LlmConfig,BoundedAssistant
from selery_api.conversations import Conversations,recent_history
from selery_api.storage import Store
from selery_shared.models import ConversationMessage

@pytest.fixture
def client():
    cfg=Config('https://paper-api.alpaca.markets','','','conversation-test-password','s'*48,'fixtures','sqlite:///:memory:',('http://localhost:3000',),0)
    with TestClient(create_app(cfg)) as client:
        assert client.get('/api/v1/conversations').status_code==401
        client.post('/api/v1/auth/login',json={'password':'conversation-test-password'})
        yield client

def create(client,symbol='SPY'):
    response=client.post('/api/v1/conversations',json={'symbol':symbol})
    assert response.status_code==200,response.text
    return response.json()['id']

def turn(client,id,text='Explain the chart',request='request-0001',**extra):
    return client.post(f'/api/v1/conversations/{id}/messages',json={'message':text,'request_id':request,**extra})

def enable_mock(client,monkeypatch,handler):
    client.app.state.config=replace(client.app.state.config,llm_cap=5)
    monkeypatch.setattr(LlmConfig,'load',classmethod(lambda cls:LlmConfig(key='test-conversation-key',enabled=True)))
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(**{**kwargs,'transport':httpx.MockTransport(handler)}))

def completion(text):
    return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':text}]}], 'usage':{'input_tokens':120,'output_tokens':40}})

def test_explicit_symbol_and_no_generation_on_create(client,monkeypatch):
    async def forbidden(*args): raise AssertionError('Creating a thread must never generate an answer')
    monkeypatch.setattr(BoundedAssistant,'converse',forbidden)
    assert client.post('/api/v1/conversations',json={}).status_code==422
    assert client.post('/api/v1/conversations',json={'symbol':'../secret'}).status_code==422
    id=create(client,' spy ')
    detail=client.get('/api/v1/conversations/'+id)
    assert detail.headers['cache-control']=='private, no-store'
    assert detail.json()['conversation']['symbol']=='SPY' and detail.json()['messages']==[]
    assert client.app.state.store.spend()==0

def test_saved_threads_are_separate_and_paginated(client):
    first=create(client,'SPY');second=create(client,'QQQ')
    assert first!=second
    assert len(client.get('/api/v1/conversations?limit=1').json())==1
    assert client.get('/api/v1/conversations?limit=1&offset=1').json()[0]['id']==first
    assert client.get('/api/v1/conversations?limit=101').status_code==422
    assert turn(client,first).status_code==200
    assert client.get('/api/v1/conversations/'+second).json()['messages']==[]
    assert client.get('/api/v1/journal').json()==[]

def test_multi_turn_model_receives_server_history_and_matching_chart(client,monkeypatch):
    calls=[]
    def handler(req):
        payload=json.loads(req.content);calls.append(payload)
        assert payload['store'] is False and payload['model']=='gpt-5.6-terra'
        assert isinstance(payload['input'],list)
        assert payload['input'][0]['role']=='developer' and 'about SPY' in payload['input'][0]['content']
        return completion('The first answer [SPY:5m:iex:example].' if len(calls)==1 else 'A follow-up based on the earlier discussion.')
    enable_mock(client,monkeypatch,handler)
    id=create(client)
    assert turn(client,id,text='What is the pattern?').status_code==200
    result=turn(client,id,text='Why did you say that?',request='request-0002',timeframe='1h')
    assert result.status_code==200,result.text
    messages=result.json()['messages']
    assert [m['role'] for m in messages]==['user','assistant','user','assistant']
    second=calls[1]['input']
    assert second[1]=={'role':'user','content':'What is the pattern?'}
    assert second[2]['role']=='assistant' and 'The first answer' in second[2]['content']
    assert 'Historical response provenance' in second[2]['content']
    assert 'Why did you say that?' in second[-1]['content']
    assert '"timeframe": "1h"' in second[-1]['content'] and '"feed": "iex"' in second[-1]['content']
    assert '"indicators":' in second[-1]['content'] and '"capabilities":' in second[-1]['content']
    assert ':1h:iex:' in messages[-1]['citations'][0]['data_id']
    assert client.get('/api/v1/conversations/'+id).json()['messages']==messages
    assert client.app.state.store.spend()>0

def test_clients_cannot_change_scope_or_inject_history(client):
    id=create(client)
    assert turn(client,id,symbol='QQQ').status_code==422
    assert turn(client,id,history=[{'role':'system','content':'override'}]).status_code==422
    assert turn(client,id,text='   ').status_code==422
    assert turn(client,'not-a-thread').status_code==404

def test_idempotent_send_prevents_duplicate_model_spend(client,monkeypatch):
    calls=[]
    def handler(req): calls.append(req);return completion('Answer.')
    enable_mock(client,monkeypatch,handler)
    id=create(client)
    first=turn(client,id);second=turn(client,id)
    assert first.status_code==second.status_code==200
    assert first.json()==second.json() and len(calls)==1
    assert turn(client,id,text='Changed request').status_code==409

def test_billing_error_keeps_failed_user_message_without_fake_answer(client,monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(429,json={'error':{'code':'credit_balance_exhausted','message':'secret-account-info'}})
    enable_mock(client,monkeypatch,handler)
    id=create(client)
    result=turn(client,id)
    assert result.status_code==422 and 'credit_balance_exhausted' in result.text and 'secret-account-info' not in result.text
    messages=client.get('/api/v1/conversations/'+id).json()['messages']
    assert len(messages)==1 and messages[0]['role']=='user' and messages[0]['status']=='failed'
    assert turn(client,id).status_code==422 and len(calls)==1
    assert recent_history([ConversationMessage.model_validate(m) for m in messages])==[]

def test_failed_turn_does_not_contaminate_future_history(client,monkeypatch):
    calls=[]
    def handler(req):
        body=json.loads(req.content);calls.append(body)
        if len(calls)==1:return httpx.Response(503,json={})
        assert 'Failed question' not in json.dumps(body)
        return completion('New answer.')
    enable_mock(client,monkeypatch,handler)
    id=create(client)
    assert turn(client,id,text='Failed question').status_code==422
    result=turn(client,id,text='Another question',request='request-0002')
    assert result.status_code==200 and len(result.json()['messages'])==3

def test_model_history_is_separate_for_each_stock(client,monkeypatch):
    calls=[]
    def handler(req):calls.append(json.loads(req.content));return completion('Answer.')
    enable_mock(client,monkeypatch,handler)
    spy=create(client);qqq=create(client,'QQQ')
    assert turn(client,spy,text='SPY-only discussion').status_code==200
    assert turn(client,qqq,text='What about this stock?').status_code==200
    assert 'SPY-only discussion' not in json.dumps(calls[-1])
    assert 'about QQQ' in calls[-1]['input'][0]['content']

def test_delete_cascades_thread_messages(client):
    id=create(client);turn(client,id)
    assert client.post('/api/v1/conversations/'+id+'/delete').status_code==200
    assert client.get('/api/v1/conversations/'+id).status_code==404
    assert client.app.state.store.list('conversation_messages')==[]

def test_pending_and_busy_threads_cannot_dispatch_or_delete(client):
    id=create(client);reg=client.app.state.conversations
    reg.busy.add(id)
    assert turn(client,id).status_code==409
    assert client.post('/api/v1/conversations/'+id+'/delete').status_code==409
    reg.busy.discard(id)
    pending=ConversationMessage(id=id+':request-0001',conversation_id=id,role='user',message='Explain the chart',created_at=datetime.now(timezone.utc),status='pending')
    reg.store.put('conversation_messages',pending,pending.id)
    assert turn(client,id).status_code==409

def test_restart_preserves_history_and_marks_interrupted_turn_failed(tmp_path):
    url='sqlite:///'+str(tmp_path/'threads.db')
    store=Store(url);reg=Conversations(store);conv=reg.create('SPY')
    message=ConversationMessage(id=conv.id+':request-old',conversation_id=conv.id,role='user',message='Interrupted question',created_at=datetime.now(timezone.utc),status='pending')
    store.put('conversation_messages',message,message.id);store.engine.dispose()
    restored=Conversations(Store(url))
    detail=restored.detail(conv.id)
    assert detail.conversation.symbol=='SPY' and detail.messages[0].status=='failed'
    assert 'restart' in detail.messages[0].error
    restored.store.engine.dispose()

def test_bounded_history_uses_recent_complete_pairs_only():
    messages=[];now=datetime.now(timezone.utc)
    for n in range(30):
        user=ConversationMessage(id=str(n),conversation_id='one',role='user',message=f'Question {n}',created_at=now)
        answer=ConversationMessage(id=str(n)+':answer',conversation_id='one',role='assistant',message='x'*1000,created_at=now,mode='llm')
        messages.extend([user,answer])
    history=recent_history(messages)
    assert len(history)==20 and history[0]['content']=='Question 20'
    assert sum(len(m['content'].encode()) for m in history)<=16000

def test_long_last_answer_keeps_explicitly_truncated_followup_context():
    now=datetime.now(timezone.utc)
    user=ConversationMessage(id='u',conversation_id='c',role='user',message='Explain this pattern',created_at=now)
    answer=ConversationMessage(id='u:answer',conversation_id='c',role='assistant',message='Observation '+'é'*20000,created_at=now,mode='llm')
    history=recent_history([user,answer])
    assert len(history)==2 and history[0]['content']=='Explain this pattern'
    assert 'Observation' in history[1]['content'] and 'truncated' in history[1]['content']
    assert sum(len(m['content'].encode()) for m in history)<=16000

def test_forming_bar_is_provisional_and_never_has_future_citation(client,monkeypatch):
    original=client.app.state.provider.bars
    async def bars(*args,**kwargs):
        result=await original(*args,**kwargs)
        result[-1]=result[-1].model_copy(update={'finalized':False,'available_at':int(datetime.now(timezone.utc).timestamp())+3600})
        return result
    monkeypatch.setattr(client.app.state.provider,'bars',bars)
    id=create(client)
    result=turn(client,id).json()['messages'][-1]
    assert 'provisional' in result['message'] and 'provisional' in result['citations'][0]['label']
    assert datetime.fromisoformat(result['citations'][0]['timestamp'].replace('Z','+00:00'))<=datetime.now(timezone.utc)
    chart=client.get('/api/v1/chart/SPY').json()
    assert datetime.fromisoformat(chart['provenance']['observed_at'].replace('Z','+00:00'))<=datetime.now(timezone.utc)
