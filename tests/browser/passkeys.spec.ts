import {test, expect} from '@playwright/test';

test('web passkey enrollment, signed login, cancel and password recovery through the real proxy', async ({page, context}) => {
  test.skip(process.env.SELERY_PASSKEY_E2E !== 'true', 'Requires a disposable fixture backend with the browser origin configured');
  const cdp = await context.newCDPSession(page);
  await cdp.send('WebAuthn.enable');
  const {authenticatorId} = await cdp.send('WebAuthn.addVirtualAuthenticator', {options: {
    protocol: 'ctap2', transport: 'internal', hasResidentKey: true, hasUserVerification: true,
    isUserVerified: true, automaticPresenceSimulation: true,
  }});
  try {
    await page.goto('/?view=Settings');
    await expect(page.getByRole('heading', {name: 'Hi Krish.'})).toBeVisible();
    await page.getByLabel('Workspace password', {exact: true}).fill('public-fixture-test-password');
    await page.getByRole('button', {name: 'Open workspace', exact: true}).click();
    await expect(page.getByRole('heading', {name: 'Touch ID & passkeys'})).toBeVisible();
    await page.getByLabel('Passkey name', {exact: true}).fill('Virtual test Mac');
    await page.getByLabel('Confirm workspace password for setup').fill('public-fixture-test-password');
    await page.getByRole('button', {name: 'Enable Touch ID / passkey', exact: true}).click();
    await expect(page.getByRole('status')).toContainText('Passkey saved');
    expect((await cdp.send('WebAuthn.getCredentials', {authenticatorId})).credentials).toHaveLength(1);
    await page.getByRole('button', {name: 'Sign out', exact: true}).click();
    await expect(page.getByRole('button', {name: 'Use workspace password instead'})).toBeVisible();
    await expect(page.getByLabel('Workspace password', {exact: true})).toHaveCount(0);
    const verified = page.waitForResponse(r => r.url().endsWith('/auth/passkeys/login/verify'));
    await page.getByRole('button', {name: 'Open workspace', exact: true}).click();
    const response = await verified;
    expect(response.status()).toBe(200);
    expect((await response.json()).token).toBe(''); // Session stays in HttpOnly web cookie.
    await expect(page.getByRole('heading', {name: 'Touch ID & passkeys'})).toBeVisible();
    expect((await context.cookies()).find(c => c.name === 'selery_session')?.httpOnly).toBe(true);
    await page.getByRole('button', {name: 'Sign out', exact: true}).click();
    await page.evaluate(() => {
      navigator.credentials.get = async () => {throw new DOMException('Canceled', 'NotAllowedError');};
    });
    await page.getByRole('button', {name: 'Open workspace', exact: true}).click();
    await expect(page.getByText(/Passkey unlock was canceled/)).toBeVisible();
    expect((await page.request.get('/api/v1/settings')).status()).toBe(401);
    await page.getByRole('button', {name: 'Use workspace password instead'}).click();
    await page.getByLabel('Workspace password', {exact: true}).fill('public-fixture-test-password');
    await page.getByRole('button', {name: 'Open workspace', exact: true}).click();
    await expect(page.getByRole('heading', {name: 'Touch ID & passkeys'})).toBeVisible();
    page.once('dialog', d => d.accept());
    await page.getByRole('button', {name: 'Remove passkey', exact: true}).click();
    await expect(page.getByRole('status')).toHaveText('Passkey removed.');
    expect((await (await page.request.get('/api/v1/auth/passkeys/status')).json()).registered).toBe(false);
  } finally {
    await cdp.send('WebAuthn.removeVirtualAuthenticator', {authenticatorId});
    await cdp.detach();
  }
});
