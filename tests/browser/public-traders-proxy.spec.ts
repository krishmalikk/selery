import {test,expect} from '@playwright/test';

// Deliberately separate from mocked browser coverage: requires the isolated
// fixture API with its disposable password and an actual Next proxy.
test.use({baseURL:process.env.SELERY_WEB_TEST_URL || 'http://127.0.0.1:3000'});
test('authenticated public records work through the real Next proxy',async({page,request})=>{
  test.skip(process.env.SELERY_PUBLIC_FIXTURE_E2E!=='true','Run only against the disposable fixture server');
  const forbidden=await request.get('/api/v1/public-traders');
  expect(forbidden.status()).toBe(401);
  const login=await page.request.post('/api/v1/auth/login',{data:{password:'public-fixture-test-password'}});
  expect(login.status()).toBe(200);
  expect((await login.json()).token).toBe('');
  const refresh=await page.request.post('/api/v1/public-traders/refresh',{data:{}});
  expect(refresh.status()).toBe(200);
  await page.goto('/?view=Traders');
  await expect(page.getByText('Ada (synthetic example)',{exact:true})).toBeVisible();
  await expect(page.getByText('Lin (synthetic example)',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Public activity',exact:true}).click();
  await page.getByRole('button',{name:'View record',exact:true}).first().click();
  const detail=page.getByRole('region',{name:'Public activity detail'});
  await expect(detail.getByText('Unavailable; no exit inferred')).toBeVisible();
  await detail.getByRole('button',{name:'Ask about this trade',exact:true}).click();
  await expect(detail.getByText(/SYNTHETIC EXAMPLE/)).toBeVisible();
  await detail.getByRole('button',{name:/Public activity source/}).click();
  await expect(detail.getByRole('region',{name:'Evidence details',exact:true}).getByRole('link',{name:'Open original source',exact:true})).toBeVisible();
  const evidence=await page.request.get('/api/v1/public-traders/activity?limit=1');
  expect(evidence.headers()['cache-control']).toContain('no-store');
  const rows=await evidence.json();expect(rows.total).toBe(3);
  expect((await page.request.get('/api/v1/journal')).status()).toBe(200);
});
