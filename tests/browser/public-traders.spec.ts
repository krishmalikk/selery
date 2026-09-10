import { test, expect, type Page } from '@playwright/test';

test.use({ baseURL: process.env.SELERY_WEB_TEST_URL || 'http://127.0.0.1:3000' });
const observed = '2026-09-09T14:00:00Z';
const sources = ['etoro', 'kinfo', 'afterhour'].map((id, i) => ({ id, name: ['eToro', 'Kinfo', 'AfterHour'][i], status: i ? 'pending' : 'fixtures', reason: i ? 'Authorized access pending.' : 'Synthetic test records only.', can_refresh: false, llm_allowed: false, last_checked_at: observed }));
const trader = { id: 'etoro:sample', source: 'etoro', username: 'sample', display_name: 'Sample researcher', source_url: 'https://www.etoro.com/people/sample', observed_at: observed, stale: true, synthetic: true, access: 'public', statistics: {}, statistics_note: 'No verified statistics.', version: '1' };
const activity = { id: 'etoro:sample:one', trader_id: trader.id, source: 'etoro', source_record_id: 'one', source_url: trader.source_url, symbol: 'SPY', instrument_name: 'SPY', instrument_kind: 'unclassified', direction: 'long', opened_at: observed, published_at: null, provider_updated_at: null, first_observed_at: observed, observed_at: observed, entry_price: 100, allocation_percent: null, quantity: null, exit_price: null, status: 'no_longer_observed', verification: 'Synthetic test record', stale: true, synthetic: true, revision: 1, limitations: ['Disappearance does not establish a sale.'] };
const provenance = { provider: 'fixture', feed: 'iex', observed_at: observed, available_at: observed, retrieved_at: observed, stale: true, synthetic: true, version: '1' };
const chart = { symbol: 'SPY', timeframe: '5m', bars: [], indicators: {}, signals: [], capabilities: [], provenance };

async function mockWorkspace(page: Page) {
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/v1', '');
    let body: unknown;
    if (path === '/settings') body = { data_mode: 'fixtures', feed: 'iex', llm_monthly_cap_usd: 5, llm_spent_usd: 0, llm_enabled: false, disclaimer: 'Selery is research software that displays analysis. It does not execute, recommend, or place trades.' };
    else if (path === '/watchlist') body = { quotes: [], data_mode: 'fixtures' };
    else if (path.startsWith('/chart/')) body = chart;
    else if (path === '/news') body = { items: [], retrieved_at: observed, stale: true };
    else if (path === '/public-traders/sources') body = sources;
    else if (path === '/public-traders') {
      const filtered = url.searchParams.get('source') === 'kinfo' || url.searchParams.get('q') === 'missing';
      body = { items: filtered ? [] : [trader], total: filtered ? 0 : 1, limit: 12, offset: 0 };
    } else if (path === '/public-traders/activity') body = { items: [activity], total: 1, limit: 12, offset: 0 };
    else if (path.startsWith('/public-traders/activity/')) body = { activity, trader, chart, market_context_reason: 'IEX context does not represent the public trader’s performance.', reference_move_percent: null, llm_allowed: false };
    else if (path === '/chat') body = { message: 'Local evidence: no sale or motive can be inferred.', citations: [{ label: 'Public source record', timestamp: observed, url: trader.source_url, data_id: activity.id }], mode: 'local', cost_usd: 0 };
    else return route.fulfill({ status: 404, json: { detail: 'Unexpected test route' } });
    await route.fulfill({ json: body });
  });
  await page.goto('/?view=Traders');
  await expect(page.getByRole('heading', { name: 'Traders', exact: true })).toBeVisible();
}

test('public directory shows source limitations and filters without provider access', async ({ page }) => {
  await mockWorkspace(page);
  await expect(page.getByText('Sample researcher', { exact: true })).toBeVisible();
  await expect(page.getByText('Authorized access pending.')).toHaveCount(2);
  await expect(page.getByRole('button', { name: 'Load / refresh directory page' })).toBeDisabled();
  await page.getByLabel('Source', { exact: true }).selectOption('kinfo');
  await expect(page.getByText(/No public records match these filters/)).toBeVisible();
  await expect(page.getByText('Sample researcher', { exact: true })).toHaveCount(0);
  await page.getByLabel('Source', { exact: true }).selectOption('');
  await page.getByLabel('Search public traders').fill('missing');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText(/No public records match these filters/)).toBeVisible();
});

test('public record preserves unknown exits and sends activity-linked local questions', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await mockWorkspace(page);
  await page.getByRole('button', { name: 'View activity', exact: true }).click();
  await page.getByRole('button', { name: 'View record', exact: true }).click();
  const detail = page.getByRole('region', { name: 'Public activity detail' });
  await expect(detail.getByText('Unavailable; no exit inferred')).toBeVisible();
  await expect(detail.getByText('unclassified', { exact: true })).toBeVisible();
  await expect(detail.getByText('Stale observation', { exact: true })).toBeVisible();
  await expect(detail.getByText(/source data will not be sent to OpenAI/)).toBeVisible();
  await expect(detail.getByText('IEX context does not represent the public trader’s performance.')).toBeVisible();
  await expect(detail.getByRole('link', { name: 'Charts by TradingView' })).toBeVisible();
  const request = page.waitForRequest(r => r.url().endsWith('/api/v1/chat'));
  await detail.getByRole('button', { name: 'Ask about this trade' }).click();
  expect((await request).postDataJSON()).toMatchObject({ activity_id: activity.id, symbol: 'SPY', debate: false });
  await expect(detail.getByText('Local evidence: no sale or motive can be inferred.')).toBeVisible();
  await expect(detail.getByRole('link', { name: 'Public source record' })).toHaveAttribute('href', trader.source_url);
  expect(errors).toEqual([]);
});

test('directory pagination and opening-date filters send explicit server queries', async ({ page }) => {
  await mockWorkspace(page);
  await page.route('**/api/v1/public-traders?*', async route => {
    const offset = Number(new URL(route.request().url()).searchParams.get('offset') || 0);
    await route.fulfill({ json: { items: [ { ...trader, id: `etoro:page-${offset}`, display_name: `Researcher page ${offset}` } ], total: 13, limit: 12, offset } });
  });
  await page.reload();
  await expect(page.getByText('Researcher page 0', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(page.getByText('Researcher page 12', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next page', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Previous page', exact: true }).click();
  await expect(page.getByText('Researcher page 0', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Public activity', exact: true }).click();
  const filtered = page.waitForRequest(request => request.url().includes('date_from=2026-09-01'));
  await page.getByLabel('Opened from (UTC)').fill('2026-09-01');
  expect(new URL((await filtered).url()).searchParams.get('offset')).toBe('0');
});

async function showDetail(page: Page) {
  await page.getByRole('button', { name: 'View activity', exact: true }).click();
  await page.getByRole('button', { name: 'View record', exact: true }).click();
  await expect(page.getByText('Unavailable; no exit inferred')).toBeVisible();
}

async function visibility(page: Page, state: 'visible' | 'hidden') {
  await page.evaluate(value => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, value });
    document.dispatchEvent(new Event('visibilitychange'));
  }, state);
}

test('backgrounding clears public evidence and ignores a late answer before revalidation', async ({ page }) => {
  await mockWorkspace(page);
  await showDetail(page);
  let complete!: () => void;
  const release = new Promise<void>(resolve => { complete = resolve; });
  await page.route('**/api/v1/chat', async route => {
    await release;
    await route.fulfill({ json: { message: 'Late private evidence', citations: [], mode: 'local', cost_usd: 0 } });
  });
  const requested = page.waitForRequest(request => request.url().endsWith('/api/v1/chat'));
  await page.getByRole('button', { name: 'Ask about this trade' }).click();
  await requested;
  await visibility(page, 'hidden');
  await expect(page.getByText('Unavailable; no exit inferred')).toHaveCount(0);
  const completed = page.waitForResponse(response => response.url().endsWith('/api/v1/chat'));
  complete(); await completed;
  await expect(page.getByText('Late private evidence')).toHaveCount(0);
  await page.route('**/api/v1/public-traders/activity/*', route => route.fulfill({ status: 404, json: { detail: 'Public access withdrawn' } }));
  await visibility(page, 'visible');
  await expect(page.getByText('Public access withdrawn', { exact: true })).toBeVisible();
  await expect(page.getByText('Late private evidence')).toHaveCount(0);
});

test('snapshot-only polling preserves a question and answer until the record revision changes', async ({ page }) => {
  await page.clock.install();
  await mockWorkspace(page);
  await showDetail(page);
  let recordRevision = 1;
  let complete!: () => void;
  const release = new Promise<void>(resolve => { complete = resolve; });
  await page.route('**/api/v1/chat', async route => {
    await release;
    await route.fulfill({ json: { message: 'Preserved evidence response', citations: [], mode: 'local', cost_usd: 0 } });
  });
  await page.route('**/api/v1/public-traders/activity/*', route => route.fulfill({ json: { activity: { ...activity, revision: recordRevision }, trader, chart: null, market_context_reason: 'Snapshot only', reference_move_percent: null, llm_allowed: false } }));
  const providerRefresh: string[] = [];
  page.on('request', request => { if (request.url().includes('/public-traders/refresh')) providerRefresh.push(request.url()); });
  const requested = page.waitForRequest(request => request.url().endsWith('/api/v1/chat'));
  await page.getByRole('button', { name: 'Ask about this trade' }).click();
  await requested;
  const polled = page.waitForResponse(response => response.url().includes('include_chart=false'));
  await page.clock.fastForward(60_000); await polled;
  await expect(page.getByRole('button', { name: 'Reviewing evidence…' })).toBeDisabled();
  complete();
  await expect(page.getByText('Preserved evidence response', { exact: true })).toBeVisible();
  const unchanged = page.waitForResponse(response => response.url().includes('include_chart=false'));
  await page.clock.fastForward(60_000); await unchanged;
  await expect(page.getByText('Preserved evidence response', { exact: true })).toBeVisible();
  recordRevision = 2;
  const changed = page.waitForResponse(response => response.url().includes('include_chart=false'));
  await page.clock.fastForward(60_000); await changed;
  await expect(page.getByText('Preserved evidence response')).toHaveCount(0);
  expect(providerRefresh).toEqual([]);
});
