import { expect, test } from '@playwright/test';

test('R4 Centre Desk uses persisted fixtures, scoped people and task changes', async ({ page }) => {
  await page.goto('/centre-desk');
  await expect(page.getByRole('heading', {name:'Centre Desk'})).toBeVisible();
  await expect(page.getByRole('region', {name:"Today's batches"})).toBeVisible();
  await expect(page.getByRole('region', {name:'Centre operational actions'})).toBeVisible();
  const people=page.getByRole('region', {name:'People to reach'});
  await expect(people.getByRole('link').first()).toHaveAttribute('href',/\/chatbox\?person=demo-/);
  const action=page.getByRole('button', {name:/Acknowledge/}).first();
  const name=await action.getAttribute('aria-label');
  await action.click();
  await expect(page.getByRole('button', {name: String(name).replace('Acknowledge','Complete')})).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', {name: String(name).replace('Acknowledge','Complete')})).toBeVisible();
});
