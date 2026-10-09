import { expect, test } from '@playwright/test';

// All review writes in this spec are intercepted. The real backend's atomic
// case transitions are independently exercised by Python/TestClient tests;
// this suite checks browser behavior and network call count without editing
// seeded CI cases or changing another test's demo story.
test('single officer click sends one review write and renders both persisted audit steps', async ({ page }) => {
  const original = await page.request.get(
    'http://127.0.0.1:8000/api/cases/SIM-KA-104-ATT/evidence-pack',
  );
  expect(original.ok()).toBeTruthy();
  const baseline = await original.json();
  let saved = false;
  let reviewWrites = 0;
  await page.route('**/api/review-access', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ mode: 'token', required: true, prototype_only: true }),
  }));
  await page.route('**/api/cases/SIM-KA-104-ATT/evidence-pack', route => {
    const body = structuredClone(baseline);
    body.case.status = saved ? 'confirmed' : 'open';
    body.review.status = saved ? 'confirmed' : 'open';
    body.review.terminal = saved;
    body.review.history = saved ? [
      { actor: 'synthetic-reviewer', timestamp: '2026-10-10T02:00:00+05:30',
        from_status: 'under_review', to_status: 'confirmed', note: 'Reviewed synthetic case.' },
      { actor: 'synthetic-reviewer', timestamp: '2026-10-10T01:59:59+05:30',
        from_status: 'open', to_status: 'under_review', note: 'Officer opened evidence review.' },
    ] : [];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.route('**/api/cases/SIM-KA-104-ATT/review', async route => {
    reviewWrites += 1;
    const posted = route.request().postDataJSON();
    expect(posted.action).toBe('confirmed');
    expect(posted.note).toBe('Reviewed synthetic case.');
    expect(route.request().headers()['authorization']).toBe('Bearer browser-ci-token');
    // Server confirms a single HTTP request, not separate start+final POSTs.
    saved = true;
    return route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ ...baseline.case, status: 'confirmed' }),
    });
  });

  await page.goto('/cases/SIM-KA-104-ATT');
  await expect(page.getByLabel('Officer access key')).toBeVisible();
  await page.getByLabel('Officer access key').fill('browser-ci-token');
  await page.getByLabel('Decision note').fill('Reviewed synthetic case.');
  await page.getByRole('button', { name: 'Confirm discrepancy' }).click();
  await expect(page.getByText('Case confirmed for officer follow-up.')).toBeVisible();
  expect(reviewWrites).toBe(1);
  await expect(page.getByText('A final officer outcome has been recorded.')).toBeVisible();
  await page.reload();
  await expect(page.getByText('A final officer outcome has been recorded.')).toBeVisible();
  await expect(page.getByText(/Recorded by: synthetic-reviewer/i).first()).toBeVisible();
  expect(reviewWrites).toBe(1);
});

test('review-server failure makes no implicit start-review write and shows an error', async ({ page }) => {
  const original = await page.request.get(
    'http://127.0.0.1:8000/api/cases/SIM-KA-104-ATT/evidence-pack',
  );
  expect(original.ok()).toBeTruthy();
  const baseline = await original.json();
  let writes = 0;
  await page.route('**/api/cases/SIM-KA-104-ATT/evidence-pack', route => {
    const body = structuredClone(baseline);
    body.case.status = 'open';
    body.review.status = 'open';
    body.review.terminal = false;
    body.review.history = [];
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.route('**/api/review-access', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ mode: 'demo', required: false, prototype_only: true }),
  }));
  await page.route('**/api/cases/SIM-KA-104-ATT/review', route => {
    writes += 1;
    return route.fulfill({
      status: 503, contentType: 'application/json',
      body: JSON.stringify({ detail: 'Synthetic backend case write unavailable.' }),
    });
  });
  await page.goto('/cases/SIM-KA-104-ATT');
  await page.getByLabel('Decision note').fill('Synthetic incomplete network action.');
  await page.getByRole('button', { name: 'Confirm discrepancy' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Synthetic backend case write unavailable.' })).toBeVisible();
  expect(writes).toBe(1);
  await expect(page.getByText('A final officer outcome has been recorded.')).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Confirm discrepancy' })).toBeVisible();
  expect(writes).toBe(1);
});

test('offline action API is unavailable, not an empty healthy queue', async ({ page }) => {
  await page.route('**/api/actions**', route => route.abort());
  await page.goto('/actions');
  await expect(page.getByText('The grounded action queue is temporarily unavailable.')).toBeVisible();
  await expect(page.getByText('No officer action is queued.')).toHaveCount(0);
  await page.unroute('**/api/actions**');
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Action queue', exact: true })).toBeVisible();
  await expect(page.getByText('The grounded action queue is temporarily unavailable.')).toHaveCount(0);
});
