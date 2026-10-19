import { expect, test } from '@playwright/test';

test('centre cockpit uses exact case or analysis facts and links to the source workflow',async ({page})=>{
  await page.goto('/centres/DEMO-KA-104');
  const cockpit=page.getByRole('region',{name:'Centre verification cockpit'});
  await expect(cockpit.getByRole('heading',{name:'Verification snapshot'})).toBeVisible();
  await expect(cockpit.getByRole('link',{name:'Attendance verification details'})).toContainText('28');
  await expect(cockpit.getByRole('link',{name:'Attendance verification details'})).toContainText('19');
  await expect(cockpit.getByRole('link',{name:'Attendance verification details'})).toContainText('Simulated');
  await expect(cockpit.getByRole('link',{name:'Equipment verification details'})).toContainText('No trusted comparison');
  await expect(cockpit.getByRole('link',{name:'Practical activity'})).toContainText('4');
  await expect(cockpit.getByRole('link',{name:'Camera & evidence'})).toContainText('2');
  await cockpit.getByRole('link',{name:'Review next'}).click();
  await expect(page).toHaveURL(/\/cases\/SIM-KA-104-ATT$/);
});

test('camera trust failure abstains from attendance/equipment observations',async ({page})=>{
  await page.goto('/centres/DEMO-KA-207');
  const cockpit=page.getByRole('region',{name:'Centre verification cockpit'});
  const attendance=cockpit.getByRole('link',{name:'Attendance verification details'});
  await expect(attendance).toContainText('No trusted comparison');
  await expect(attendance).not.toContainText('19');
  await expect(cockpit.getByRole('link',{name:'Equipment verification details'})).toContainText('No trusted comparison');
  await expect(cockpit.getByRole('link',{name:'Inspect evidence'})).toHaveAttribute('href','/centres/DEMO-KA-207/evidence');
});

test('centre without analysis never borrows another site observations',async ({page})=>{
  await page.goto('/centres/DEMO-KA-601');
  const cockpit=page.getByRole('region',{name:'Centre verification cockpit'});
  await expect(cockpit.getByRole('link',{name:'Attendance verification details'})).toContainText('No trusted comparison');
  await expect(cockpit.getByRole('link',{name:'Equipment verification details'})).toContainText('No trusted comparison');
  await expect(cockpit.getByRole('link',{name:'Practical activity'})).toContainText('No trusted activity data');
});

test('centre verification cockpit is usable at 390 px',async ({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/centres/DEMO-KA-104');
  const cockpit=page.getByRole('region',{name:'Centre verification cockpit'});
  await expect(cockpit.getByRole('heading',{name:'Verification snapshot'})).toBeVisible();
  await expect(cockpit.getByRole('link',{name:'Equipment verification details'})).toBeVisible();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
