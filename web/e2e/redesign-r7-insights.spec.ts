import {expect,test} from '@playwright/test';

test('R7 Insights has exactly one range control and correct source period',async({page})=>{
  const calls:string[]=[];
  page.on('request',r=>{if(r.url().includes('/api/insights?'))calls.push(r.url());});
  await page.goto('/insights');
  const picker=page.getByRole('combobox',{name:'Date range'});
  await expect(picker).toHaveCount(1);
  await expect(picker).toHaveValue('last_7_days');
  await expect(page.getByRole('region',{name:'Attendance comparison chart'})).toBeVisible();
  await expect(page.getByRole('region',{name:'Infrastructure exception chart'})).toBeVisible();
  await picker.selectOption('today');
  await expect(picker).toHaveValue('today');
  await expect(page.getByText(/Today · Verified source data/)).toBeVisible();
  expect(calls.some(url=>url.includes('period=today'))).toBeTruthy();
  await picker.selectOption('last_30_days');
  await expect(page.getByText(/Last 30 days · Verified source data/)).toBeVisible();
  expect(calls.some(url=>url.includes('period=last_30_days'))).toBeTruthy();
});

test('R7 optional heatmap scrolls internally at 320px',async({page})=>{
  await page.setViewportSize({width:320,height:700});
  await page.goto('/insights');
  await page.getByText('Activity across the training day').click();
  const heat=page.getByRole('region',{name:'Activity heatmap, horizontally scrollable'});
  await expect(heat).toBeVisible();
  const state=await heat.evaluate(el=>({width:el.clientWidth,content:el.scrollWidth}));
  expect(state.content).toBeGreaterThan(state.width);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});
