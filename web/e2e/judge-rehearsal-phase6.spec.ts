import {test,expect} from '@playwright/test';

test('60-second route selects exact four trusted scenarios with manual timing',async({page})=>{
 await page.goto('/demo/mission');
 const rail=page.getByRole('region',{name:'Judge rehearsal'});
 await expect(rail.getByText('Planned speaking windows · manual navigation, not a timer')).toBeVisible();
 await rail.getByRole('button',{name:'60 sec'}).click();
 await expect(rail.getByRole('button',{name:'60 sec'})).toHaveAttribute('aria-pressed','true');
 await expect(rail.getByRole('status')).toContainText('00:00–00:15');
 await rail.getByRole('button',{name:'Next cue'}).click();
 await expect(page.getByRole('heading',{name:'Camera is obstructed'})).toBeVisible();
 await expect(page.getByText('Withheld · not zero')).toBeVisible();
 await expect(rail.getByRole('status')).toContainText('00:15–00:29');
 await rail.getByRole('button',{name:'Next cue'}).click();
 await expect(page.getByRole('heading',{name:'Equipment visibility'})).toBeVisible();
 await rail.getByRole('button',{name:'Next cue'}).click();
 await expect(page.getByRole('heading',{name:'No exception needed'})).toBeVisible();
 await expect(rail.getByRole('status')).toContainText('00:43–01:00');
 await expect(rail.getByRole('button',{name:'Next cue'})).toBeDisabled();
 await rail.getByRole('button',{name:'Restart judge route'}).click();
 await expect(page.getByRole('heading',{name:'Attendance gap'})).toBeVisible();
});

test('full judge route has 3:20 planned coverage and includes officer audit',async({page})=>{
 await page.goto('/demo/mission');
 const rail=page.getByRole('region',{name:'Judge rehearsal'});
 await expect(rail.getByRole('button',{name:'3m 20s'})).toHaveAttribute('aria-pressed','true');
 await expect(rail.getByRole('button',{name:/Chapter 6 Offline/})).toBeVisible();
 await rail.getByRole('button',{name:/Chapter 4 Officer/}).click();
 await expect(page.getByRole('heading',{name:'Attendance gap'})).toBeVisible();
 await expect(rail.getByRole('status')).toContainText('01:55–02:40');
 await expect(page.getByRole('region',{name:'Officer evidence chain'})).toBeVisible();
 await rail.getByRole('button',{name:/Chapter 6 Offline/}).click();
 await expect(rail.getByRole('status')).toContainText('02:58–03:20');
});

test('presenter shortcuts remain keyboard and mobile accessible without side scroll',async({page})=>{
 await page.setViewportSize({width:375,height:812});
 await page.goto('/demo/mission');
 const rail=page.getByRole('region',{name:'Judge rehearsal'});
 await rail.getByRole('button',{name:'60 sec'}).focus();
 await page.keyboard.press('Enter');
 await expect(rail.getByRole('button',{name:'60 sec'})).toHaveAttribute('aria-pressed','true');
 await rail.getByRole('button',{name:'Next cue'}).focus();
 await page.keyboard.press('Enter');
 await expect(page.getByRole('heading',{name:'Camera is obstructed'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)).toBe(false);
});
