import { expect, test } from '@playwright/test';

test.use({
  permissions: ['microphone'],
  launchOptions: { args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'] },
});

test('R10 virtual microphone note can preview, persist, and play across authorised demo roles', async ({page}) => {
  await page.goto('/chatbox?centre=DEMO-KA-104&person=demo-head-DEMO-KA-104');
  await expect(page.getByRole('region',{name:'Chatbox workspace'})).toBeVisible();
  const composer=page.getByRole('region',{name:'Voice note composer'});
  await composer.getByRole('button',{name:'Record voice note'}).click();
  await expect(composer.getByRole('button',{name:'Stop voice recording'})).toBeVisible();
  await page.waitForTimeout(900); // Allow fake audio stream to emit a nonempty valid WebM chunk.
  await composer.getByRole('button',{name:'Stop voice recording'}).click();
  const preview=composer.locator('audio[aria-label="Preview voice note"]');
  await expect(preview).toBeVisible();
  await expect(preview).toHaveAttribute('src',/^blob:/);
  await composer.getByRole('button',{name:'Send voice note'}).click();
  const history=page.getByLabel('Message history');
  await expect(history.getByText(/Voice note/).last()).toBeVisible();
  await page.getByRole('combobox',{name:'Demo role'}).selectOption('demo-head-DEMO-KA-104');
  await expect(page.getByRole('button',{name:'Load voice note'}).last()).toBeVisible();
  await page.getByRole('button',{name:'Load voice note'}).last().click();
  await expect(history.locator('audio[aria-label="Play verified voice note"]').last()).toHaveAttribute('src',/^blob:/);
});
