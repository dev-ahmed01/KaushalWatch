import { expect, test } from '@playwright/test';

test('R3 issue selection opens in-page detail rather than a modal', async ({page}) => {
  await page.goto('/issues');
  await expect(page.getByRole('heading', {name:'Issues', exact:true})).toBeVisible();
  const queue = page.getByRole('region', {name:'Issue queue'});
  await expect(queue).toBeVisible();
  await queue.getByRole('button', {name:/Review infrastructure exception|Verify camera evidence|Review attendance evidence/}).first().click();
  await expect(page).toHaveURL(/\/issues\?issue=/);
  await expect(page.getByRole('region', {name:'Selected issue details'})).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('tab', {name:'Communication'}).click();
  await expect(page.getByRole('link', {name:/Open in Chatbox/})).toHaveAttribute('href',/\/chatbox\?centre=.*&issue=/);
});

test('R3 evidence metadata loads only after explicit tab selection', async ({page}) => {
  const requests:string[] = [];
  page.on('request', request => { if (request.url().includes('/evidence-pack')) requests.push(request.url()); });
  await page.goto('/issues');
  await expect(page.getByRole('region', {name:'Selected issue details'})).toBeVisible();
  expect(requests).toHaveLength(0);
  await page.getByRole('tab', {name:'Evidence'}).click();
  await expect(page.getByText(/Metadata is retrieved only after opening this tab/)).toBeVisible();
});

test('R3 works as a focused pane on narrow screens', async ({page}) => {
  await page.setViewportSize({width:375,height:740});
  await page.goto('/issues');
  const queue=page.getByRole('region',{name:'Issue queue'});
  await queue.getByRole('button').first().click();
  await expect(page.getByRole('region',{name:'Selected issue details'})).toBeVisible();
  await page.getByRole('button',{name:'Back to issue list'}).click();
  await expect(queue).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});
