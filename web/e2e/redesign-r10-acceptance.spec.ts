import { expect, test } from '@playwright/test';

const routes = [
  {path:'/',heading:'Overview'},
  {path:'/issues',heading:'Issues'},
  {path:'/insights',heading:'Insights'},
  {path:'/centre-desk',heading:'Centre Desk'},
  {path:'/chatbox',heading:'Chatbox'},
] as const;

test('R10 main navigation is coherent across every module without document overflow',async({page})=>{
  const failures:string[]=[];
  page.on('pageerror',err=>failures.push(err.message));
  await page.setViewportSize({width:1366,height:768});
  for(const route of routes){
    await page.goto(route.path);
    const nav=page.getByRole('navigation',{name:'Primary navigation'});
    await expect(nav.getByRole('link')).toHaveCount(5);
    await expect(nav.getByRole('link',{name:route.heading,exact:true})).toHaveAttribute('aria-current','page');
    await expect(page.getByRole('heading',{name:route.heading,exact:true}).first()).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth),route.path).toBeLessThanOrEqual(1);
  }
  expect(failures).toEqual([]);
});

test('R10 narrow-screen navigation and focus remain usable across all five modules',async({page})=>{
  await page.setViewportSize({width:320,height:700});
  for(const route of routes){
    await page.goto(route.path);
    const nav=page.getByRole('navigation',{name:'Mobile primary navigation'});
    await expect(nav).toBeVisible();
    await expect(nav.getByRole('link',{name:route.heading,exact:true})).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth),route.path).toBeLessThanOrEqual(1);
  }
});

test('R10 source-backed issue, report and Chatbox remain connected',async({page,request})=>{
  await page.goto('/issues');
  await expect(page.getByRole('region',{name:'Selected issue details'})).toBeVisible();
  const issue=page.getByRole('region',{name:'Issue queue'});
  await expect(issue.getByRole('button').first()).toBeVisible();
  await page.getByRole('tab',{name:'Communication'}).click();
  const chatLink=page.getByRole('link',{name:/Open in Chatbox/});
  await expect(chatLink).toHaveAttribute('href',/\/chatbox\?centre=/);
  await chatLink.click();
  await expect(page.getByRole('heading',{name:'Chatbox',exact:true})).toBeVisible();
  await page.goto('/insights');
  await expect(page.getByRole('combobox',{name:'Date range'})).toHaveCount(1);
  const report=page.getByRole('region',{name:'Centre report workspace'});
  await expect(report.getByRole('link',{name:'Download PDF'})).toHaveAttribute('href',/report\.pdf\?period=/);
  const pdf=await request.get((process.env.E2E_API_BASE_URL || 'http://127.0.0.1:8000') + '/api/centres/DEMO-KA-104/report.pdf?period=7d');
  expect(pdf.ok()).toBeTruthy();
  expect((await pdf.body()).subarray(0,5).toString()).toBe('%PDF-');
});

test('R10 optional visual capture at desktop and mobile breakpoints',async({page})=>{
  test.skip(process.env.KW_CAPTURE_REDESIGN_SCREENSHOTS!=='true','Opt-in visual capture for reviewed CI/device environments');
  for(const width of [1586,1366,375,320]){
    await page.setViewportSize({width,height:width>500?992:812});
    for(const route of routes){
      await page.goto(route.path);
      await page.getByRole('heading',{name:route.heading,exact:true}).first().waitFor();
      await page.screenshot({path:'test-results/redesign-screens/'+route.heading.toLowerCase().replaceAll(' ','-')+'-'+width+'.png',fullPage:true});
    }
  }
});
