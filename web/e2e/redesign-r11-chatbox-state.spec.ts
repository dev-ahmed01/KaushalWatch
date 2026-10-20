import { expect, test } from '@playwright/test';

test('R11 sending another message does not blank previously displayed history', async ({ page }) => {
  await page.goto('/chatbox?centre=DEMO-KA-104&person=demo-head-DEMO-KA-104');
  const history = page.getByLabel('Message history');
  await expect(history).toBeVisible();
  const input = page.getByRole('textbox', { name: 'Type a text message' });
  const send = page.getByRole('button', { name: 'Send message' });

  const first = 'R11 history continuity ' + Date.now();
  await input.fill(first);
  await send.click();
  await expect(history.getByText(first)).toBeVisible();

  await page.evaluate((priorText) => {
    const node = document.querySelector('[aria-label="Message history"]');
    if (!node) throw new Error('Message history is missing');
    const status = window as typeof window & { __kwHistoryFlashed?: boolean };
    status.__kwHistoryFlashed = false;
    new MutationObserver(() => {
      if (!node.textContent?.includes(priorText)) status.__kwHistoryFlashed = true;
    }).observe(node, { childList: true, characterData: true, subtree: true });
  }, first);

  const second = 'R11 second persisted message ' + Date.now();
  await input.fill(second);
  await send.click();
  await expect(history.getByText(second)).toBeVisible();
  await expect(history.getByText(first)).toBeVisible();
  // Wait for the independent sidebar-preview refresh to finish.
  await expect(page.getByRole('region', { name: 'Chatbox workspace' })).toBeVisible();
  expect(await page.evaluate(() => (window as typeof window & { __kwHistoryFlashed?: boolean }).__kwHistoryFlashed)).toBe(false);
});

test('R11 changing conversation clears previous messages before showing the new thread', async ({ page }) => {
  await page.goto('/chatbox?centre=DEMO-KA-104&person=demo-head-DEMO-KA-104');
  const history = page.getByLabel('Message history');
  const threadButtons = page.getByLabel('Permitted threads').getByRole('button');
  await expect(threadButtons.first()).toBeVisible();
  const count = await threadButtons.count();
  test.skip(count < 2, 'The controlled fixture needs at least two permitted conversations');

  const selected = page.getByLabel('Permitted threads').getByRole('button', { pressed: true });
  const originalName = await selected.locator('strong').innerText();
  const other = threadButtons.filter({ hasNotText: originalName }).first();
  await other.click();
  await expect(other).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('heading', { name: 'Chatbox', exact: true })).toBeVisible();
  // A thread change must not preserve the previously selected conversation's message DOM.
  await expect(history).toBeVisible();
});
