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

    // Chromium accepts Secure cookies on loopback in this HTTPS-equivalent
    // test context. Playwright's Node APIRequestContext does not send Secure
    // cookies over plain HTTP: use real browser fetch for authenticated BFF.
    const cases = await page.evaluate(async () => {
      const response = await fetch('/api/proxy/api/cases', {
        credentials: 'same-origin', cache: 'no-store',
      });
      return { status: response.status, cache: response.headers.get('cache-control'), text: await response.text() };
    });
    expect(cases.status).toBe(200);
    expect(cases.cache).toContain('no-store');
    expect(cases.text).not.toContain(TOKEN);
    const records = JSON.parse(cases.text);
    expect(records.length).toBeGreaterThan(0);
    expect(records.some((record: { evidence: unknown[] }) => record.evidence.length > 0)).toBe(true);
    const firstEvidence = records.flatMap((record: { evidence: { evidence_id: string }[] }) => record.evidence)[0];
    const image = await page.evaluate(async evidenceId => {
      const response = await fetch('/api/proxy/evidence/' + evidenceId + '.jpg', {
        credentials: 'same-origin', cache: 'no-store',
      });
      const bytes = new Uint8Array(await response.arrayBuffer());
      return { status: response.status, contentType: response.headers.get('content-type'),
               length: bytes.length, first: Array.from(bytes.slice(0, 2)) };
    }, firstEvidence.evidence_id);
    expect(image.status).toBe(200);
    expect(image.contentType).toContain('image/');
    expect(image.length).toBeGreaterThan(100);
    expect(image.first).toEqual([0xff, 0xd8]);

    // CSRF and same-origin required for every mutation, including review.
    const missingCsrf = await page.evaluate(async () => {
      const response = await fetch('/api/proxy/api/cases/SIM-KA-104-ATT/review', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'confirmed', note: 'Synthetic only' }),
      });
      return response.status;
    });
    expect(missingCsrf).toBe(403);
    // This API-request harness forwards the opaque cookie only to exercise a
    // forged Origin; real browsers cannot override their Origin header.
    const invalidOrigin = await page.request.post('/api/proxy/api/cases/SIM-KA-104-ATT/review', {
      data: { action: 'confirmed', note: 'Synthetic only' },
      headers: { Cookie: 'kw_officer_session=' + session?.value,
                 Origin: 'https://attacker.example', 'X-KaushalWatch-CSRF': payload.csrfToken },
    });
    expect(invalidOrigin.status()).toBe(403);
    const edgeBlocked = await page.evaluate(async csrf => {
      const response = await fetch('/api/proxy/api/edge/sync', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-KaushalWatch-CSRF': csrf },
        body: JSON.stringify({ events: [] }),
      });
      return response.status;
    }, payload.csrfToken);
    expect(edgeBlocked).toBe(404);

    await page.getByRole('button', { name: 'Sign out of officer session' }).click();
    await expect(page).toHaveURL(/\/login/);
    const after = await page.request.get('/api/proxy/api/cases', {
      headers: { Cookie: 'kw_officer_session=' + session?.value },
    });
    expect(after.status()).toBe(401);
    const afterStatus = await page.evaluate(async () => {
      const response = await fetch('/api/auth/status', { credentials: 'same-origin' });
      return response.json();
    });
    expect(afterStatus.authenticated).toBe(false);
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

  test('one Redis-backed login works on two Next.js instances and logout revokes both', async ({ page }) => {
    test.skip(process.env.E2E_DISTRIBUTED_MODE !== 'true', 'Requires two protected web instances sharing synthetic Redis REST.');
    await page.goto('http://127.0.0.1:3001/login');
    await page.getByLabel('Officer access key').fill(TOKEN);
    await page.getByRole('button', { name: 'Sign in securely' }).click();
    await expect(page).toHaveURL('http://127.0.0.1:3001/');
    const cookie = (await page.context().cookies()).find(c => c.name === 'kw_officer_session');
    expect(cookie?.value).toHaveLength(43);

    // Navigate rather than fetch across origins: browser cookies are scoped to
    // the hostname, not the TCP port. Instance B never issued this session.
    await page.goto('http://127.0.0.1:3002/');
    await expect(page.getByRole('heading', { name: 'KaushalAI' })).toBeVisible();
    const fromB = await page.evaluate(async () => {
      const [status, cases] = await Promise.all([
        fetch('/api/auth/status', { cache: 'no-store', credentials: 'same-origin' }),
        fetch('/api/proxy/api/cases', { cache: 'no-store', credentials: 'same-origin' }),
      ]);
      return { status: await status.json(), caseCode: cases.status };
    });
    expect(fromB.status.authenticated).toBe(true);
    expect(fromB.status.csrfToken).toBeTruthy();
    expect(fromB.caseCode).toBe(200);
    await page.getByRole('button', { name: 'Sign out of officer session' }).click();
    await expect(page).toHaveURL(/\/login/);

    // A new request to instance A using the revoked ID is rejected.
    const revoked = await page.request.get('http://127.0.0.1:3001/api/proxy/api/cases', {
      headers: { Cookie: 'kw_officer_session=' + cookie?.value },
    });
    expect(revoked.status()).toBe(401);
    await page.goto('http://127.0.0.1:3001/');
    await expect(page).toHaveURL(/\/login\?next=/);
  });


  test('centre viewer sees only permitted records and cannot record a decision', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Officer access key').fill('CI_Synthetic_Viewer_AccessKey_0123456789abcdef');
    await page.getByRole('button', { name: 'Sign in securely' }).click();
    await expect(page).toHaveURL('http://127.0.0.1:3001/');
    const scoped = await page.evaluate(async () => {
      const [cases, profile, deniedReport] = await Promise.all([
        fetch('/api/proxy/api/cases', { credentials: 'same-origin' }),
        fetch('/api/proxy/api/officer-context', { credentials: 'same-origin' }),
        fetch('/api/proxy/api/centres/DEMO-KA-207/report.pdf', { credentials: 'same-origin' }),
      ]);
      return {
        casesCode: cases.status, records: await cases.json(),
        profile: await profile.json(), reportCode: deniedReport.status,
      };
    });
    expect(scoped.casesCode).toBe(200);
    expect(scoped.records.length).toBeGreaterThan(0);
    expect(scoped.records.every((record: { centre_id: string }) =>
      record.centre_id === 'DEMO-KA-104')).toBe(true);
    expect(scoped.profile.role).toBe('centre_viewer');
    expect(scoped.profile.can_review).toBe(false);
    expect(scoped.reportCode).toBe(404);
    await page.goto('/cases/SIM-KA-104-ATT');
    await expect(page.getByText('Read-only officer access.', { exact: false })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Confirm discrepancy' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Ask KaushalAI' })).toHaveCount(0);
    const csrf = await page.evaluate(async () => {
      const response = await fetch('/api/auth/status', { credentials: 'same-origin' });
      return (await response.json()).csrfToken as string;
    });
    const denied = await page.evaluate(async token => {
      const response = await fetch('/api/proxy/api/cases/SIM-KA-104-ATT/review', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-KaushalWatch-CSRF': token },
        body: JSON.stringify({ action: 'confirmed', note: 'Unauthorized test write' }),
      });
      return response.status;
    }, csrf);
    expect(denied).toBe(403);
    await page.goto('/cases/SIM-KA-207-ATT');
    await expect(page.getByRole('alert')).toBeVisible();
  });

});
