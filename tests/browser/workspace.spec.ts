import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
const password=process.env.SELERY_PASSWORD||readFileSync('.env','utf8').split('\n').find(l=>l.startsWith('SELERY_PASSWORD='))?.split('=').slice(1).join('=')||'';
test.beforeEach(async({page})=>{await page.goto('/');await page.getByLabel('Workspace password').fill(password);await page.getByRole('button',{name:'Open workspace'}).click();await expect(page.getByRole('heading',{name:'Signal context'})).toBeVisible();});
test('watchlist chart and feed limitations render without browser errors',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await expect(page.locator('canvas').first()).toBeVisible();
 await expect(page.getByText('IEX only').first()).toBeVisible();
 await expect(page.getByRole('button',{name:/VWAP/})).toBeDisabled();
 await page.screenshot({path:'docs/web-desktop.png',fullPage:true});
 expect(errors).toEqual([]);
});
test('keyboard command palette changes view',async({page})=>{
 await page.keyboard.press('Control+k');await expect(page.getByRole('dialog')).toBeVisible();
 await page.getByRole('dialog').getByRole('button',{name:'Research',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Historical event study'})).toBeVisible();
 await page.getByRole('button',{name:'Run event study'}).click();
 await expect(page.getByRole('heading',{name:'Assumptions'})).toBeVisible();
});
test('informational sizing uses backend limits',async({page})=>{
 await page.getByRole('button',{name:'Sizing',exact:true}).click();
 await page.getByLabel('Research capital ($)').fill('10000');await page.getByLabel('Risk budget (%)').fill('1');
 await page.getByLabel('Reference price ($)').fill('100');await page.getByLabel('Analytical stop level ($)').fill('95');await page.getByLabel('Maximum allocation (%)').fill('20');
 await page.getByRole('button',{name:'Calculate research size'}).click();
 await expect(page.getByText('Informational calculation only; no action is taken.')).toBeVisible();
 await expect(page.getByRole('heading',{name:'Analytical size'})).toBeVisible();
});
