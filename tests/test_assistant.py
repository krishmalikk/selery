import httpx
import pytest
from selery_api.assistant import BoundedAssistant,LlmConfig
from selery_api.storage import Store

@pytest.mark.asyncio
async def test_zero_cap_never_dispatches():
    calls=[]
    def handler(request):calls.append(request);return httpx.Response(200,json={})
    agent=BoundedAssistant(Store('sqlite:///:memory:'),LlmConfig(key='test-only',enabled=True),0,httpx.MockTransport(handler))
    with pytest.raises(ValueError,match='disabled'):await agent.complete('hello','test')
    assert calls==[]

@pytest.mark.asyncio
async def test_usage_recorded_and_cap_enforced():
    store=Store('sqlite:///:memory:')
    def handler(request):
        assert request.url.host=='api.anthropic.com'
        return httpx.Response(200,json={'content':[{'type':'text','text':'Observed evidence [bar-1].'}],'usage':{'input_tokens':100,'output_tokens':50}})
    agent=BoundedAssistant(store,LlmConfig(key='test-only',enabled=True),0.02,httpx.MockTransport(handler))
    text,cost=await agent.complete('hello','test')
    assert cost==pytest.approx(0.00035) and store.spend()==pytest.approx(cost)
    assert store.list('audit')[0]['detail']['feature']=='test'

@pytest.mark.asyncio
async def test_unknown_response_retains_reservation():
    store=Store('sqlite:///:memory:')
    def handler(request):raise httpx.ReadTimeout('test timeout')
    agent=BoundedAssistant(store,LlmConfig(key='test-only',enabled=True),1,httpx.MockTransport(handler))
    with pytest.raises(ValueError,match='unknown'):await agent.complete('hello','test')
    assert store.spend()>0
