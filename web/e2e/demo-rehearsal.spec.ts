import { test, expect } from '@playwright/test';

test('prepared SIH demo stays deterministic and auditable after AI-first restructure', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'KaushalAI' })).toBeVisible();
  await expect(page.getByText('Centres at a glance')).toBeVisible();
  await expect(page.getByText('Bengaluru TC-04').first()).toBeVisible();

  await page.goto('/centres/DEMO-KA-104');
  await expect(page.getByRole('heading', { name: 'Bengaluru TC-04' })).toBeVisible();
  await expect(page.getByText('KaushalAI centre brief')).toBeVisible();
  await expect(page.getByText('Verification engines')).toBeVisible();
  await expect(page.getByText('Attendance', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Practical activity', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Apparent operability', { exact: true }).first()).toBeVisible();

  await page.getByRole('navigation', { name: 'Centre sections' }).getByRole('link', { name: 'Evidence', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Evidence', exact: true })).toBeVisible();
  await expect(page.getByText('Simulated evidence')).toBeVisible();
  await expect(page.getByText('1 possible duplicate')).toBeVisible();
  await expect(page.getByAltText('Retained compliance evidence')).toBeVisible();
  await page.getByText('Technical details', { exact: true }).first().click();
  await expect(page.getByText(/SHA-256:/)).toBeVisible();

  await page.goto('/centres/DEMO-KA-104');
  await page.getByText('Review attendance evidence', { exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Attendance discrepancy' })).toBeVisible();
  await expect(page.getByAltText('Retained compliance evidence')).toBeVisible();

  await page.getByPlaceholder('Record the reason for your decision…').fill('Reviewed during SIH demo rehearsal.');
  await page.getByRole('button', { name: 'Confirm discrepancy', exact: true }).click();
  await expect(page.getByText('Case confirmed for officer follow-up.')).toBeVisible();

  await page.getByText(/Audit trail · 2 events/).click();
  await expect(page.getByText(/open → under review/)).toBeVisible();
  await expect(page.getByText(/under review → confirmed/)).toBeVisible();

  await page.reload();
  await expect(page.getByText('CONFIRMED', { exact: true })).toBeVisible();
  await expect(page.getByText('A final officer outcome has been recorded. The evidence and audit trail remain available.')).toBeVisible();

  await page.goto('/reports?centre=DEMO-KA-104');
  await expect(page).toHaveURL(/\/insights$/);
  await expect(page.getByRole('heading', { name: 'Insights' })).toBeVisible();

  const reportPdf = await page.request.get(
    'http://127.0.0.1:8000/api/centres/DEMO-KA-104/report.pdf?period=7d',
  );
  expect(reportPdf.ok()).toBeTruthy();
  expect(reportPdf.headers()['content-type']).toContain('application/pdf');
  const reportBytes = await reportPdf.body();
  expect(reportBytes.subarray(0, 8).toString('latin1')).toBe('%PDF-1.4');
  const reportText = reportBytes.toString('latin1');
  expect(reportText).toContain('Data: SIMULATED PROTOTYPE RECORDS');
  expect(reportText).toContain('Overall verification: NEEDS REVIEW');
  expect(reportText).toContain('Attendance: NEEDS REVIEW');

  const uncertainPdf = await page.request.get(
    'http://127.0.0.1:8000/api/centres/DEMO-KA-207/report.pdf?period=7d',
  );
  expect(uncertainPdf.ok()).toBeTruthy();
  const uncertainText = (await uncertainPdf.body()).toString('latin1');
  expect(uncertainText).toContain('Overall verification: UNCERTAIN');
  expect(uncertainText).toContain('Attendance: UNCERTAIN');
});
