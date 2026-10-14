import { expect, test } from '@playwright/test';

const BASE = 'http://127.0.0.1:3003';
const IDP = 'http://127.0.0.1:8371/authorize';
const API = 'http://127.0.0.1:8013';
test.describe('Synthetic OIDC browser acceptance (never production)', () => {
  test.skip(process.env.E2E_SYNTHETIC_OIDC !== 'true', 'CI-only OIDC test with ephemeral signer');

  test('PKCE authorization, signed API identity, protected case access and logout', async ({ page }) => {
    await page.goto(BASE + '/login');
    await expect(page.getByRole('link', { name: 'Continue with organization SSO' })).toBeVisible();
    await expect(page.getByLabel('Officer access key')).toHaveCount(0);
    const oldKeyLogin = await page.request.post(BASE + '/api/auth/login', {
      data: { accessKey: 'synthetic-not-a-real-key-01234567890123' },
      headers: { Origin: BASE },
    });
    expect(oldKeyLogin.status()).toBe(403);

    const direct = await page.request.get(API + '/api/cases');
    expect(direct.status()).toBe(401);
    await page.getByRole('link', { name: 'Continue with organization SSO' }).click();
    await expect(page).toHaveURL(BASE + '/');
    const cookies = await page.context().cookies();
    const session = cookies.find(c => c.name === 'kw_officer_session');
    expect(session?.httpOnly).toBe(true);
    expect(session?.sameSite).toBe('Strict');
    expect(session?.value).toHaveLength(43);
    expect(cookies.some(c => c.name === 'kw_oidc_transaction')).toBe(false);
    const scoped = await page.evaluate(async () => {
      const [status, principal, cases] = await Promise.all([
        fetch('/api/auth/status', { cache: 'no-store' }),
        fetch('/api/proxy/api/officer-context', { cache: 'no-store' }),
        fetch('/api/proxy/api/cases', { cache: 'no-store' }),
      ]);
      return {
        status: await status.json(), principal: await principal.json(),
        casesCode: cases.status, cases: await cases.json(),
      };
    });
    expect(scoped.status.authenticated).toBe(true);
    expect(scoped.status.identityMode).toBe('oidc');
    expect(scoped.principal.role).toBe('network_admin');
    expect(scoped.casesCode).toBe(200);
    expect(scoped.cases.length).toBeGreaterThan(0);
    expect(JSON.stringify(scoped)).not.toContain('access_token');

    await page.getByRole('button', { name: 'Sign out of officer session' }).click();
    await expect(page).toHaveURL(/\/login/);
    const revoked = await page.request.get(BASE + '/api/proxy/api/cases', {
      headers: { Cookie: 'kw_officer_session=' + session?.value },
    });
    expect(revoked.status()).toBe(401);
  });

  test('forged authorization state never establishes a browser session', async ({ page }) => {
    await page.route(IDP + '**', async route => {
      const target = new URL(route.request().url());
      target.searchParams.set('state', 'x'.repeat(43));
      await route.continue({ url: target.toString() });
    });
    await page.goto(BASE + '/api/auth/oidc/start');
    await expect(page.getByText('The organization sign-in could not be completed.')).toBeVisible();
    const status = await page.request.get(BASE + '/api/auth/status');
    expect((await status.json()).authenticated).toBe(false);
  });

  test('unprovisioned signed subject is denied by backend grants', async ({ page }) => {
    await page.route(IDP + '**', async route => {
      const target = new URL(route.request().url());
      target.searchParams.set('synthetic_subject', 'ci-unprovisioned-subject');
      await route.continue({ url: target.toString() });
    });
    await page.goto(BASE + '/api/auth/oidc/start');
    await expect(page.getByText('The organization sign-in could not be completed.')).toBeVisible();
    const noSession = await page.request.get(BASE + '/api/proxy/api/cases');
    expect(noSession.status()).toBe(401);
  });

  test('wrong API audience access token cannot create a session', async ({ page }) => {
    await page.route(IDP + '**', async route => {
      const target = new URL(route.request().url());
      target.searchParams.set('synthetic_audience', 'api://wrong-audience');
      await route.continue({ url: target.toString() });
    });
    await page.goto(BASE + '/api/auth/oidc/start');
    await expect(page.getByText('The organization sign-in could not be completed.')).toBeVisible();
    expect((await (await page.request.get(BASE + '/api/auth/status')).json()).authenticated).toBe(false);
  });

  test('signed admin claims cannot upgrade a locally provisioned viewer', async ({ page }) => {
    await page.route(IDP + '**', async route => {
      const target = new URL(route.request().url());
      target.searchParams.set('synthetic_subject', 'ci-viewer-subject');
      await route.continue({ url: target.toString() });
    });
    await page.goto(BASE + '/api/auth/oidc/start');
    await expect(page).toHaveURL(BASE + '/');
    const observed = await page.evaluate(async () => {
      const [who, cases, forbidden] = await Promise.all([
        fetch('/api/proxy/api/officer-context'),
        fetch('/api/proxy/api/cases'),
        fetch('/api/proxy/api/centres/DEMO-KA-207/report.pdf'),
      ]);
      return { principal: await who.json(), cases: await cases.json(), denied: forbidden.status };
    });
    expect(observed.principal.role).toBe('centre_viewer');
    expect(observed.cases.every((c: { centre_id: string }) => c.centre_id === 'DEMO-KA-104')).toBe(true);
    expect(observed.denied).toBe(404);
  });
});
