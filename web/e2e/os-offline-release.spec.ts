import { createHash } from 'node:crypto';
import { expect, test } from '@playwright/test';

test('device offline status is explicit, reversible and does not claim live data',async ({page,context})=>{
  await page.goto('/actions');
  await expect(page.getByRole('heading',{name:'Action queue'})).toBeVisible();
  await context.setOffline(true);
  const banner=page.getByTestId('device-offline');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('live centre updates and officer decisions need a connection');
  await expect(banner).toContainText('Saved sample recordings');
  await context.setOffline(false);
  await expect(banner).toHaveCount(0);
});

test('read-only overview modules offer an explicit retry after network failure',async ({page})=>{
  const items=[
    {route:'/',source:'**/api/kaushalai/brief**',failure:'Some authorised records could not be loaded.',ready:'Training centre status'},
    {route:'/centres',source:'**/api/centres',failure:'Live centre records are unavailable.',ready:'Centres ('},
    {route:'/actions',source:'**/api/actions**',failure:'The grounded action queue is temporarily unavailable.',ready:'Action queue'},
    {route:'/insights',source:'**/api/insights**',failure:'Grounded insights are temporarily unavailable.',ready:'Centre verification reports'},
  ];
  for(const item of items){
    let requests=0;
    await page.route(item.source,async route=>{
      requests++;
      if(requests===1)await route.abort();
      else await route.continue();
    });
    await page.goto(item.route);
    await expect(page.getByText(item.failure,{exact:false}).first()).toBeVisible();
    await page.getByRole('button',{name:'Retry',exact:true}).click();
    await expect(page.getByText(item.failure,{exact:false})).toHaveCount(0);
    await expect(page.getByText(item.ready,{exact:false}).first()).toBeVisible();
    expect(requests).toBeGreaterThanOrEqual(2);
    await page.unroute(item.source);
  }
});

test('centre record identity remains sourced if intelligence service goes down',async ({page})=>{
  await page.route('**/api/centres/DEMO-KA-104/intelligence**',route=>route.abort());
  await page.goto('/centres/DEMO-KA-104');
  await expect(page.getByRole('heading',{name:'Bengaluru TC-04'})).toBeVisible();
  await expect(page.getByRole('region',{name:'Source and connectivity'})).toContainText('Low-bandwidth centre');
  await expect(page.getByRole('region',{name:'Source and connectivity'})).toContainText('not a live video or sync indicator');
  await expect(page.getByRole('alert').filter({hasText:'Live centre intelligence is unavailable.'})).toBeVisible();
  await expect(page.getByText('Simulated centre metadata')).toHaveCount(0);
  await page.unroute('**/api/centres/DEMO-KA-104/intelligence**');
  await page.getByRole('button',{name:'Retry',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Verification snapshot'})).toBeVisible();
  await expect(page.getByRole('alert').filter({hasText:'Live centre intelligence is unavailable.'})).toHaveCount(0);
});

test('unknown centre never inherits the Bengaluru record when identity API fails',async ({page})=>{
  await page.route('**/api/centres/NOT-A-CENTRE',route=>route.abort());
  await page.goto('/centres/NOT-A-CENTRE');
  await expect(page.getByRole('heading',{name:'Centre record unavailable'})).toBeVisible();
  await expect(page.getByText('No verified centre identity or measurements have been substituted.')).toBeVisible();
  await expect(page.getByText('Bengaluru TC-04')).toHaveCount(0);
});

test('bundled recordings have exact versioned SHA-256 provenance and no source CCTV',async ({request,page})=>{
  const manifestResponse=await request.get('/camera-trust/manifest.json');
  expect(manifestResponse.ok()).toBeTruthy();
  const manifest=await manifestResponse.json();
  expect(manifest.schema).toBe('KW_SUBMISSION_SAMPLE_MEDIA_V1');
  expect(manifest.provenance).toBe('PROCEDURALLY_GENERATED_RECORDING_NOT_REAL_CCTV');
  const stems=['east-corridor','training-bay','workshop-floor'];
  expect(Object.keys(manifest.clips).sort()).toEqual(stems);
  for(const stem of stems){
    const response=await request.get('/camera-trust/'+stem+'.mp4');
    expect(response.ok()).toBeTruthy();
    const video=await response.body();
    expect(video.length).toBeGreaterThan(500);
    expect(video.length).toBeLessThan(128*1024);
    expect(createHash('sha256').update(video).digest('hex')).toBe(manifest.clips[stem].sha256);
  }
  await page.goto('/centres/DEMO-KA-104/camera-trust');
  await expect(page.getByText('PLAYBACK')).toBeVisible();
  await expect(page.getByRole('heading',{name:'Camera Trust'})).toBeVisible();
});

test('mobile offline banner and operator modules stay within the viewport',async ({page,context})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/centres/DEMO-KA-104');
  await context.setOffline(true);
  await expect(page.getByTestId('device-offline')).toBeVisible();
  const dimensions=await page.evaluate(()=>({
    content:document.documentElement.scrollWidth,
    viewport:document.documentElement.clientWidth,
  }));
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport+1);
  await context.setOffline(false);
});
