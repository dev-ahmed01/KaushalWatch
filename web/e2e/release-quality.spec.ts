import { expect, test } from '@playwright/test';

async function expectNoDocumentOverflow(page: import('@playwright/test').Page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    bodyScrollWidth: document.body.scrollWidth,
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
  expect(overflow.bodyScrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
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
