import { expect, test } from '@playwright/test';

const PROTECTED = process.env.E2E_PROTECTED_MODE === 'true';
const TOKEN = 'CI_Synthetic_Officer_AccessKey_0123456789abcdef';
test.describe('Protected browser officer session', () => {
  test.skip(!PROTECTED, 'Dedicated protected session smoke requires separate protected API and web.');

  test('login persists HttpOnly session, protected records and evidence flow through BFF', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/login\?next=/);
    await expect(page.getByRole('heading', { name: 'Officer sign in' })).toBeVisible();

    // No token, no data. A backend token is still required on direct protected API.
    const anonymous = await page.request.get('/api/proxy/api/cases');
    expect(anonymous.status()).toBe(401);
    const direct = await page.request.get('http://127.0.0.1:8011/api/cases');
    expect(direct.status()).toBe(401);
    const bad = await page.request.post('/api/auth/login', {
      data: { accessKey: 'A'.repeat(40) },
      headers: { Origin: 'http://127.0.0.1:3001' },
    });
    expect(bad.status()).toBe(401);
    const crossOrigin = await page.request.post('/api/auth/login', {
      data: { accessKey: TOKEN }, headers: { Origin: 'https://attacker.example' },
    });
    expect(crossOrigin.status()).toBe(403);

    await page.getByLabel('Officer access key').fill(TOKEN);
    await page.getByRole('button', { name: 'Sign in securely' }).click();
    await expect(page).toHaveURL('http://127.0.0.1:3001/');
    await expect(page.getByRole('heading', { name: 'KaushalAI' })).toBeVisible();
    const cookies = await page.context().cookies();
    const session = cookies.find(c => c.name === 'kw_officer_session');
    expect(session).toBeTruthy();
    expect(session?.httpOnly).toBe(true);
    expect(session?.sameSite).toBe('Strict');
    expect(session?.value).not.toContain(TOKEN);
    const status = await page.evaluate(async () => {
      const response = await fetch('/api/auth/status', {
        cache: 'no-store', credentials: 'same-origin',
      });
      return { code: response.status, payload: await response.json() };
    });
    expect(status.code).toBe(200);
    const payload = status.payload;
    expect(payload.authenticated).toBe(true);
    expect(payload.mode).toBe('protected');
    expect(payload.csrfToken.length).toBeGreaterThan(20);
    expect(JSON.stringify(payload)).not.toContain(TOKEN);

    const cases = await page.request.get('/api/proxy/api/cases');
    expect(cases.status()).toBe(200);
    expect(cases.headers()['cache-control']).toContain('no-store');
    expect(cases.text()).resolves.not.toContain(TOKEN);
    const records = await cases.json();
    expect(records.length).toBeGreaterThan(0);
    expect(records.some((record: { evidence: unknown[] }) => record.evidence.length > 0)).toBe(true);
    const firstEvidence = records.flatMap((record: { evidence: { evidence_id: string }[] }) => record.evidence)[0];
    const image = await page.request.get('/api/proxy/evidence/' + firstEvidence.evidence_id + '.jpg');
    expect(image.status()).toBe(200);
    expect(image.headers()['content-type']).toContain('image/');
    const imageBytes = await image.body();
    expect(imageBytes.length).toBeGreaterThan(100);
    expect(imageBytes[0]).toBe(0xff);
    expect(imageBytes[1]).toBe(0xd8);

    // CSRF and same-origin required for every mutation, including review.
    const missingCsrf = await page.request.post(
      '/api/proxy/api/cases/SIM-KA-104-ATT/review',
      { data: { action: 'confirmed', note: 'Synthetic only' }, headers: { Origin: 'http://127.0.0.1:3001' } },
    );
    expect(missingCsrf.status()).toBe(403);
    const invalidOrigin = await page.request.post('/api/proxy/api/cases/SIM-KA-104-ATT/review', {
      data: { action: 'confirmed', note: 'Synthetic only' },
      headers: { Origin: 'https://attacker.example', 'X-KaushalWatch-CSRF': payload.csrfToken },
    });
    expect(invalidOrigin.status()).toBe(403);
    const edgeBlocked = await page.request.post('/api/proxy/api/edge/sync', {
      data: { events: [] },
      headers: { Origin: 'http://127.0.0.1:3001', 'X-KaushalWatch-CSRF': payload.csrfToken },
    });
    expect(edgeBlocked.status()).toBe(404);

    await page.getByRole('button', { name: 'Sign out of officer session' }).click();
    await expect(page).toHaveURL(/\/login/);
    const after = await page.request.get('/api/proxy/api/cases');
    expect(after.status()).toBe(401);
    const afterStatus = await page.request.get('/api/auth/status');
    expect((await afterStatus.json()).authenticated).toBe(false);
  });

  test('protected browser review posts exactly one audited decision through the proxy', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Officer access key').fill(TOKEN);
    await page.getByRole('button', { name: 'Sign in securely' }).click();
    await expect(page).toHaveURL('http://127.0.0.1:3001/');
    await page.goto('/cases/SIM-KA-104-ATT');
    await expect(page.getByRole('heading', { name: 'Attendance discrepancy' })).toBeVisible();
    await expect(page.getByLabel('Officer access key')).toHaveCount(0);
    await expect(page.getByAltText('Retained compliance evidence')).toBeVisible();
    await page.getByLabel('Decision note').fill('Synthetic officer reviewed retained privacy evidence.');
    await page.getByRole('button', { name: 'Confirm discrepancy' }).click();
    await expect(page.getByText('Case confirmed for officer follow-up.')).toBeVisible();
    await page.reload();
    await expect(page.getByText('A final officer outcome has been recorded.')).toBeVisible();
    await page.getByText(/Audit trail · 2 events/).click();
    await expect(page.getByText('Recorded by: browser-ci-officer').first()).toBeVisible();
  });
});
