import {test} from 'node:test';
import assert from 'node:assert/strict';
import {SeleryClient} from '../packages/shared/src/client';

test('staggered backend rollout preserves old chats with explicit unavailable metadata',async()=>{
  const previous=globalThis.fetch;
  const conversation={id:'legacy',symbol:'SPY',title:'Old thread',created_at:'2026-09-09T12:00:00Z',updated_at:'2026-09-09T12:00:00Z'};
  const citation={label:'Old bar',timestamp:conversation.created_at,url:null,data_id:'old-bar'};
  let payload:unknown={conversation,messages:[{id:'answer',conversation_id:'legacy',role:'assistant',message:'Saved answer [old-bar]',created_at:conversation.created_at,status:'complete',error:null,citations:[citation],mode:'llm',cost_usd:.001}]};
  globalThis.fetch=async()=>new Response(JSON.stringify(payload),{status:200});
  try {
    const client=new SeleryClient('https://fixture.invalid');
    const result=await client.conversation('legacy');
    assert.equal(result.conversation.signal,null);assert.equal(result.messages[0].phase,null);
    assert.equal(result.messages[0].citations[0].observation,null);
    payload=[{...conversation,signal:null,unexpected:'must reject'}];
    await assert.rejects(()=>client.conversations());
    payload={conversation:{...conversation,signal:{invalid:'not a signal'}},messages:[]};
    await assert.rejects(()=>client.conversation('legacy'));
  } finally {globalThis.fetch=previous;}
});
