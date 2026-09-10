import {test,expect} from '@playwright/test';

test('saved stock conversations work through the real backend proxy',async({page})=>{
  test.skip(process.env.SELERY_PUBLIC_FIXTURE_E2E!=='true','Requires the disposable fixture API');
  const login=await page.request.post('/api/v1/auth/login',{data:{password:'public-fixture-test-password'}});
  expect(login.status()).toBe(200);
  await page.goto('/?view=Assistant');
  await expect(page.getByLabel('Message about SPY',{exact:true})).toHaveCount(0);
  await page.getByLabel('Stock symbol',{exact:true}).fill('SPY');
  await page.getByRole('button',{name:'Start conversation',exact:true}).click();
  const chart=page.getByRole('region',{name:'SPY chart context',exact:true});
  await expect(chart.locator('canvas').first()).toBeVisible();
  await page.getByLabel('Message about SPY',{exact:true}).fill('Show the available price context.');
  await page.getByRole('button',{name:'Send',exact:true}).click();
  await expect(page.locator('.conversation-message.assistant')).toHaveCount(1);
  await page.getByLabel('Message about SPY',{exact:true}).fill('What is unavailable?');
  await page.getByRole('button',{name:'Send',exact:true}).click();
  await expect(page.locator('.conversation-message.assistant')).toHaveCount(2);
  await page.reload();
  await page.getByRole('navigation',{name:'Saved conversations'}).getByRole('button',{name:/SPY/}).first().click();
  await expect(page.locator('.conversation-message.user')).toHaveCount(2);
  await expect(page.locator('.conversation-message.assistant')).toHaveCount(2);
  const threads=await (await page.request.get('/api/v1/conversations')).json();
  const detail=await page.request.get('/api/v1/conversations/'+threads[0].id);
  expect(detail.headers()['cache-control']).toContain('no-store');
  const messages=(await detail.json()).messages;
  expect(messages.every((m:{role:string;mode:string})=>m.role==='user'||m.mode==='local')).toBe(true);
  await page.request.post('/api/v1/conversations/'+threads[0].id+'/delete');
});
