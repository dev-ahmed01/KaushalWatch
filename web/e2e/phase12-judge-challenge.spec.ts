import {expect,test} from '@playwright/test';

test('controlled judge route ends with correct quiet decision, not a fabricated review case',async({page})=>{
 await page.goto('/demo/mission');
 const rail=page.getByRole('region',{name:'Judge rehearsal'});
 await rail.getByRole('button',{name:'60 sec'}).click();
 await expect(page.getByRole('heading',{name:'Attendance gap'})).toBeVisible();
 await rail.getByRole('button',{name:'Next cue'}).click();
 await expect(page.getByRole('heading',{name:'Camera is obstructed'})).toBeVisible();
 await expect(page.getByText('Withheld · not zero')).toBeVisible();
 await rail.getByRole('button',{name:'Next cue'}).click();
 await expect(page.getByRole('heading',{name:'Equipment visibility'})).toBeVisible();
 await page.getByText('Why the evidence quality gate matters').click();
 await expect(page.getByText('Not visible is not proven absent',{exact:false})).toBeVisible();
 await rail.getByRole('button',{name:'Next cue'}).click();
 await expect(page.getByRole('heading',{name:'No exception needed'})).toBeVisible();
 await expect(page.getByRole('region',{name:'Officer evidence chain'})).toContainText(
  'Normal control: no exception case is required for this authored example.');
 await expect(page.getByText('Fraud confirmed')).toHaveCount(0);
 await expect(rail.getByRole('button',{name:'Next cue'})).toBeDisabled();
 await rail.getByRole('button',{name:'Restart judge route'}).click();
 await expect(page.getByRole('heading',{name:'Attendance gap'})).toBeVisible();
});

test('judge route negative-control outcome survives narrow mobile display',async({page})=>{
 await page.setViewportSize({width:375,height:812});
 await page.goto('/demo/mission');
 await page.getByRole('button',{name:/No exception needed/}).click();
 await expect(page.getByRole('region',{name:'Officer evidence chain'})).toContainText(
  'no exception case is required');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
