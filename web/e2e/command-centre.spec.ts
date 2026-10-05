import { test, expect } from '@playwright/test';

test('calm command centre keeps the three-item IA and evidence-first workflow', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Network' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('link')).toHaveCount(3);
  await expect(page.getByRole('link', { name: 'Network' })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('link', { name: 'Cases' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Reports' })).toBeVisible();

  await page.getByRole('button', { name: 'List' }).click();
  await expect(page.getByRole('link', { name: /Bengaluru TC-04 Simulated/ })).toBeVisible();
  await page.goto('/centres/DEMO-KA-104');
  await expect(page.getByRole('heading', { name: 'Bengaluru TC-04' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Centre sections' }).getByRole('link')).toHaveCount(5);
  await expect(page.getByRole('button', { name: /Run analysis now/i })).toBeVisible();
  await expect(page.getByText('Temporal Proof')).toBeVisible();
  await expect(page.getByText(/A single frame never creates a case/i)).toBeVisible();

  await page.getByRole('button', { name: /Run analysis now/i }).click();
  await expect(page.getByRole('heading', { name: 'Run analysis' })).toBeVisible();
  await expect(page.getByText('Manifest reading')).toBeVisible();
  await expect(page.getByText('Visual evidence', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Temporal Proof', { exact: true }).last()).toBeVisible();
  await expect(page.getByText('Case evidence', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Close analysis' }).click();

  await page.goto('/centres/DEMO-KA-104/attendance');
  await expect(page.getByRole('heading', { name: 'Attendance' })).toBeVisible();
  await expect(page.getByText('Reported', { exact: true })).toBeVisible();
  await expect(page.getByText('Observed', { exact: true })).toBeVisible();
  await expect(page.getByText('Status', { exact: true })).toBeVisible();

  await page.goto('/cases');
  await expect(page.getByRole('heading', { name: 'Cases' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Review Queue' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Escalations' })).toBeVisible();

  await page.goto('/reports');
  await expect(page.getByRole('heading', { name: 'Reports' })).toBeVisible();
  await expect(page.getByText('Centre Verification Report')).toBeVisible();
  await expect(page.getByRole('link', { name: /Download PDF/i })).toBeVisible();
});
