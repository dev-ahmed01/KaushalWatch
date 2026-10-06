import { test, expect } from '@playwright/test';

test('AI-first restructure exposes the new four-item navigation and core routes', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'KaushalAI' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('link')).toHaveCount(4);
  await expect(page.getByRole('link', { name: 'KaushalAI' })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('link', { name: 'Centres' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Insights' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Actions' })).toBeVisible();
  await expect(page.getByText('Centres at a glance')).toBeVisible();
  await expect(page.getByText(/Grounded in 0 analysis runs/)).toBeVisible();
  await page.getByRole('button', { name: '7 days' }).click();
  await expect(page.getByText(/Grounded in 15 analysis runs/)).toBeVisible();

  await page.goto('/centres');
  await expect(page.getByRole('heading', { name: 'Centres' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'View', exact: true }).first()).toBeVisible();

  await page.goto('/centres/DEMO-KA-104');
  await expect(page.getByRole('heading', { name: 'Bengaluru TC-04' })).toBeVisible();
  await expect(page.getByText('KaushalAI centre brief')).toBeVisible();
  await expect(page.getByText('Verification engines')).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Centre sections' }).getByRole('link', { name: 'Overview', exact: true })).toHaveAttribute('aria-current', 'page');

  await page.goto('/centres/DEMO-KA-104/practical');
  await expect(page.getByRole('heading', { name: 'Activity', exact: true })).toBeVisible();
  await expect(page.getByText('Daily activity pattern')).toBeVisible();
  await expect(page.getByText('10:45–12:00').first()).toBeVisible();
  await expect(page.getByText('14:00–14:45').first()).toBeVisible();
  await expect(page.getByText('Confirm the low-activity period with the Centre Head')).toBeVisible();
  await expect(page.getByText(/scheduled break, class transition, or interruption/)).toBeVisible();

  await page.goto('/insights');
  await expect(page.getByRole('heading', { name: 'Insights' })).toBeVisible();
  await expect(page.getByText('Centre health')).toBeVisible();
  await expect(page.getByText('Reported vs observed attendance')).toBeVisible();
  await expect(page.getByText('Activity across the training day')).toBeVisible();
  await expect(page.getByText('Infrastructure exceptions')).toBeVisible();
  await expect(page.getByText('Camera trust')).toBeVisible();
  await expect(page.getByText('Case outcomes')).toBeVisible();
  await expect(page.getByText('Bengaluru attendance variance')).toBeVisible();
  await expect(page.getByText('Hubballi infrastructure')).toBeVisible();
  await expect(page.getByText('Tumakuru camera trust')).toBeVisible();
  await expect(page.getByText('Centre verification reports')).toBeVisible();
  await expect(page.getByText('91').first()).toBeVisible();

  await page.goto('/actions');
  await expect(page.getByRole('heading', { name: 'Actions', exact: true })).toBeVisible();
  await expect(page.getByText('Today’s recommended actions')).toBeVisible();
  await expect(page.getByText('Action queue')).toBeVisible();

  await page.goto('/cases');
  await expect(page).toHaveURL(/\/actions$/);

  await page.goto('/reports');
  await expect(page).toHaveURL(/\/insights$/);
});
