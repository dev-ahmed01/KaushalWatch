import { test, expect } from '@playwright/test';

test('R5 chatbox exchanges persisted text across two real demo roles', async ({page})=>{
  await page.goto('/chatbox?centre=DEMO-KA-104&person=demo-head-DEMO-KA-104');
  await expect(page.getByRole('heading',{name:'Chatbox',exact:true})).toBeVisible();
  await expect(page.getByRole('region',{name:'Chatbox workspace'})).toBeVisible();
  const text='Follow up on roster ' + Date.now();
  await page.getByRole('textbox',{name:'Type a text message'}).fill(text);
  await page.getByRole('button',{name:'Send message'}).click();
  await expect(page.getByLabel('Message history').getByText(text)).toBeVisible();
  await page.getByRole('combobox',{name:'Demo role'}).selectOption('demo-head-DEMO-KA-104');
  await expect(page.getByLabel('Message history').getByText(text)).toBeVisible();
  const reply='Acknowledged '+Date.now();
  await page.getByRole('textbox',{name:'Type a text message'}).fill(reply);
  await page.getByRole('button',{name:'Send message'}).click();
  await expect(page.getByLabel('Message history').getByText(reply)).toBeVisible();
  await page.reload();
  await page.getByRole('combobox',{name:'Demo role'}).selectOption('demo-head-DEMO-KA-104');
  await expect(page.getByLabel('Message history').getByText(text)).toBeVisible();
  await expect(page.getByLabel('Message history').getByText(reply)).toBeVisible();
});
