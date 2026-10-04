import { test, expect } from '@playwright/test';
import path from 'path';

test('multipage KaushalWatch workflow covers network, analysis, review and reports', async ({ page }) => {
  const videoPath = process.env.E2E_VIDEO_PATH;
  if (!videoPath) throw new Error('E2E_VIDEO_PATH is required');

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Training Centre Network' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Network Overview' })).toBeVisible();
  await expect(page.getByRole('link', { name: /Bengaluru TC-04/ }).first()).toBeVisible();

  await page.goto('/centres/DEMO-KA-104');
  await expect(page.locator('h1').filter({ hasText: 'Bengaluru TC-04' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Recent Analysis' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Start Analysis' })).toBeVisible();
  await expect(page.getByText('Ask KaushalWatch')).toBeVisible();

  await page.getByRole('link', { name: 'Start Analysis' }).click();
  await expect(page.getByRole('heading', { name: 'Start Centre Analysis' })).toBeVisible();
  await expect(page.getByText('Automatic scheduled monitoring')).toBeVisible();

  // Core CI does not install YOLO. Attendance must show an explicit withheld state
  // rather than silently presenting a genuine zero occupancy.
  await page.getByRole('link', { name: /Analyse Attendance/ }).click();
  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await page.getByRole('button', { name: 'Analyse Attendance' }).click();
  await expect(page.getByText(/Detector unavailable/i).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/decision withheld/i)).toBeVisible();

  // Infrastructure has a deliberate discrepancy demo profile and should create
  // an evidence-backed case without requiring raw advanced controls.
  await page.goto('/centres/DEMO-KA-104/infrastructure');
  await page.locator('select.headerSelect').selectOption('discrepancy');
  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await page.getByRole('button', { name: 'Analyse Infrastructure' }).click();
  await expect(page.getByText(/Infrastructure item not detected/i)).toBeVisible({ timeout: 25_000 });

  await page.goto('/centres/DEMO-KA-104/review');
  await expect(page.getByRole('heading', { name: 'Review Queue' })).toBeVisible();
  const firstCase = page.locator('.caseListItem').first();
  await expect(firstCase).toBeVisible();
  await firstCase.click();

  const confirm = page.getByRole('button', { name: 'Confirm & Resolve' });
  await expect(confirm).toBeDisabled();
  await page.getByRole('button', { name: 'Start Review' }).click();
  await page.locator('.reviewNote').fill('Reviewed the evidence and confirmed the persistent infrastructure gap.');
  await expect(confirm).toBeEnabled();
  await confirm.click();

  await expect(page.getByText(/No pending cases|pending/i).first()).toBeVisible();

  await page.goto('/reports?centre=DEMO-KA-104&period=7d');
  await expect(page.getByRole('heading', { name: 'Compliance Reports' })).toBeVisible();
  await expect(page.getByText('Centre Verification Report')).toBeVisible();
  await expect(page.getByText(/Privacy & limitations/i)).toBeVisible();

  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Settings & Configuration' })).toBeVisible();
  await expect(page.getByText('Automatic monitoring')).toBeVisible();
  await expect(page.getByText('Low-bandwidth deployment')).toBeVisible();
});
