import httpx
import json
import pytest
from selery_api.assistant import BoundedAssistant,LlmConfig
from selery_api.storage import Store

def completed(**overrides):
    return {'status':'completed','output':[{'type':'reasoning','summary':[]},{'type':'message','content':[{'type':'output_text','text':'Observed evidence [bar-1].'}]}],'usage':{'input_tokens':100,'output_tokens':50,'output_tokens_details':{'reasoning_tokens':30}},**overrides}

@pytest.mark.parametrize('name',['OPENAI_API_KEY','OPENAI_KEY','openAI_KEY'])
def test_key_aliases_and_defaults(monkeypatch,name):
    for variable in ('OPENAI_API_KEY','OPENAI_KEY','openAI_KEY','SELERY_LLM_MODEL','SELERY_LLM_REASONING_EFFORT','SELERY_LLM_MAX_OUTPUT_TOKENS','SELERY_LLM_INPUT_USD_PER_MILLION','SELERY_LLM_OUTPUT_USD_PER_MILLION'):
        monkeypatch.delenv(variable,raising=False)
    monkeypatch.setenv(name,'local-test-key')
    config=LlmConfig.load()
    assert config.key=='local-test-key' and config.model=='gpt-5.6-terra'
    assert config.reasoning_effort=='high' and config.max_tokens==8192
    assert 'local-test-key' not in repr(config)

def test_conflicting_aliases_rejected(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','local-test-first')
    monkeypatch.setenv('OPENAI_KEY','local-test-second')
    with pytest.raises(ValueError,match='Conflicting'):LlmConfig.load()

@pytest.mark.parametrize('rate',[float('nan'),float('inf'),0,-1])
def test_invalid_prices_rejected(rate):
    with pytest.raises(ValueError,match='finite'):LlmConfig(input_per_million=rate)

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
        assert str(request.url)=='https://api.openai.com/v1/responses'
        assert request.headers['authorization']=='Bearer test-only'
        body=json.loads(request.content)
        assert body['model']=='gpt-5.6-terra' and body['reasoning']=={'effort':'high'}
        assert body['store'] is False and body['max_output_tokens']==8192
        assert 'tools' not in body and 'Never recommend taking a trade' in body['instructions']
        return httpx.Response(200,json=completed())
    agent=BoundedAssistant(store,LlmConfig(key='test-only',enabled=True),1,httpx.MockTransport(handler))
    text,cost=await agent.complete('hello','test')
    assert text=='Observed evidence [bar-1].'
    assert cost==pytest.approx(0.0008) and store.spend()==pytest.approx(cost)
    assert store.list('audit')[0]['detail']['feature']=='test'

@pytest.mark.asyncio
async def test_unknown_response_retains_reservation():
    store=Store('sqlite:///:memory:')
    def handler(request):raise httpx.ReadTimeout('test timeout')
    agent=BoundedAssistant(store,LlmConfig(key='test-only',enabled=True),1,httpx.MockTransport(handler))
    with pytest.raises(ValueError,match='unknown'):await agent.complete('hello','test')
    assert store.spend()>0

@pytest.mark.asyncio
@pytest.mark.parametrize('block',['cap','kill'])
async def test_budget_and_kill_switch_block_before_dispatch(block):
    store=Store('sqlite:///:memory:');calls=[]
    if block=='kill':store.put('settings',{'reason':'test'},'llm-kill-switch')
    def handler(request):calls.append(request);return httpx.Response(200,json=completed())
    agent=BoundedAssistant(store,LlmConfig(key='test-only',enabled=True),0.001 if block=='cap' else 5,httpx.MockTransport(handler))
    with pytest.raises(ValueError):await agent.complete('hello','test')
    assert not calls and store.spend()==0

@pytest.mark.asyncio
@pytest.mark.parametrize('payload',[completed(status='incomplete',output=[]),completed(output=[])])
async def test_incomplete_or_empty_answers_settle_usage_without_success(payload):
    store=Store('sqlite:///:memory:')
    agent=BoundedAssistant(store,LlmConfig(key='test-only',enabled=True),5,httpx.MockTransport(lambda request:httpx.Response(200,json=payload)))
    with pytest.raises(ValueError,match='reported usage was recorded'):await agent.complete('hello','test')
    assert store.spend()==pytest.approx(0.0008)

@pytest.mark.asyncio
async def test_refusal_is_visible():
    payload=completed(output=[{'type':'message','content':[{'type':'refusal','refusal':'Cannot provide that.'}]}])
    agent=BoundedAssistant(Store('sqlite:///:memory:'),LlmConfig(key='test-only',enabled=True),5,httpx.MockTransport(lambda request:httpx.Response(200,json=payload)))
    assert (await agent.complete('hello','test'))[0]=='Cannot provide that.'

@pytest.mark.asyncio
@pytest.mark.parametrize('usage',[None,{}, {'input_tokens':-1,'output_tokens':50},{'input_tokens':100,'output_tokens':float('inf')}])
async def test_invalid_usage_retains_allowance(usage):
    store=Store('sqlite:///:memory:')
    # JSON cannot encode infinity; use a string to represent invalid provider data.
    if usage and usage.get('output_tokens')==float('inf'):usage['output_tokens']='Infinity'
    agent=BoundedAssistant(store,LlmConfig(key='test-only',enabled=True),5,httpx.MockTransport(lambda request:httpx.Response(200,json=completed(usage=usage))))
    with pytest.raises(ValueError,match='usage unavailable'):await agent.complete('hello','test')
    assert store.spend()>0.09

@pytest.mark.asyncio
async def test_excess_usage_enables_durable_kill_switch():
    store=Store('sqlite:///:memory:')
    payload=completed(usage={'input_tokens':100,'output_tokens':999999})
    agent=BoundedAssistant(store,LlmConfig(key='test-only',enabled=True),5,httpx.MockTransport(lambda request:httpx.Response(200,json=payload)))
    with pytest.raises(ValueError,match='invariant'):await agent.complete('hello','test')
    assert store.get('settings','llm-kill-switch')

@pytest.mark.asyncio
@pytest.mark.parametrize('status',[401,403,404,429,500])
async def test_provider_errors_are_sanitized(status):
    store=Store('sqlite:///:memory:')
    agent=BoundedAssistant(store,LlmConfig(key='test-only',enabled=True),5,httpx.MockTransport(lambda request:httpx.Response(status,json={'error':{'message':'private-provider-details'}})))
    with pytest.raises(ValueError,match=f'HTTP {status}') as error:await agent.complete('hello','test')
    assert 'private-provider-details' not in str(error.value) and store.spend()>0

@pytest.mark.asyncio
@pytest.mark.parametrize('code',['insufficient_quota','credit_balance_exhausted','project_spend_limit_exceeded','organization_spend_limit_exceeded','organization_usage_limit_exceeded','rate_limit_exceeded','slow_down'])
async def test_429_classification_is_safe_and_never_retries(code):
    store=Store('sqlite:///:memory:');calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(429,headers={'retry-after':'30'},json={'error':{'code':code,'type':'insufficient_quota','message':'private-provider-details'}})
    agent=BoundedAssistant(store,LlmConfig(key='test-only',enabled=True),5,httpx.MockTransport(handler))
    with pytest.raises(ValueError) as exc: await agent.complete('hello','test')
    assert code in str(exc.value) and 'private-provider-details' not in str(exc.value)
    assert store.list('audit')[0]['detail']['provider_code']==code
    assert len(calls)==1 and store.spend()>0

@pytest.mark.parametrize('payload',[{'error':{'code':['malformed']}},{'error':'private-details'},[],{'error':{'code':'private-details'}}])
def test_unknown_error_fields_are_not_exposed(payload):
    from selery_api.assistant import provider_error
    code,hint=provider_error(httpx.Response(429,json=payload))
    assert code=='unclassified' and 'private-details' not in hint
