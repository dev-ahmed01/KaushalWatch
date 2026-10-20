import {expect,test} from '@playwright/test';

test('R12 recording playback checkpoints drive all five synthetic module views and local copilot',async({page})=>{
  const providerRequests:string[]=[];
  page.on('request',req=>{
    if(/\/api\/(assistant\/chat|chatbox\/|centre-desk\/.*\/status)/.test(new URL(req.url()).pathname))
      providerRequests.push(req.url());
  });
  await page.goto('/demo/studio');
  await expect(page.getByRole('heading',{name:'From recording to officer action.'})).toBeVisible();
  await expect(page.getByText('Simulated demo · scripted analysis')).toBeVisible();
  await expect(page.getByRole('region',{name:'Recorded scene playback'})).toContainText('SHA-256 source verified');
  const video=page.getByRole('region',{name:'Recorded scene playback'}).locator('video');
  await expect(video).toHaveAttribute('src','/camera-trust/training-bay.mp4');
  await expect.poll(()=>page.evaluate(()=>document.querySelector('video')?.readyState||0)).toBeGreaterThan(0);
  await page.getByRole('button',{name:'Jump to finding'}).click();
  await expect(page.getByRole('region',{name:'KaushalAI scripted copilot'})).toContainText('28 reported trainees');
  await page.getByRole('button',{name:'Jump to review'}).click();
  await expect(page.getByRole('region',{name:'Current simulated case status'})).toContainText('Officer review');
  const tabs=page.getByRole('tablist',{name:'Demo modules'});
  await tabs.getByRole('tab',{name:'Overview'}).click();
  await expect(page.getByRole('tabpanel')).toContainText('28');
  await expect(page.getByRole('tabpanel')).toContainText('19');
  await tabs.getByRole('tab',{name:'Issues'}).click();
  await expect(page.getByRole('tabpanel')).toContainText('Synthetic issue opened');
  await tabs.getByRole('tab',{name:'Insights'}).click();
  await expect(page.getByRole('tabpanel')).toContainText('Illustrative values');
  await tabs.getByRole('tab',{name:'Centre Desk'}).click();
  await expect(page.getByRole('tabpanel')).toContainText('Today\'s synthetic follow-up');
  await tabs.getByRole('tab',{name:'Chatbox'}).click();
  await page.getByRole('textbox',{name:'Compose simulated message'}).fill('Please share the training register.');
  await page.getByRole('button',{name:'Send simulated message'}).click();
  await expect(page.getByLabel('Demo conversation history')).toContainText('Please share the training register.');
  await page.getByRole('button',{name:'Why is this flagged?'}).click();
  await expect(page.getByLabel('Scripted AI conversation')).toContainText('28 reported trainees');
  await expect(page.getByLabel('Scripted AI conversation')).toContainText('not proof of absence');
  expect(providerRequests).toEqual([]);
});

test('R12 camera trust withholds unsupported counts and scenario switch isolates prior state',async({page})=>{
  await page.goto('/demo/studio');
  await expect(page.getByRole('region',{name:'Recorded scene playback'})).toContainText('SHA-256 source verified');
  await page.getByRole('button',{name:/03 \/ recorded scenario Camera trust/}).click();
  const video=page.locator('video');
  await expect(video).toHaveAttribute('src','/camera-trust/east-corridor.mp4');
  await expect.poll(()=>page.evaluate(()=>document.querySelector('video')?.readyState||0)).toBeGreaterThan(0);
  await page.getByRole('button',{name:'Jump to review'}).click();
  await expect(page.getByRole('region',{name:'KaushalAI scripted copilot'})).toContainText('withholds attendance counts');
  await page.getByRole('tab',{name:'Overview'}).click();
  await expect(page.getByRole('tabpanel')).toContainText('Unknown');
  await page.getByRole('tab',{name:'Insights'}).click();
  await expect(page.getByRole('tabpanel')).toContainText('Observed: unknown (camera gate)');
  await page.getByRole('button',{name:/01 \/ recorded scenario Attendance gap/}).click();
  await expect(page.getByRole('region',{name:'KaushalAI scripted copilot'})).toContainText('Play the recorded scene');
  await expect(page.getByRole('tabpanel')).toContainText('—');
  await page.getByRole('button',{name:'Reset recorded demo'}).click();
  await expect(page.getByRole('region',{name:'Synthetic analysis timeline'})).toContainText('1 / 5 checkpoints');
});

test('R12 narrow screen has usable synthetic demo with no document overflow',async({page})=>{
  await page.setViewportSize({width:320,height:700});
  await page.goto('/demo/studio');
  await expect(page.getByRole('heading',{name:'From recording to officer action.'})).toBeVisible();
  await expect(page.getByRole('tablist',{name:'Demo modules'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});
