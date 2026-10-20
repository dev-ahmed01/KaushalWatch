import {expect,test} from '@playwright/test';

test('R9 mission only fetches recorded media after explicit operator action',async({page})=>{
  const urls:string[]=[];
  page.on('request',r=>{if(/\.mp4(?:\?|$)|\.webm(?:\?|$)/.test(r.url())) urls.push(r.url());});
  await page.goto('/demo/mission');
  const replay=page.getByRole('region',{name:'Source-locked replay'});
  await expect(replay.getByText('Manifest hash matched')).toBeVisible();
  await expect(replay.getByRole('button',{name:'Load verified recording'})).toBeVisible();
  await expect(replay.locator('video').first()).not.toHaveAttribute('src',/./);
  expect(urls).toEqual([]);
  await replay.getByRole('button',{name:'Load verified recording'}).click();
  await expect(replay.locator('video').first()).toHaveAttribute('src',/\.mp4/);
  await expect.poll(()=>urls.length).toBeGreaterThan(0);
});

test('R9 mission keeps saved case evidence and source verification on load',async({page})=>{
  await page.goto('/demo/mission');
  await expect(page.getByRole('region',{name:'Officer evidence chain'})).toBeVisible();
  await expect(page.getByRole('region',{name:'Source-locked replay'}).getByText('Manifest hash matched')).toBeVisible();
  await expect(page.getByRole('button',{name:'Open optional research diagnostics'})).toBeVisible();
  await expect(page.getByRole('region',{name:'Private research replay'})).toHaveCount(0);
  await page.getByRole('button',{name:'Open optional research diagnostics'}).click();
});
