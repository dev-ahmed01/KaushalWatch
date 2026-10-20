import {expect,test} from '@playwright/test';

test('saved officer case returns to exact judge evidence step',async({page})=>{
 await page.goto('/demo/mission');
 await page.getByRole('button',{name:'Decision',exact:true}).click();
 await expect(page.getByRole('region',{name:'Selected evidence step'})).toContainText('Review the attendance case');
 const link=page.getByRole('region',{name:'Officer evidence chain'}).getByRole('link',{name:/Review saved case/});
 await expect(link).toHaveAttribute('href','/cases/SIM-KA-104-ATT?from=mission&scene=attendance&step=3');
 await link.click();
 await expect(page).toHaveURL(/\/cases\/SIM-KA-104-ATT\?from=mission&scene=attendance&step=3/);
 await expect(page.getByText('Simulated').first()).toBeVisible();
 await page.getByRole('link',{name:'Return to walkthrough'}).click();
 await expect(page).toHaveURL(/\/demo\/mission\?scene=attendance&step=3/);
 await expect(page.getByRole('heading',{name:'Attendance gap'})).toBeVisible();
 await expect(page.getByRole('region',{name:'Selected evidence step'})).toContainText('Review the attendance case');
});

test('unavailable case ledger never becomes invented no-case evidence and can retry',async({page})=>{
 let unavailable=true;
 await page.route('**/api/cases',async route=>{
  if(unavailable)await route.abort();
  else await route.continue();
 });
 await page.goto('/demo/mission');
 const chain=page.getByRole('region',{name:'Officer evidence chain'});
 await expect(chain.getByRole('alert')).toContainText('Case records unavailable');
 await expect(chain.getByRole('link',{name:/Review saved case/})).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'Attendance gap'})).toBeVisible();
 unavailable=false;
 await chain.getByRole('button',{name:'Retry case lookup'}).click();
 await expect(chain.getByText('Controlled case')).toBeVisible();
 await expect(chain.getByRole('link',{name:/Review saved case/})).toBeVisible();
});

test('recording decoder failure does not trap mission and does not invent inference',async({page})=>{
 await page.route('**/camera-trust/*.mp4',async route=>route.abort());
 await page.goto('/demo/mission');
 const replay=page.getByRole('region',{name:'Source-locked replay'});
 await expect(replay.getByRole('button',{name:'Load verified recording'})).toBeVisible();
 await replay.getByRole('button',{name:'Load verified recording'}).click();
 await expect(replay.getByRole('alert')).toContainText('Playback and detections are disabled');
 await expect(replay.getByRole('button',{name:'Retry recording'})).toBeVisible();
 await expect(replay.getByRole('link',{name:'Continue with evidence'})).toHaveAttribute('href','#kw-evidence-trail');
 await expect(replay.getByText('Preparing verified recording…')).toHaveCount(0);
 await replay.getByRole('link',{name:'Continue with evidence'}).click();
 await expect(page).toHaveURL(/#kw-evidence-trail$/);
 await expect(page.getByRole('region',{name:'Selected evidence step'})).toBeVisible();
});

test('case record failure has retry and safe walkthrough fallback, never endless skeleton',async({page})=>{
 let unavailable=true;
 await page.route('**/api/cases/SIM-KA-104-ATT/evidence-pack',async route=>{
  if(unavailable)await route.abort();
  else await route.continue();
 });
 await page.goto('/cases/SIM-KA-104-ATT?from=mission&scene=attendance&step=2');
 await expect(page.getByRole('heading',{name:'Case evidence unavailable'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Retry saved case'})).toBeVisible();
 await expect(page.getByRole('link',{name:'Open walkthrough'})).toHaveAttribute('href','/demo/mission');
 await expect(page.getByLabel('Loading saved case')).toHaveCount(0);
 unavailable=false;
 await page.getByRole('button',{name:'Retry saved case'}).click();
 await expect(page.getByText('Simulated').first()).toBeVisible();
 await expect(page.getByRole('link',{name:'Return to walkthrough'})).toHaveAttribute('href','/demo/mission?scene=attendance&step=2');
});

test('cross-centre case return is never offered',async({page})=>{
 await page.goto('/cases/SIM-KA-104-ATT?from=mission&scene=equipment&step=2');
 await expect(page.getByText('Simulated').first()).toBeVisible();
 await expect(page.getByRole('link',{name:'Return to walkthrough'})).toHaveCount(0);
});
