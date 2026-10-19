import {test,expect} from '@playwright/test';
test('controlled evidence journey has four explainable scenarios',async({page})=>{
  await page.goto('/demo/mission');
  await expect(page.getByRole('heading',{name:/A centre reports. Evidence responds./})).toBeVisible();
  await expect(page.getByText('Controlled SIH scenarios · simulated')).toBeVisible();
  await expect(page.getByRole('heading',{name:'Attendance gap'})).toBeVisible();
  await page.getByRole('button',{name:'Next evidence step'}).click();
  await expect(page.getByRole('region',{name:'Selected evidence step'})).toContainText('Construction Electrician');
  await page.getByRole('button',{name:/Camera is obstructed/}).click();
  await expect(page.getByText('Evidence insufficient').first()).toBeVisible();
  await expect(page.getByText('Withheld · not zero')).toBeVisible();
  await page.getByRole('button',{name:'Observed'}).click();
  await expect(page.getByRole('region',{name:'Selected evidence step'})).toContainText('Evidence unavailable');
  await page.getByRole('button',{name:/Equipment visibility/}).click();
  await expect(page.getByText('Not visible is not proven absent',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:/No exception needed/}).click();
  await expect(page.getByText('No exception in this scenario').first()).toBeVisible();
  await expect(page.getByText('Fraud confirmed')).toHaveCount(0);
});
test('controlled walkthrough fits mobile viewport',async({page})=>{
  await page.setViewportSize({width:375,height:812});
  await page.goto('/demo/mission');
  await expect(page.getByRole('heading',{name:/A centre reports. Evidence responds./})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)).toBe(false);
});
