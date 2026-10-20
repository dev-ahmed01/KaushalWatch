import {test,expect} from '@playwright/test';

test('guided source and saved officer case stay source-separated; PDF links to actual report',async({page,request})=>{
 await page.goto('/demo/mission');
 const chain=page.getByRole('region',{name:'Officer evidence chain'});
 await expect(chain.getByText('Controlled case')).toBeVisible();
 await expect(chain.getByText('Original video not linked')).toBeVisible();
 await expect(chain.getByText(/not derived from the procedural replay/)).toBeVisible();
 await expect(chain.getByText('01 · Source')).toBeVisible();
 await expect(chain.getByText('02 · Evidence')).toBeVisible();
 await expect(chain.getByText('03 · Officer')).toBeVisible();
 await expect(chain.getByText('04 · Report')).toBeVisible();
 await expect(chain.getByRole('link',{name:/Review saved case/})).toHaveAttribute('href','/cases/SIM-KA-104-ATT?from=mission&scene=attendance&step=0');
 const link=chain.getByRole('link',{name:/Centre PDF/});
 await expect(link).toHaveAttribute('href',/\/api\/centres\/DEMO-KA-104\/report\.pdf/);
 const pdf=await request.get('http://127.0.0.1:8000/api/centres/DEMO-KA-104/report.pdf');
 expect(pdf.status()).toBe(200);
 expect(pdf.headers()['content-type']).toContain('application/pdf');
 expect((await pdf.body()).subarray(0,5).toString()).toBe('%PDF-');
 await chain.getByRole('link',{name:/Review saved case/}).click();
 await expect(page).toHaveURL(/\/cases\/SIM-KA-104-ATT/);
 await expect(page.getByText('Simulated').first()).toBeVisible();
 await expect(page.getByRole('link',{name:'Return to walkthrough'})).toHaveAttribute('href','/demo/mission?scene=attendance&step=0');
 await page.getByRole('link',{name:'Return to walkthrough'}).click();
 await expect(page.getByRole('heading',{name:'Attendance gap'})).toBeVisible();
});

test('no-case normal control has no invented officer audit or alert',async({page})=>{
 await page.goto('/demo/mission');
 await page.getByRole('button',{name:/No exception needed/}).click();
 const chain=page.getByRole('region',{name:'Officer evidence chain'});
 await expect(chain.getByText(/no exception case is required/i)).toBeVisible();
 await expect(chain.getByRole('link',{name:/Review saved case/})).toHaveCount(0);
 await expect(chain.getByText('Controlled case')).toHaveCount(0);
});

test('failed evidence pack cannot be replaced by an authored scenario status',async({page})=>{
 await page.route('**/api/cases/SIM-KA-104-ATT/evidence-pack',route=>route.abort());
 await page.goto('/demo/mission');
 const chain=page.getByRole('region',{name:'Officer evidence chain'});
 await expect(chain.getByRole('alert')).toContainText('No case status or source relationship was assumed');
 await expect(chain.getByRole('link',{name:/Review saved case/})).toHaveCount(0);
 await expect(chain.getByRole('button',{name:'Retry record'})).toBeVisible();
});

test('insights confidence panel does not invent unreviewed model accuracy',async({page})=>{
 await page.goto('/insights');
 const panel=page.getByRole('region',{name:'Proof of Training qualification scorecard'});
 await expect(panel.getByRole('heading',{name:'Evidence qualification'})).toBeVisible();
 await expect(panel.getByText('No field certification')).toBeVisible();
 await expect(panel.getByText('NOT QUALIFIED')).toHaveCount(6);
 await expect(panel.getByText(/No private benchmark receipt loaded/)).toBeVisible();
});

test('375px guided officer evidence chain remains keyboard-usable and within viewport',async({page})=>{
 await page.setViewportSize({width:375,height:812});
 await page.goto('/demo/mission');
 const chain=page.getByRole('region',{name:'Officer evidence chain'});
 await expect(chain.getByRole('link',{name:/Review saved case/})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)).toBe(false);
 await chain.getByRole('link',{name:/Review saved case/}).focus();
 expect(await chain.getByRole('link',{name:/Review saved case/}).evaluate(x=>document.activeElement===x)).toBe(true);
});
