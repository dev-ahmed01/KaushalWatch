import { test, expect } from '@playwright/test';
import path from 'path';

test('video upload creates a compliance case and officer can review it', async ({ page }) => {
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

  const newestCase = page.locator('.case').first();
  await newestCase.getByRole('button', { name: 'Review' }).click();
  await expect(newestCase.getByText('under review')).toBeVisible({ timeout: 10_000 });

  await expect(page.getByText(/cached detections on a demo configuration/i)).toBeVisible();
  await expect(page.getByText('Electrical Training Panel')).toBeVisible();
});
