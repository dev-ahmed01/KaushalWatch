import {expect,test} from '@playwright/test';

/**
 * Phase 15 read-only judge rehearsal against real running Next + FastAPI.
 * Procedural video and seeded cases are distinct, never a field-accuracy test.
 * Both this spec and the Windows launcher use the same 4 controlled scenarios.
 */
const apiRoot=(process.env.E2E_API_BASE_URL||'http://127.0.0.1:8000').replace(/\/$/,'');
test.describe('Phase 15 controlled release rehearsal',()=>{
 test('from OS entry through replay, saved officer evidence and real PDF, then quiet normal control',async({page,request})=>{
  const writes:string[]=[];
  page.on('request',r=>{
   if(r.method()!=='GET'&&r.method()!=='HEAD'&&/\/api\/cases\/[^/]+\/review/.test(r.url()))
     writes.push(r.url());
  });
  await page.goto('/');
  const shell=page.getByRole('navigation',{name:'Primary navigation'});
  await expect(shell.getByRole('link',{name:'Overview',exact:true})).toHaveAttribute('aria-current','page');
  await page.getByRole('link',{name:/Explore the Proof of Training/}).click();
  await expect(page).toHaveURL(/\/demo\/mission$/);
  await expect(page.getByRole('heading',{name:/A centre reports. Evidence responds. An officer decides./})).toBeVisible();

  const replay=page.getByRole('region',{name:'Source-locked replay'});
  await expect(replay.getByText('Manifest hash matched')).toBeVisible();
  const identity=await request.get('/api/demo/replay');
  expect(identity.status()).toBe(200);
  const manifest=await identity.json();
  expect(manifest.status).toBe('ready');
  expect(manifest.private_video_available).toBe(false);
  expect(manifest.physical_camera_accuracy_qualified).toBe(false);
  expect(manifest.clips).toHaveLength(3);

  const officer=page.getByRole('region',{name:'Officer evidence chain'});
  await expect(officer.getByText('Controlled case')).toBeVisible();
  await expect(officer.getByText('Original video not linked')).toBeVisible();
  await expect(officer.getByText(/not derived from the procedural replay/)).toBeVisible();
  for(const title of ['01 · Source','02 · Evidence','03 · Officer','04 · Report'])
   await expect(officer.getByText(title)).toBeVisible();

  await page.getByRole('button',{name:'Decision',exact:true}).click();
  await expect(page.getByRole('region',{name:'Selected evidence step'}))
    .toContainText('Review the attendance case');
  const caseLink=officer.getByRole('link',{name:/Review saved case/});
  await expect(caseLink).toHaveAttribute('href',
    '/cases/SIM-KA-104-ATT?from=mission&scene=attendance&step=3');
  await caseLink.click();
  await expect(page).toHaveURL(/\/cases\/SIM-KA-104-ATT\?/);
  await expect(page.getByText('Simulated').first()).toBeVisible();
  await expect(page.getByText('Officer review',{exact:true})).toBeVisible();
  const back=page.getByRole('link',{name:'Return to walkthrough'});
  await expect(back).toHaveAttribute('href','/demo/mission?scene=attendance&step=3');
  await back.click();
  await expect(page.getByRole('region',{name:'Selected evidence step'}))
    .toContainText('Review the attendance case');

  const pdf=await request.get(apiRoot+'/api/centres/DEMO-KA-104/report.pdf');
  expect(pdf.status()).toBe(200);
  expect(pdf.headers()['content-type']).toContain('application/pdf');
  const binary=await pdf.body();
  expect(binary.subarray(0,5).toString()).toBe('%PDF-');
  expect(binary.length).toBeGreaterThan(300);

  const quick=page.getByRole('region',{name:'Judge rehearsal'});
  await quick.getByRole('button',{name:'60 sec'}).click();
  await expect(page.getByRole('heading',{name:'Attendance gap'})).toBeVisible();
  await quick.getByRole('button',{name:'Next cue'}).click();
  await expect(page.getByRole('heading',{name:'Camera is obstructed'})).toBeVisible();
  await expect(page.getByText('Withheld · not zero')).toBeVisible();
  await quick.getByRole('button',{name:'Next cue'}).click();
  await expect(page.getByRole('heading',{name:'Equipment visibility'})).toBeVisible();
  await page.getByText('Why the evidence quality gate matters').click();
  await expect(page.getByText(/Not visible is not proven absent/)).toBeVisible();
  await quick.getByRole('button',{name:'Next cue'}).click();
  await expect(page.getByRole('heading',{name:'No exception needed'})).toBeVisible();
  await expect(officer.getByText(/no exception case is required for this authored example/)).toBeVisible();
  await expect(officer.getByRole('link',{name:/Review saved case/})).toHaveCount(0);
  await expect(page.getByText('Fraud confirmed')).toHaveCount(0);
  await expect(quick.getByRole('button',{name:'Next cue'})).toBeDisabled();

  // The old centre directory remains available by deep link, not in the new five-module sidebar.
  await page.goto('/centres');
  await expect(page.getByRole('heading',{name:'Centres',exact:true})).toBeVisible();
  await page.getByRole('textbox',{name:'Search centres'}).fill('Bengaluru');
  await expect(page.getByRole('link',{name:'View',exact:true})).toHaveCount(1);
  await page.getByRole('link',{name:'View',exact:true}).click();
  await expect(page).toHaveURL(/\/centres\/DEMO-KA-104$/);
  await expect(page.getByRole('navigation',{name:'Centre sections'}).getByRole('link',{name:'Overview'}))
    .toHaveAttribute('aria-current','page');
  await shell.getByRole('link',{name:'Insights'}).click();
  await expect(page.getByRole('region',{name:'Centre report workspace'})).toBeVisible();
  await shell.getByRole('link',{name:'Issues'}).click();
  await expect(page.getByRole('region',{name:'Selected issue details'})).toBeVisible();
  expect(writes).toHaveLength(0);
 });

 test('real recording-manifest outage yields explicit denial and restores after retry',async({page})=>{
  let unavailable=true;
  await page.route('**/api/demo/replay',async route=>{
   if(unavailable)await route.abort('failed');
   else await route.continue();
  });
  await page.goto('/demo/mission');
  const replay=page.getByRole('region',{name:'Source-locked replay'});
  await expect(replay.getByRole('alert')).toContainText('No replay, detection or camera conclusion is shown');
  await expect(replay.locator('video')).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Officer evidence chain'})).toBeVisible();
  unavailable=false;
  await replay.getByRole('button',{name:'Retry verification'}).click();
  await expect(replay.getByText('Manifest hash matched')).toBeVisible();
  await expect(replay.locator('video')).toHaveCount(1);
 });

 test('mobile judge route, centre report and no-exception conclusion avoid document overflow',async({page})=>{
  await page.setViewportSize({width:375,height:812});
  for(const url of ['/demo/mission','/centres/DEMO-KA-104','/insights','/actions']){
   await page.goto(url);
   const overflow=await page.evaluate(()=>
     document.documentElement.scrollWidth-document.documentElement.clientWidth);
   expect(overflow,'Horizontal overflow at '+url).toBeLessThanOrEqual(1);
   await expect(page.getByRole('navigation',{name:'Mobile primary navigation'})).toBeVisible();
  }
  await page.goto('/demo/mission');
  await page.getByRole('button',{name:/No exception needed/}).click();
  const officer=page.getByRole('region',{name:'Officer evidence chain'});
  await expect(officer.getByText(/no exception case is required/)).toBeVisible();
  await expect(officer.getByRole('link',{name:/Review saved case/})).toHaveCount(0);
 });
});
