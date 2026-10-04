import { test, expect } from '@playwright/test';
import path from 'path';

test('command centre handles detector fallback, case lifecycle and evidence integrity', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByText('KaushalWatch', { exact: true })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
  const primaryNav = page.getByRole('navigation', { name: 'Primary navigation' });

  // Demo walkthrough intentionally opens on Infrastructure first.
  await expect(page.getByText(/stage-safe visual manifest/i)).toBeVisible();
  await expect(page.getByText('One centre · three checkpoints')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reset walkthrough' })).toBeVisible();
  await expect(page.locator('select[name="demo_profile"]')).toHaveValue('compliant');
  await expect(page.getByText(/Manifest counts use stage-safe demo telemetry/i)).toBeVisible();

  // Edge sync zero should read as an idle/expected state, not a fault.
  await primaryNav.getByRole('button', { name: /Overview/ }).click();
  const edgeMetric = page.locator('.kpi').filter({ hasText: 'Edge sync' });
  await expect(edgeMetric.getByText('0 synced', { exact: true })).toBeVisible();
  await expect(edgeMetric.getByText(/Idle · no pending events/i)).toBeVisible();

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

  const videoPath = process.env.E2E_VIDEO_PATH;
  if (!videoPath) throw new Error('E2E_VIDEO_PATH is required');

  // Core CI intentionally has no YOLO dependency. The UI must present fallback
  // as unavailable rather than silently reporting zero occupancy.
  await primaryNav.getByRole('button', { name: /Attendance/ }).click();
  await expect(page.locator('input[name="reported_attendance"]')).toHaveValue('3');
  await page.getByLabel('Active centre ID').fill('DEMO-KA-205');
  await page.getByLabel('Active batch ID').fill('CTX-BATCH-01');
  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await page.locator('input[name="reported_attendance"]').fill('12');
  await page.getByRole('button', { name: 'Run attendance verification' }).click();

  await expect(
    page.getByRole('heading', { name: 'Detector unavailable / fallback mode' })
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Attendance decision withheld')).toBeVisible();
  await expect(page.getByText('Unavailable', { exact: true })).toBeVisible();
  await expect(page.getByText('Could not verify', { exact: true })).toBeVisible();

  // Practical-work configuration upload is optional; bundled profiles are present.
  await primaryNav.getByRole('button', { name: /Practical work/ }).click();
  await expect(page.locator('input[name="centre_id"]')).toHaveValue('DEMO-KA-205');
  await expect(page.locator('input[name="batch_id"]')).toHaveValue('CTX-BATCH-01');
  await expect(page.getByRole('button', { name: 'Authorized activity' })).toBeVisible();
  await page.getByRole('button', { name: 'Unauthorized alert' }).click();
  await expect(page.locator('select[name="zone_profile"]')).toHaveValue('unauthorized');
  await page.getByRole('button', { name: 'Authorized activity' }).click();
  await expect(page.locator('select[name="zone_profile"]')).toHaveValue('authorized');
  const zoneInput = page.locator('input[name="zones_file"]');
  await expect(zoneInput).not.toHaveAttribute('required', '');
  await expect(page.getByText(/Work-zone JSON · optional/i)).toBeVisible();
  await expect(page.locator('select[name="zone_profile"]')).toHaveValue('authorized');
  await expect(page.getByText('Practical-work runtime unavailable', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run practical-work verification' })).toBeDisabled();

  // Infrastructure remains the clearest live walkthrough and creates a review case.
  await primaryNav.getByRole('button', { name: /Infrastructure/ }).click();
  await expect(page.locator('input[name="centre_id"]')).toHaveValue('DEMO-KA-205');
  await expect(page.locator('input[name="batch_id"]')).toHaveValue('CTX-BATCH-01');
  await page.locator('select[name="demo_profile"]').selectOption('discrepancy');
  await page.locator('input[name="infra_file"]').setInputFiles(path.resolve(videoPath));
  await page.getByRole('button', { name: 'Run infrastructure verification' }).click();
  await expect(
    page.getByRole('heading', { name: 'Visual manifest exception created' })
  ).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('Exception · review', { exact: true })).toBeVisible();

  // Re-run the same evidence to exercise the independent duplicate-evidence signal.
  await page.getByRole('button', { name: 'Run infrastructure verification' }).click();
  await expect(
    page.getByRole('heading', { name: 'Visual manifest exception created' })
  ).toBeVisible({ timeout: 20_000 });

  await primaryNav.getByRole('button', { name: /Review queue/ }).click();
  await expect(page.getByText(/Showing only cases for DEMO-KA-205 \/ CTX-BATCH-01/i)).toBeVisible();
  await expect(page.getByText(/pending$/).first()).toBeVisible();
  await expect(page.locator('.caseCard').filter({ hasText: 'DEMO-KA-104' })).toHaveCount(0);

  const infraCases = page.locator('.caseCard').filter({ hasText: 'infrastructure compliance' });
  await expect(infraCases.first()).toBeVisible();

  const duplicateCase = infraCases.filter({ hasText: 'Evidence integrity signal' }).first();
  await expect(duplicateCase).toBeVisible();
  await expect(duplicateCase.getByText(/Possible duplicate evidence detected/i)).toBeVisible();

  const pendingBefore = await page.locator('.queueCount').first().textContent();

  const firstInfraCase = infraCases.first();
  await firstInfraCase.getByRole('button', { name: 'Inspect evidence' }).click();
  await expect(firstInfraCase.getByText('EVIDENCE SNAPSHOT')).toBeVisible();
  await expect(firstInfraCase.getByRole('img', { name: /Evidence for CASE-/ })).toBeVisible();

  // Final decisions require an auditable officer rationale.
  const confirmButton = firstInfraCase.getByRole('button', { name: 'Confirm exception' });
  await expect(confirmButton).toBeDisabled();
  await firstInfraCase.getByPlaceholder(/What did you verify/i).fill(
    'Reviewed the visual manifest evidence and confirmed the persistent gap.'
  );
  await expect(confirmButton).toBeEnabled();

  // Resolve one pending case and verify it leaves the live priority queue.
  await confirmButton.click();
  await expect(page.getByText('RESOLVED / HISTORY')).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('.resolvedCase').first()).toBeVisible();
  await expect(page.getByText(/Reviewed the visual manifest evidence/i)).toBeVisible();

  const pendingAfter = await page.locator('.queueCount').first().textContent();
  expect(pendingAfter).not.toBe(pendingBefore);

  const evidencePack = infraCases.first().getByRole('link', { name: 'Evidence pack' });
  if (await evidencePack.count()) {
    const packHref = await evidencePack.getAttribute('href');
    expect(packHref).toBeTruthy();
    const packResponse = await page.request.get(packHref!);
    expect(packResponse.ok()).toBeTruthy();
  }
});
