import { expect, test } from '@playwright/test';

test('R2 Overview presents compact grounded status, priority issues, and copilot fallback', async ({ page }) => {
  await page.route('**/api/assistant/status', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({enabled: true, configured: false, available: false, voice_configured: false, voice_available: false}),
  }));
  await page.goto('/');
  await expect(page.getByRole('heading', {name:'Overview', exact:true})).toBeVisible();
  await expect(page.getByRole('region', {name:'Training centre status'})).toBeVisible();
  await expect(page.getByRole('region', {name:'Priority issues'})).toBeVisible();
  await expect(page.getByRole('complementary', {name:'KaushalAI copilot'})).toBeVisible();
  await expect(page.getByText('Operational summary')).toBeVisible();
  await expect(page.getByRole('textbox', {name:'Ask KaushalAI about authorised evidence'})).toBeDisabled();
  await expect(page.getByRole('link', {name:/View all issues/})).toHaveAttribute('href','/issues');
});

test('R2 Overview opens the corresponding selected issue', async ({ page }) => {
  await page.goto('/');
  const priority = page.getByRole('region', {name:'Priority issues'});
  const link = priority.getByRole('link', {name:/Inspect evidence/}).first();
  await expect(link).toHaveAttribute('href',/\/issues\?issue=/);
  await link.click();
  await expect(page).toHaveURL(/\/issues\?issue=/);
});

test('R2 compact overview stays within narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Mobile primary navigation' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});
