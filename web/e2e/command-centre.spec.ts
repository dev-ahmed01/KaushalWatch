import { test, expect } from '@playwright/test';
import path from 'path';

test('command centre verifies attendance, evidence, review and infrastructure cases', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByText('KaushalWatch Command Centre')).toBeVisible();
  await expect(page.getByText('PROTOTYPE — SIMULATED OPERATIONAL DATA')).toBeVisible();

  const videoPath = process.env.E2E_VIDEO_PATH;
  if (!videoPath) throw new Error('E2E_VIDEO_PATH is required');

  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await page.locator('input[name="reported_attendance"]').fill('12');
  await page.getByRole('button', { name: 'Analyse video' }).click();

  await expect(page.getByText('Created', { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Reported attendance 12/)).toBeVisible({ timeout: 10_000 });

  const attendanceCase = page.locator('.case').first();
  const evidence = attendanceCase.getByRole('link', { name: 'Open evidence' });
  await expect(evidence).toBeVisible();
  const href = await evidence.getAttribute('href');
  expect(href).toBeTruthy();
  const evidenceResponse = await page.request.get(href!);
  expect(evidenceResponse.ok()).toBeTruthy();

  await attendanceCase.getByRole('button', { name: 'Review' }).click();
  await expect(attendanceCase.getByText('under review')).toBeVisible({ timeout: 10_000 });

  await expect(page.getByText(/Cached detections are a stage-safe fallback/i)).toBeVisible();
  await expect(page.getByText('Electrical Training Panel')).toBeVisible();

  await page.locator('input[name="infra_file"]').setInputFiles(path.resolve(videoPath));
  await page.getByRole('button', { name: 'Analyse infrastructure evidence' }).click();
  await expect(page.getByText(/Construction Electrician visual manifest exception/)).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('infrastructure compliance')).toBeVisible();
  await expect(page.getByText('APPARENTLY ACTIVE')).toBeVisible({ timeout: 10_000 });

  const infraCase = page.locator('.case').first();
  await expect(infraCase.getByRole('link', { name: 'Open evidence' })).toBeVisible();
});
