import { expect, test } from '@playwright/test';

test('Camera Trust centre workspace abstains instead of inventing a healthy camera', async ({ page }) => {
  await page.goto('/centres/DEMO-KA-104/camera-trust');
  await expect(page.getByRole('heading', { name: 'Camera Trust' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Centre sections' })
    .getByRole('link', { name: 'Camera Trust' })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByText('Not production-qualified')).toBeVisible();
  await expect(page.getByText('None — shadow only')).toBeVisible();
  await expect(page.getByText('UNKNOWN', { exact: true }).first()).toBeVisible();
  // The demo JSON backend intentionally cannot masquerade as migrated PostgreSQL.
  await expect(page.getByRole('alert')).toContainText('requires migrated PostgreSQL');
  await expect(page.getByText('No cameras registered. This is not a healthy-camera finding.')).toBeVisible();
});
