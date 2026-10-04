import { test, expect } from '@playwright/test';
import fs from 'fs';

const centre = 'DEMO-KA-104';
const shots = [
  { slug: '01-network-overview', path: '/', heading: 'Training Centre Network' },
  { slug: '02-centres-directory', path: '/centres', heading: 'Training Centres' },
  { slug: '03-centre-overview', path: `/centres/${centre}`, heading: 'Bengaluru TC-04' },
  { slug: '04-analysis-launcher', path: `/centres/${centre}/analysis`, heading: 'Centre Analysis' },
  { slug: '05-attendance-empty', path: `/centres/${centre}/attendance`, heading: 'Attendance Verification' },
  { slug: '06-practical-empty', path: `/centres/${centre}/practical`, heading: 'Practical Work Verification' },
  { slug: '07-infrastructure', path: `/centres/${centre}/infrastructure`, heading: 'Infrastructure & Asset Verification' },
  { slug: '08-review-queue', path: `/centres/${centre}/review`, heading: 'Review Queue' },
  { slug: '09-final-outcome', path: `/centres/${centre}/outcome`, heading: 'Final Review Outcome' },
  { slug: '10-history', path: `/centres/${centre}/history`, heading: 'Analysis History' },
  { slug: '11-escalations', path: '/escalations', heading: 'Escalations & Review' },
  { slug: '12-reports', path: `/reports?centre=${centre}&period=7d`, heading: 'Compliance Reports' },
  { slug: '13-analytics', path: '/analytics', heading: 'Monitoring Analytics' },
  { slug: '14-settings', path: '/settings', heading: 'Settings & Configuration' },
];

test('capture every primary KaushalWatch screen for visual review', async ({ page }) => {
  fs.mkdirSync('visual-audit', { recursive: true });
  await page.setViewportSize({ width: 1536, height: 900 });

  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', error => pageErrors.push(error.message));

  for (const shot of shots) {
    await page.goto(shot.path);
    await expect(page.getByRole('heading', { name: shot.heading }).first()).toBeVisible({ timeout: 20_000 });
    await page.waitForTimeout(500);
    await page.screenshot({ path: `visual-audit/${shot.slug}.png`, fullPage: true });
  }

  fs.writeFileSync(
    'visual-audit/browser-errors.json',
    JSON.stringify({ consoleErrors, pageErrors }, null, 2)
  );
  expect(pageErrors, 'uncaught browser page errors').toEqual([]);
});

test('network, directory, reports, history, assistant and settings controls respond', async ({ page }) => {
  await page.setViewportSize({ width: 1536, height: 900 });

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Training Centre Network' })).toBeVisible();
  await page.getByRole('button', { name: /Requires Review/ }).click();
  await expect(page.locator('.dataTable tbody tr').first()).toBeVisible();

  await page.goto('/centres');
  const search = page.getByPlaceholder('Search centre, district or batch…');
  await search.fill('Mysuru');
  await expect(page.getByRole('link', { name: /Mysuru TC-12/ })).toBeVisible();
  await search.fill('');

  await page.goto(`/centres/${centre}`);
  await expect(page.getByRole('link', { name: 'Recent Analysis' })).toHaveAttribute('href', `/centres/${centre}/history`);
  await expect(page.getByRole('link', { name: 'Start Analysis' })).toHaveAttribute('href', `/centres/${centre}/analysis`);

  const assistantQuestion = page.getByRole('button', { name: 'What needs attention?' });
  await assistantQuestion.click();
  await expect(page.locator('.neoChat.ai')).toBeVisible({ timeout: 15_000 });

  await page.goto(`/centres/${centre}/history`);
  const period = page.locator('.headerSelect');
  await period.selectOption('30d');
  await expect(period).toHaveValue('30d');
  const type = page.locator('.filterBar select');
  await type.selectOption('infrastructure');
  await expect(type).toHaveValue('infrastructure');

  await page.goto(`/reports?centre=${centre}&period=7d`);
  await page.getByRole('button', { name: 'Last 30 days' }).click();
  await expect(page.getByRole('button', { name: 'Last 30 days' })).toHaveClass(/active/);
  await expect(page.getByText('Centre Verification Report')).toBeVisible();

  await page.goto('/settings');
  const auto = page.getByRole('checkbox').first();
  const before = await auto.isChecked();
  await auto.setChecked(!before);
  await page.getByRole('button', { name: 'Save Changes' }).click();
  await expect(page.getByRole('button', { name: /Saved/ })).toBeVisible({ timeout: 10_000 });
  await auto.setChecked(before);
  await page.getByRole('button', { name: /Save Changes|Saved/ }).click();
});
