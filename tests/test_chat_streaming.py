import json
import httpx
import pytest
from selery_api.assistant import BoundedAssistant,LlmConfig
from selery_api.storage import Store

def event(kind,**fields):
    return ('event: '+kind+'\ndata: '+json.dumps({'type':kind,**fields})+'\n\n').encode()

def terminal(status='completed'):
    return event('response.'+status,response={'status':status,'output':[{'type':'message','content':[{'type':'output_text','text':'Evidence [one].'}]}],
        'usage':{'input_tokens':100,'output_tokens':50}})

@pytest.mark.asyncio
async def test_stream_only_visible_deltas_and_final_usage():
    store=Store('sqlite:///:memory:');visible=[]
    async def receive(text):visible.append(text)
    def handle(request):
        payload=json.loads(request.content)
        assert payload['stream'] is True and payload['store'] is False and 'tools' not in payload
        body=event('response.reasoning_text.delta',delta='not public')+event('response.output_text.delta',delta='Evidence ')+event('response.output_text.delta',delta='[one].')+terminal()
        return httpx.Response(200,content=body,headers={'content-type':'text/event-stream'})
    result=await BoundedAssistant(store,LlmConfig(key='fixture',enabled=True),5,httpx.MockTransport(handle)).complete('question','test',on_text=receive)
    assert visible==['Evidence ','Evidence [one].']
    assert result[0]=='Evidence [one].' and store.spend()==pytest.approx(.0008)

@pytest.mark.asyncio
@pytest.mark.parametrize('ending',[b'',b'data: [DONE]\n\n',b'data: invalid-json\n\n',event('error',message='private-provider-account')])
async def test_interrupted_stream_preserves_reservation_and_partial_visibility(ending):
    store=Store('sqlite:///:memory:');visible=[]
    async def receive(text):visible.append(text)
    body=event('response.output_text.delta',delta='Partial')+ending
    agent=BoundedAssistant(store,LlmConfig(key='fixture',enabled=True),5,httpx.MockTransport(lambda _:httpx.Response(200,content=body,headers={'content-type':'text/event-stream'})))
    with pytest.raises(ValueError,match='reservation retained') as failure:await agent.complete('question','test',on_text=receive)
    assert 'private-provider-account' not in str(failure.value)
    assert visible==['Partial'] and store.spend()>.09

@pytest.mark.asyncio
async def test_incomplete_stream_settles_known_usage_but_is_not_success():
    store=Store('sqlite:///:memory:')
    async def receive(text):pass
    agent=BoundedAssistant(store,LlmConfig(key='fixture',enabled=True),5,httpx.MockTransport(lambda _:httpx.Response(200,content=terminal('incomplete'),headers={'content-type':'text/event-stream'})))
    with pytest.raises(ValueError,match='did not complete'):await agent.complete('q','test',on_text=receive)
    assert store.spend()==pytest.approx(.0008)
