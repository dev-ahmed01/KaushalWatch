import {expect,test} from '@playwright/test';

test.skip(process.env.NEXT_PUBLIC_KAUSHALWATCH_PUBLIC_SHOWCASE!=='true','Runs only against the isolated public-showcase build');

test('public cloud mode serves only the recorded synthetic studio and approved sources',async({page,request})=>{
  await page.goto('/');
  await expect(page).toHaveURL(/\/demo\/studio$/);
  await expect(page.getByRole('heading',{name:'From recording to officer action.'})).toBeVisible();
  await expect(page.getByText('Simulated demo · scripted analysis')).toBeVisible();
  const replay=await request.get('/api/demo/replay');
  expect(replay.status()).toBe(200);
  const data=await replay.json();
  expect(data.kind).toBe('synthetic_quality_demonstration');
  expect(data.clips.map((x:{id:string})=>x.id)).toEqual(['training-bay','workshop-floor','east-corridor']);
  for(const clip of data.clips as Array<{source_url:string;sha256:string}>){
    const content=await request.get(clip.source_url);
    expect(content.status()).toBe(200);
    const buffer=await content.body();
    const {createHash}=await import('node:crypto');
    expect(createHash('sha256').update(buffer).digest('hex')).toBe(clip.sha256);
  }
  await expect(page.getByRole('region',{name:'Recorded scene playback'})).toContainText('SHA-256 source verified');
  const blocked=await request.get('/api/assistant/chat');
  expect(blocked.status()).toBe(404);
  const cases=await request.get('/api/cases');
  expect(cases.status()).toBe(404);
  await page.goto('/chatbox');
  await expect(page).toHaveURL(/\/demo\/studio$/);
});
