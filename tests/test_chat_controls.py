import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from test_conversations import client,create,turn,enable_mock
from test_chat_streaming import event,terminal
from selery_api.conversations import recent_history
from selery_shared.models import ConversationMessage

def test_search_rename_summary_are_private_and_no_paid_call(client):
    id=create(client)
    assert turn(client,id,text='Explain seasonal ambiguity').status_code==200
    response=client.post(f'/api/v1/conversations/{id}/rename',json={'title':'My dated research'})
    assert response.status_code==200
    assert client.get('/api/v1/conversations?q=DATED').json()[0]['id']==id
    assert client.get('/api/v1/conversations?q=seasonal').json()[0]['id']==id
    assert client.get('/api/v1/conversations?q=%25').json()==[]
    assert client.post(f'/api/v1/conversations/{id}/rename',json={'title':'  '}).status_code==422
    summary=client.post(f'/api/v1/conversations/{id}/summary').json()
    assert 'not current market evidence' in summary['summary'] and 'seasonal ambiguity' in summary['summary']
    assert summary['summary_at'] and client.app.state.store.spend()==0
    client.post('/api/v1/auth/logout')
    assert client.get('/api/v1/conversations?q=seasonal').status_code==401

def test_signal_scope_chart_snapshot_and_cascade(client):
    chart=client.get('/api/v1/chart/SPY?limit=2000').json()
    signal=chart['signals'][-1]
    response=client.post('/api/v1/conversations',json={'symbol':'SPY','signal_id':signal['id'],'timeframe':signal['timeframe'],'chart_start':chart['bars'][0]['time'],'chart_end':signal['time']})
    assert response.status_code==200,response.text
    conversation=response.json();id=conversation['id']
    assert conversation['signal']==signal
    saved=client.get(f'/api/v1/conversations/{id}/chart').json()
    assert saved['bars'][-1]['time']==signal['time'] and saved['provenance']['stale']
    assert saved['signals']==[signal]
    assert client.post('/api/v1/conversations',json={'symbol':'QQQ','signal_id':signal['id']}).status_code==422
    assert turn(client,id,signal_id='another').status_code==422
    assert turn(client,id,timeframe='1h').status_code==422
    assert client.post(f'/api/v1/conversations/{id}/delete').status_code==200
    assert client.app.state.store.get('conversation_charts',id) is None

def test_stream_is_recoverable_before_request_completes_and_duplicate_is_blocked(client,monkeypatch):
    ready=threading.Event();release=threading.Event();calls=[]
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield event('response.output_text.delta',delta='Evidence ')
            ready.set()
            await asyncio.to_thread(release.wait,5)
            yield event('response.output_text.delta',delta='[one].')
            yield terminal()
    def handler(request):calls.append(request);return httpx.Response(200,stream=Stream(),headers={'content-type':'text/event-stream'})
    enable_mock(client,monkeypatch,handler)
    id=create(client)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future=executor.submit(turn,client,id)
        try:
            assert ready.wait(5)
            detail=client.get('/api/v1/conversations/'+id).json()
            assert detail['messages'][-1]['message']=='Evidence ' and detail['messages'][-1]['status']=='pending'
            assert detail['messages'][0]['phase']=='generating'
            assert turn(client,id).status_code==409
            assert client.post(f'/api/v1/conversations/{id}/rename',json={'title':'Concurrent'}).status_code==409
        finally:release.set()
        result=future.result(5)
    assert result.status_code==200,result.text
    assert len(result.json()['messages'])==2 and result.json()['messages'][-1]['status']=='complete'
    assert len(calls)==1

def test_partial_failure_does_not_become_history(client,monkeypatch):
    enable_mock(client,monkeypatch,lambda _:httpx.Response(200,content=event('response.output_text.delta',delta='Incomplete'),headers={'content-type':'text/event-stream'}))
    id=create(client)
    assert turn(client,id).status_code==422
    messages=client.get('/api/v1/conversations/'+id).json()['messages']
    assert [m['status'] for m in messages]==['failed','failed']
    assert recent_history([ConversationMessage.model_validate(m) for m in messages])==[]
