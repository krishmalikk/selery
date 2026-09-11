import {test,expect,type Page} from '@playwright/test';

async function setup(page:Page,confidence:number|null=null) {
  let passkeys:'old'|'disabled'|'ready'|'expired'='old', listings=0;
  const stamp='2026-09-09T15:00:00Z';
  await page.route('**/api/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname.replace('/api/v1','');
    const json=(body:unknown,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
    if(path==='/settings')return json({data_mode:'fixtures',feed:'iex',llm_monthly_cap_usd:5,llm_spent_usd:0,llm_enabled:false,disclaimer:'Research fixture'});
    if(path==='/auth/passkeys/status')return passkeys==='old'?json({detail:'Not Found'},404):json({enabled:passkeys!=='disabled',registered:false,reason:passkeys==='disabled'?'Passkey sign-in is not configured for this website yet.':null});
    if(path==='/auth/passkeys'){listings++;return passkeys==='expired'?json({detail:'Session expired'},401):json([]);}
    if(path==='/models')return json({status:'untrained',reason:'No validated model is promoted.',registry:[]});
    if(path==='/watchlist')return json({quotes:[],data_mode:'fixtures'});
    if(path==='/news')return json({items:[],retrieved_at:stamp,stale:true});
    if(path.startsWith('/chart/'))return json({symbol:'SPY',timeframe:'5m',bars:[{symbol:'SPY',time:1788966000,available_at:1788966300,open:100,high:102,low:99,close:101,volume:100,feed:'iex',finalized:true}],signals:[{id:'fixture-signal',symbol:'SPY',strategy:'ema_cross',strategy_version:'1',timeframe:'5m',time:1788966000,available_at:1788966300,direction:'bullish',reference_price:101,stop:99,target:104,horizon_bars:20,confidence,confidence_reason:confidence===null?'No calibrated prediction recorded.':null,feed:'iex',features:{},explanation:'Synthetic research signal'}],indicators:{},capabilities:[],provenance:{provider:'fixture',feed:'iex',observed_at:stamp,available_at:stamp,retrieved_at:stamp,stale:true,synthetic:true,version:'1'}});
    return json([]);
  });
  return {mode:(value:typeof passkeys)=>{passkeys=value;},listings:()=>listings};
}

test('old passkey backend ends loading and supports retry after deployment',async({page})=>{
  const state=await setup(page);
  await page.goto('/?view=Settings');
  await expect(page.getByRole('alert').filter({hasText:'has not been updated for passkeys'})).toBeVisible();
  await expect(page.getByText('Loading passkey settings…')).toHaveCount(0);
  state.mode('ready');await page.getByRole('button',{name:'Retry passkey settings'}).click();
  await expect(page.getByLabel('Passkey name',{exact:true})).toBeVisible();
  await expect(page.getByRole('alert').filter({hasText:'has not been updated for passkeys'})).toHaveCount(0);
});

test('disabled passkeys skip credential listing and model status explains absent confidence',async({page})=>{
  const state=await setup(page);state.mode('disabled');
  await page.goto('/?view=Settings');
  await expect(page.getByText('Passkey sign-in is not configured for this website yet.')).toBeVisible();
  await expect(page.getByText('Loading passkey settings…')).toHaveCount(0);
  expect(state.listings()).toBe(0);
  await expect(page.getByText(/No validated model is active/)).toBeVisible();
});

test('expired passkey-list session produces recovery guidance without an endless loader',async({page})=>{
  const state=await setup(page);state.mode('expired');
  await page.goto('/?view=Settings');
  await expect(page.getByRole('alert').filter({hasText:'Your session expired'})).toBeVisible();
  await expect(page.getByText('Loading passkey settings…')).toHaveCount(0);
});

for(const confidence of [null,0,.73])test(`signal confidence preserves ${confidence===null?'unavailable':confidence}`,async({page})=>{
  await setup(page,confidence);await page.goto('/');
  const label=confidence===null?'Unavailable':`${(confidence*100).toFixed(1)}%`;
  await expect(page.getByRole('cell').filter({has:page.getByText(label,{exact:true})})).toBeVisible();
  await expect(page.getByText(/Confidence is unavailable for these signals/)).toHaveCount(confidence===null?1:0);
});
