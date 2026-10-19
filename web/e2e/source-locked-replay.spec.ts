import {test,expect} from '@playwright/test';

test('replay endpoint admits matching procedural recordings only',async({page})=>{
  const response=await page.request.get('/api/demo/replay');
  expect(response.status()).toBe(200);
  const data=await response.json();
  expect(data.schema).toBe('KW_SOURCE_LOCKED_REPLAY_V1');
  expect(data.status).toBe('ready');
  expect(data.private_video_available).toBe(false);
  expect(data.physical_camera_accuracy_qualified).toBe(false);
  expect(data.clips).toHaveLength(3);
  for(const clip of data.clips){
    expect(clip.status).toBe('verified');
    expect(clip.sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(clip.source_url).toMatch(/^\/camera-trust\/[a-z-]+\.mp4$/);
    expect(clip.receipt_status).toBe('absent');
  }
});

test('source-locked recorded replay and cue navigation work',async({page})=>{
  await page.goto('/demo/mission');
  const replay=page.getByRole('region',{name:'Source-locked replay'});
  await expect(replay.getByText('Manifest hash matched')).toBeVisible();
  const video=replay.locator('video');
  await expect(video).toHaveAttribute('src',/training-bay\.mp4/);
  await expect(replay.getByRole('button',{name:'Inspect quality event'})).toBeEnabled();
  await replay.getByRole('button',{name:'Inspect quality event'}).click();
  await expect(replay.getByText('Inside the quality-change interval')).toBeVisible();
  const elapsed=await video.evaluate((v:HTMLVideoElement)=>v.currentTime);
  expect(elapsed).toBeGreaterThan(8);
  expect(elapsed).toBeLessThan(10);
  await replay.getByRole('button',{name:'Workshop floor'}).click();
  await expect(video).toHaveAttribute('src',/workshop-floor\.mp4/);
  await expect(replay.getByText('Visibility change')).toBeVisible();
  await expect(replay.getByText(/No matching model receipt/)).toBeVisible();
});

test('failed media verification cannot render recorded footage',async({page})=>{
  await page.route('**/api/demo/replay',r=>r.fulfill({status:503,
    contentType:'application/json',body:'{"schema":"KW_SOURCE_LOCKED_REPLAY_V1","status":"blocked"}'}));
  await page.goto('/demo/mission');
  const replay=page.getByRole('region',{name:'Source-locked replay'});
  await expect(replay.getByRole('alert')).toContainText('No replay, detection or camera conclusion is shown');
  await expect(replay.locator('video')).toHaveCount(0);
  await expect(replay.getByRole('button',{name:'Retry verification'})).toBeVisible();
});

test('recorded replay fits mobile viewport',async({page})=>{
  await page.setViewportSize({width:375,height:812});
  await page.goto('/demo/mission');
  await expect(page.getByText('Manifest hash matched')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)).toBe(false);
});
