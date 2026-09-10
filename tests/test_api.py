from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from selery_api.config import Config
from selery_api.main import create_app
from selery_api.storage import Store
from selery_api.outcomes import score_signal
from selery_shared.models import Signal,Bar,Feed,Timeframe

@pytest.fixture
def client():
    config=Config('https://paper-api.alpaca.markets','','','local-test-password','s'*48,'fixtures','sqlite:///:memory:',('http://localhost:3000',),0)
    with TestClient(create_app(config)) as client:yield client

def login(client):
    result=client.post('/api/v1/auth/login',json={'password':'local-test-password'})
    assert result.status_code==200
    return result.json()['token']

def test_auth_and_contracts(client):
    assert client.get('/api/v1/watchlist').status_code==401
    token=login(client)
    response=client.get('/api/v1/watchlist')
    assert response.status_code==200
    assert len(response.json()['quotes'])==4
    assert all(q['provenance']['stale'] for q in response.json()['quotes'])
    chart=client.get('/api/v1/chart/SPY').json()
    assert 'ema9' in chart['indicators'] and 'vwap' not in chart['indicators']
    assert all(not c['enabled'] for c in chart['capabilities'])
    assert all(s['confidence'] is None for s in chart['signals'])
    assert client.post('/api/v1/auth/logout').status_code==200
    assert client.get('/api/v1/watchlist',headers={'Authorization':'Bearer '+token}).status_code==401

def test_journal_only_explicit_save(client):
    login(client)
    client.get('/api/v1/chart/SPY')
    client.post('/api/v1/research',json={'symbol':'SPY','timeframe':'1D'})
    assert client.get('/api/v1/journal').json()==[]
    saved=client.post('/api/v1/journal',json={'symbol':'SPY','thesis':'Manual research note'})
    assert saved.status_code==200 and saved.json()['id']
    assert len(client.get('/api/v1/journal').json())==1

def test_sizing_and_research(client):
    login(client)
    result=client.post('/api/v1/research/size',json={'research_capital':10000,'risk_percent':1,'reference_price':100,'stop':95,'max_allocation_percent':20})
    assert result.json()['units']==20 and result.json()['analytical_risk']==100
    study=client.post('/api/v1/research',json={'symbol':'SPY','timeframe':'1D'})
    assert study.status_code==200,study.text
    assert study.json()['metrics']['sharpe'] is None
    assert client.get('/api/v1/research/'+study.json()['id']).status_code==200

def test_budget_cap_is_atomic_and_disabled_by_default():
    store=Store('sqlite:///:memory:')
    assert not store.reserve(1,0)
    assert store.reserve(2,3)
    assert not store.reserve(2,3)
    store.settle(2,1)
    assert store.spend()==1
    assert store.reserve(2,3)

@pytest.mark.parametrize('debate',[False,True])
def test_openai_chat_contract_and_manual_perspectives(client,monkeypatch,debate):
    import json
    import httpx
    from dataclasses import replace
    from selery_api.assistant import LlmConfig
    client.app.state.config=replace(client.app.state.config,llm_cap=5)
    monkeypatch.setattr(LlmConfig,'load',classmethod(lambda cls:LlmConfig(key='local-test-key',enabled=True)))
    requests=[]
    def handler(request):
        requests.append(request)
        assert str(request.url)=='https://api.openai.com/v1/responses'
        assert json.loads(request.content)['reasoning']=={'effort':'high'}
        return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'Research evidence only.'}]}],'usage':{'input_tokens':100,'output_tokens':50}})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(**{**kwargs,'transport':httpx.MockTransport(handler)}))
    login(client)
    assert client.get('/api/v1/settings').json()['llm_enabled'] is True
    response=client.post('/api/v1/chat',json={'symbol':'SPY','message':'Explain available observations.','debate':debate})
    assert response.status_code==200,response.text
    payload=response.json()
    assert payload['mode']=='llm' and payload['citations'] and payload['message']
    assert len(requests)==(5 if debate else 1)
    assert payload['cost_usd']==pytest.approx(0.0008*len(requests))
    assert client.get('/api/v1/journal').json()==[]

def test_signal_snapshot_immutable():
    store=Store('sqlite:///:memory:')
    store.put('signals',{'reference_price':100},'one',immutable=True)
    store.put('signals',{'reference_price':200},'one',immutable=True)
    assert store.get('signals','one')['reference_price']==100

def test_both_thresholds_are_ambiguous_and_pre_signal_data_ignored():
    signal=Signal(id='one',symbol='SPY',strategy='test',timeframe=Timeframe.M5,time=0,available_at=300,direction='bullish',reference_price=100,stop=95,target=110,feed=Feed.IEX,explanation='test',horizon_bars=2)
    bar=Bar(symbol='SPY',time=300,available_at=600,open=100,high=111,low=94,close=101,feed=Feed.IEX)
    assert score_signal(signal,[bar]).status=='ambiguous'
    earlier=bar.model_copy(update={'time':0,'available_at':300})
    assert score_signal(signal,[earlier]).status=='pending'

def test_origin_rejected_for_cookie_mutation(client):
    login(client)
    assert client.post('/api/v1/research/size',json={'research_capital':1000,'risk_percent':1,'reference_price':100,'stop':90},headers={'Origin':'https://untrusted.example'}).status_code==403

def test_stream_ticket_single_use(client):
    login(client)
    ticket=client.post('/api/v1/auth/stream-ticket').json()['ticket']
    assert client.app.state.auth.consume_ticket(ticket)
    assert not client.app.state.auth.consume_ticket(ticket)

def test_stream_ticket_rejected_after_logout_and_open_stream_revoked(client):
    from starlette.websockets import WebSocketDisconnect
    login(client)
    ticket=client.post('/api/v1/auth/stream-ticket').json()['ticket']
    unused=client.post('/api/v1/auth/stream-ticket').json()['ticket']
    with client.websocket_connect('/api/v1/stream?ticket='+ticket) as stream:
        client.post('/api/v1/auth/logout')
        assert not client.app.state.auth.consume_ticket(unused)
        async def publish():
            for queue in client.app.state.subscribers:queue.put_nowait({'type':'heartbeat'})
        client.portal.call(publish)
        with pytest.raises(WebSocketDisconnect) as closed:stream.receive_json()
        assert closed.value.code==4401

def test_forward_cohorts_keep_symbols_separate(client):
    login(client)
    from selery_shared.models import Outcome
    for symbol,status in [('SPY','target_first'),('QQQ','stop_first')]:
        signal=Signal(id=symbol,symbol=symbol,strategy='test',timeframe=Timeframe.M5,time=0,available_at=300,direction='bullish',reference_price=100,stop=95,target=110,feed=Feed.IEX,explanation='test')
        client.app.state.store.put('signals',signal,signal.id,immutable=True)
        client.app.state.store.put('outcomes',Outcome(signal_id=signal.id,status=status,evaluated_at=datetime.now(timezone.utc),bars_observed=1),signal.id)
    cohorts=client.get('/api/v1/outcomes').json()
    assert len(cohorts)==2
    assert sorted(c['hit_rate'] for c in cohorts)==[0,1]
