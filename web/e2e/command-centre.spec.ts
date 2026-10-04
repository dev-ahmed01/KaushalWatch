import { test, expect } from '@playwright/test';
import path from 'path';

test('multipage KaushalWatch workflow covers network, analysis, review and reports', async ({ page }) => {
  const videoPath = process.env.E2E_VIDEO_PATH;
  if (!videoPath) throw new Error('E2E_VIDEO_PATH is required');

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Training Centre Network' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Network Overview' })).toBeVisible();
  await expect(page.getByRole('link', { name: /Bengaluru TC-04/ }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Requires Review/ })).toContainText('0');
  await expect(page.getByRole('button', { name: /Camera Issues/ })).toContainText('0');
  await expect(page.getByRole('button', { name: /Verification Incomplete/ })).toContainText('6');
  await expect(page.locator('.networkMapLegend')).toBeVisible();

  // Keep the command-centre UI readable at normal presentation distance.
  const navFontSize = await page.getByRole('link', { name: 'Network Overview' }).evaluate((element) =>
    Number.parseFloat(window.getComputedStyle(element).fontSize)
  );
  const firstTableCellFontSize = await page.locator('.dataTable td').first().evaluate((element) =>
    Number.parseFloat(window.getComputedStyle(element).fontSize)
  );
  expect(navFontSize).toBeGreaterThanOrEqual(11);
  expect(firstTableCellFontSize).toBeGreaterThanOrEqual(11);

  await page.goto('/centres/DEMO-KA-104');
  await expect(page.locator('h1').filter({ hasText: 'Bengaluru TC-04' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Recent Analysis' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Start Analysis' })).toBeVisible();
  await expect(page.getByText('Ask KaushalWatch')).toBeVisible();
  await expect(page.getByText('incomplete').first()).toBeVisible();
  await expect(page.locator('.centreVisualCard')).toBeVisible();

  // No evidence must never be displayed as a compliant centre-level outcome.
  await page.goto('/centres/DEMO-KA-104/outcome');
  await expect(page.getByRole('heading', { name: 'Verification incomplete' })).toBeVisible();

  // Review Queue must inherit real workflow state rather than hard-code completed steps.
  await page.goto('/centres/DEMO-KA-104/review');
  expect(await page.locator('.neoWorkflowNode.pending').count()).toBeGreaterThanOrEqual(3);

  await page.goto('/centres/DEMO-KA-104');
  await page.getByRole('link', { name: 'Start Analysis' }).click();
  await expect(page.getByRole('heading', { name: 'Centre Analysis' })).toBeVisible();
  await expect(page.getByText('Full verification run')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start Full Analysis' })).toBeDisabled();

  // Core CI does not install YOLO. Attendance must show an explicit withheld state
  // rather than silently presenting a genuine zero occupancy.
  await page.locator('.analysisLaunchStep.blue').click();
  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await page.getByRole('button', { name: 'Analyse Attendance' }).click();
  await expect(page.getByText(/Detector unavailable/i).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/decision withheld/i)).toBeVisible();
  await expect(page.locator('.overlayMode')).toContainText(/Diagnostic detector overlay/i);
  const attendanceOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(attendanceOverflow).toBeLessThanOrEqual(2);

  // Practical work now uses the same detector abstraction as attendance. Core CI
  // can still be non-authoritative, but it must process the clip, show real work
  // zones, and withhold the conclusion explicitly instead of failing the route.
  await page.goto('/centres/DEMO-KA-104/practical');
  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await expect(page.locator('.workZoneBox').first()).toBeVisible();
  await page.getByRole('button', { name: 'Analyse Practical Work' }).click();
  await expect(page.getByText(/decision withheld/i).first()).toBeVisible({ timeout: 35_000 });
  await expect(page.getByText(/hog/i).first()).toBeVisible();
  const practicalOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(practicalOverflow).toBeLessThanOrEqual(2);

  // Infrastructure has a deliberate discrepancy demo profile and should create
  // an evidence-backed case without requiring raw advanced controls.
  await page.goto('/centres/DEMO-KA-104/infrastructure');
  await page.locator('.infraSetupCard select').selectOption('discrepancy');
  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await page.getByRole('button', { name: 'Analyse Infrastructure' }).click();
  await expect(page.getByText(/Infrastructure item not detected/i)).toBeVisible({ timeout: 25_000 });
  await expect(page.locator('.evidenceGallery img').first()).toBeVisible();
  const infrastructureOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(infrastructureOverflow).toBeLessThanOrEqual(2);

  await page.goto('/centres/DEMO-KA-104/review');
  await expect(page.getByRole('heading', { name: 'Review Queue' })).toBeVisible();
  const firstCase = page.locator('.caseListItem').first();
  await expect(firstCase).toBeVisible();
  await firstCase.click();
  await expect(page.getByRole('link', { name: 'Open Evidence Pack' })).toBeVisible();
  await expect(page.locator('.evidenceGallery img').first()).toBeVisible();

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
  await expect(page.getByText('Automatic monitoring policy')).toBeVisible();
  await expect(page.getByText('Low-bandwidth deployment')).toBeVisible();
});
