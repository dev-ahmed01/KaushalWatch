import { test, expect } from '@playwright/test';
import path from 'path';

test('command centre verifies attendance, evidence, review and infrastructure cases', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByText('KaushalWatch', { exact: true })).toBeVisible();
  await expect(page.getByText('Simulated operational records')).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Attendance/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Practical work/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Infrastructure/ })).toBeVisible();
  await expect(page.getByText('Three checks, one review workflow')).toBeVisible();
  await page.getByRole('button', { name: /Practical work/ }).click();
  await expect(page.getByText('Separate visible activity from authorization.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run practical-work verification' })).toBeVisible();
  await page.getByRole('button', { name: /Attendance/ }).click();

  const edgeSync = await page.request.post('http://127.0.0.1:8000/api/edge/sync', {
    data: {
      events: [{
        event_id: 'EDGE-E2E-001',
        event_type: 'compliance_case',
        created_at: '2026-10-03T00:00:00Z',
        payload: {
          case_type: 'attendance_discrepancy',
          raw_video_included: false
        }
      }]
    }
  });
  expect(edgeSync.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByText('Synced edge events')).toBeVisible();
  const syncedMetric = page.locator('.metric').filter({ hasText: 'Synced edge events' });
  await expect(syncedMetric.getByText('1', { exact: true })).toBeVisible();

  const videoPath = process.env.E2E_VIDEO_PATH;
  if (!videoPath) throw new Error('E2E_VIDEO_PATH is required');

  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await page.locator('input[name="reported_attendance"]').fill('12');
  await page.getByRole('button', { name: 'Run attendance verification' }).click();

  await expect(page.getByText('Persistent attendance exception')).toBeVisible({ timeout: 30_000 });
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

  await page.getByRole('button', { name: /Infrastructure/ }).click();
  await expect(page.getByText(/stage-safe visual manifest/i)).toBeVisible();
  await expect(page.getByText(/Electrical (Switchboard \/ )?Training Panel/)).toBeVisible();

  await page.locator('input[name="infra_file"]').setInputFiles(path.resolve(videoPath));
  await page.getByRole('button', { name: 'Run infrastructure verification' }).click();
  await expect(page.getByText(/visual manifest exception/)).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('infrastructure compliance')).toBeVisible();
  await expect(
    page.locator('.infraResult').getByText(/APPARENTLY (ACTIVE|INACTIVE)|UNCERTAIN/)
  ).toBeVisible({ timeout: 10_000 });

  const infraCase = page.locator('.case').first();
  await expect(infraCase.getByRole('link', { name: 'Open evidence' })).toBeVisible();
  const evidencePack = infraCase.getByRole('link', { name: 'Evidence pack' });
  await expect(evidencePack).toBeVisible();
  const packHref = await evidencePack.getAttribute('href');
  expect(packHref).toBeTruthy();
  const packResponse = await page.request.get(packHref!);
  expect(packResponse.ok()).toBeTruthy();
});
