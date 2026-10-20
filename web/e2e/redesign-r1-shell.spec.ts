import { expect, test } from '@playwright/test';

test('R1 five-module primary shell and backwards routes', async ({ page }) => {
  await page.goto('/');
  const nav = page.getByRole('navigation', { name: 'Primary navigation' });
  for (const name of ['Overview', 'Issues', 'Insights', 'Centre Desk', 'Chatbox']) {
    await expect(nav.getByRole('link', { name, exact: true })).toBeAttached();
  }
  await nav.getByRole('link', { name: 'Centre Desk' }).click();
  await expect(page).toHaveURL(/\/centre-desk$/);
  await expect(page.getByRole('heading', { name: 'Centre Desk' }).first()).toBeVisible();
  await nav.getByRole('link', { name: 'Chatbox' }).click();
  await expect(page).toHaveURL(/\/chatbox$/);
  await expect(page.getByText('Messaging setup in progress')).toBeVisible();
  await page.goto('/actions');
  await expect(page.getByRole('heading', { name: 'Action queue' })).toBeVisible();
  await page.goto('/issues');
  await expect(page.getByRole('heading', { name: 'Issues', exact: true })).toBeVisible();
});

test('R1 stays inside a 320px mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  for (const path of ['/', '/issues', '/insights', '/centre-desk', '/chatbox']) {
    await page.goto(path);
    await expect(page.getByRole('navigation', { name: 'Mobile primary navigation' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), path).toBeLessThanOrEqual(1);
  }
});
