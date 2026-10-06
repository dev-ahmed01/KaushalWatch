import { expect, test } from '@playwright/test';

async function expectNoDocumentOverflow(page: import('@playwright/test').Page) {
  const overflow = await page.evaluate(() => {
    const clientWidth = document.documentElement.clientWidth;
    const offenders = Array.from(document.querySelectorAll<HTMLElement>('body *'))
      .map(element => {
        const rect = element.getBoundingClientRect();
        return {
          tag: element.tagName.toLowerCase(),
          className: String(element.className || '').slice(0, 180),
          text: String(element.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 100),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth,
        };
      })
      .filter(item => item.right > clientWidth + 1 || item.left < -1 || item.width > clientWidth + 1)
      .sort((a, b) => b.right - a.right)
      .slice(0, 10);

    return {
      pathname: window.location.pathname,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth,
      bodyScrollWidth: document.body.scrollWidth,
      offenders,
    };
  });

  const diagnostic = `${overflow.pathname}: ${JSON.stringify(overflow.offenders)}`;
  expect(overflow.scrollWidth, diagnostic).toBeLessThanOrEqual(overflow.clientWidth + 1);
  expect(overflow.bodyScrollWidth, diagnostic).toBeLessThanOrEqual(overflow.clientWidth + 1);
}

test('keyboard users can skip navigation and close the assistant', async ({ page }) => {
  await page.goto('/');

  await page.keyboard.press('Tab');
  const skip = page.getByRole('link', { name: 'Skip to content' });
  await expect(skip).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();

  await page.getByRole('button', { name: 'Ask KaushalAI' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
});

test('mobile shell stays usable without document-level horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });

  const routes = [
    '/',
    '/centres',
    '/centres/DEMO-KA-104',
    '/centres/DEMO-KA-104/attendance',
    '/centres/DEMO-KA-104/practical',
    '/centres/DEMO-KA-104/infrastructure',
    '/centres/DEMO-KA-104/evidence',
    '/cases/SIM-KA-104-ATT',
    '/insights',
    '/actions',
  ];

  for (const route of routes) {
    await page.goto(route);
    await expect(page.getByRole('navigation', { name: 'Mobile primary navigation' })).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Date range' })).toBeVisible();
    await expectNoDocumentOverflow(page);
  }

  await page.getByRole('navigation', { name: 'Mobile primary navigation' }).getByRole('link', { name: 'Centres' }).click();
  await expect(page).toHaveURL(/\/centres$/);

  await page.getByRole('combobox', { name: 'Date range' }).selectOption('last_7_days');
  await expect(page.getByRole('combobox', { name: 'Date range' })).toHaveValue('last_7_days');
});

test('centre tabs remain reachable on a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/centres/DEMO-KA-104');

  const tabs = page.getByRole('navigation', { name: 'Centre sections' });
  await expect(tabs).toBeVisible();
  await expect(tabs.getByRole('link', { name: 'Overview', exact: true })).toBeVisible();
  await expect(tabs.getByRole('link', { name: 'Evidence', exact: true })).toBeAttached();

  await tabs.getByRole('link', { name: 'Evidence', exact: true }).click();
  await expect(page).toHaveURL(/\/centres\/DEMO-KA-104\/evidence$/);
  await expect(page.getByRole('heading', { name: 'Evidence', exact: true })).toBeVisible();
  await expectNoDocumentOverflow(page);
});

test('analysis dialog fits the mobile viewport and exposes live status semantics', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/centres/DEMO-KA-104');

  const runAnalysis = page.getByRole('button', { name: /Run analysis/i }).first();
  await expect(runAnalysis).toBeVisible();
  await runAnalysis.click();

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeLessThanOrEqual(390);
  expect(box!.height).toBeLessThanOrEqual(844);

  await expect(dialog.locator('[aria-live="polite"]')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
});

test('unknown routes provide a clear recovery action', async ({ page }) => {
  await page.goto('/this-route-does-not-exist');

  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  const back = page.getByRole('link', { name: 'Back to KaushalAI' });
  await expect(back).toBeVisible();
  await back.click();
  await expect(page).toHaveURL(/\/$/);
});

test('API failures never present simulated fallbacks as live evidence', async ({ page }) => {
  await page.route('**/api/kaushalai/brief**', route => route.abort());
  await page.goto('/');

  await expect(page.getByRole('alert')).toContainText('simulated demo fallback data');
  await expect(page.getByText('Simulated fallback')).toBeVisible();

  await page.unroute('**/api/kaushalai/brief**');
  await page.route('**/api/centres', route => route.abort());
  await page.goto('/centres');

  await expect(page.getByRole('alert')).toContainText('simulated demo fallback data');
  await expect(page.getByText('Simulated fallback')).toBeVisible();
  await expect(page.getByText('Bengaluru TC-04')).toBeVisible();
});

test('empty and unavailable centre data remain distinct from healthy state', async ({ page }) => {
  await page.route('**/api/centres', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ centres: [], total: 0 }),
  }));
  await page.goto('/centres');

  await expect(page.getByText('No monitored centre records are available.')).toBeVisible();
  await expect(page.getByText('No demo values have been substituted for an empty live response.')).toBeVisible();
  await expect(page.getByText('Bengaluru TC-04')).toHaveCount(0);

  await page.unroute('**/api/centres');
  await page.route('**/api/centres/DEMO-KA-104/intelligence**', route => route.abort());
  await page.goto('/centres/DEMO-KA-104');

  await expect(page.getByRole('alert')).toContainText('verification states, recommendations and recent analysis are not being inferred');
  await expect(page.getByText('Recommendations are unavailable until centre intelligence responds.')).toBeVisible();
  await expect(page.getByText('Recent analysis is unavailable until centre intelligence responds.')).toBeVisible();
});

test('evidence API failures do not masquerade as an empty review queue', async ({ page }) => {
  await page.route('**/api/cases', route => route.abort());
  await page.goto('/centres/DEMO-KA-104/evidence');

  await expect(page.getByRole('alert')).toContainText('Case and evidence records are unavailable');
  await expect(page.getByText('Evidence records unavailable').first()).toBeVisible();
  await expect(page.getByText('Case records are unavailable. No empty queue conclusion is being shown.')).toBeVisible();
  await expect(page.getByText('No open officer-review case for this centre.')).toHaveCount(0);
});

test('officer review exposes a labelled decision field and alert errors', async ({ page }) => {
  await page.goto('/cases/SIM-KA-104-ATT');

  const note = page.getByLabel('Decision note');
  await expect(note).toBeVisible();

  await page.getByRole('button', { name: 'Confirm discrepancy' }).click();
  await expect(page.getByRole('alert')).toContainText('Add a short review note');
});

test('attendance and activity pages withhold conclusions when evidence services fail', async ({ page }) => {
  await page.route('**/api/analysis-history**', route => route.abort());
  await page.goto('/centres/DEMO-KA-104/attendance');

  await expect(page.getByRole('alert')).toContainText('Reported/observed facts and Temporal Proof are withheld');
  await expect(page.getByText('Unavailable while required evidence services are unavailable. No temporal pattern is inferred.')).toBeVisible();
  await expect(page.getByText('Simulated preview:', { exact: false })).toHaveCount(0);

  await page.unroute('**/api/analysis-history**');
  await page.route('**/api/centres/DEMO-KA-104/activity-intelligence**', route => route.abort());
  await page.goto('/centres/DEMO-KA-104/practical');

  await expect(page.getByRole('alert')).toContainText('No activity pattern or follow-up conclusion is being inferred');
  await expect(page.getByText('Activity service unavailable')).toBeVisible();
});

