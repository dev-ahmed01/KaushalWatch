import { test, expect } from '@playwright/test';

test('assistant opens only as an on-demand drawer and uses grounded starter questions', async ({ page }) => {
  await page.route('**/api/assistant/status', async route => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ enabled: true, configured: true, available: true, voice_configured: false, voice_available: false }) });
  });
  await page.route('**/api/assistant/chat', async route => {
    const request = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: `Recorded evidence answer for: ${request.message}`, session_id: 'demo-session', sources: [{ kind: 'analysis', id: 'a-1', label: 'Attendance analysis', href: '/centres/DEMO-KA-104/attendance', timestamp: null }], tool_calls: [] }) });
  });

  await page.goto('/centres/DEMO-KA-104');
  await expect(page.getByText('KaushalWatch Assistant')).toHaveCount(0);
  await page.getByRole('button', { name: 'Ask assistant' }).first().click();
  await expect(page.getByText('KaushalWatch Assistant')).toBeVisible();
  await expect(page.getByRole('button', { name: 'What happened today?' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Why was attendance flagged?' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Which equipment is repeatedly missing?' })).toBeVisible();

  await page.getByRole('button', { name: 'What happened today?' }).click();
  await expect(page.getByText('Recorded evidence answer for: What happened today?')).toBeVisible();
  await expect(page.getByText(/Grounded in 1 recorded source/)).toBeVisible();
  await page.getByRole('button', { name: 'Close assistant' }).click();
  await expect(page.getByText('KaushalWatch Assistant')).toHaveCount(0);
});

test('assistant unconfigured state stays inside the drawer', async ({ page }) => {
  await page.route('**/api/assistant/status', async route => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ enabled: true, configured: false, available: false, voice_configured: false, voice_available: false }) });
  });
  await page.goto('/centres/DEMO-KA-104');
  await page.getByRole('button', { name: 'Ask assistant' }).first().click();
  await expect(page.getByText('Assistant unavailable')).toBeVisible();
  await expect(page.getByText(/Evidence review remains available throughout KaushalWatch/)).toBeVisible();
});
