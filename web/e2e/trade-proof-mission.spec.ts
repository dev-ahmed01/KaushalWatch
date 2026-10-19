import {test,expect} from '@playwright/test';

test('trade equipment manifest derives the actual five classes and simulated counts',async({page})=>{
 const response=await page.request.get('/api/demo/trade-proof');
 expect(response.status()).toBe(200);
 expect(response.headers()['cache-control']).toContain('no-store');
 const proof=await response.json();
 expect(proof.status).toBe('illustrative_only');
 expect(proof.job_role_code).toBe('CON/Q0603');
 expect(proof.counts_are_simulated).toBe(true);
 expect(proof.video_source_sha256).toBeNull();
 expect(proof.model_run_verified).toBe(false);
 expect(proof.independent_per_class_tp_fp_fn).toBeNull();
 expect(proof.items).toHaveLength(5);
 expect(proof.items.find((x:{id:string})=>x.id==='training_panel').required).toBe(4);
 expect(proof.items.find((x:{id:string})=>x.id==='training_panel').example_observed).toBe(3);
 expect(proof.items.find((x:{id:string})=>x.id==='multimeter').example_observed).toBeNull();
});

test('officer can explore sample times and withhold equipment counts on blocked camera',async({page})=>{
 await page.goto('/demo/mission');
 await page.getByRole('button',{name:/Equipment visibility/}).click();
 const matrix=page.getByRole('region',{name:'Trade equipment proof'});
 await expect(matrix.getByRole('heading',{name:'Equipment proof matrix'})).toBeVisible();
 await expect(matrix.getByText('Quantities are simulated')).toBeVisible();
 await expect(matrix.getByRole('button',{name:/Electrical Switchboard \/ Training Panel/})).toBeVisible();
 await expect(matrix.getByText('Example visibility gap')).toBeVisible();
 await expect(matrix.getByText(/Independent TP\/FP\/FN not measured/)).toBeVisible();
 await matrix.getByRole('button',{name:'20s'}).click();
 await expect(matrix.getByRole('button',{name:'20s'})).toHaveAttribute('aria-pressed','true');
 await matrix.getByRole('button',{name:/Illustrate camera blocked/}).click();
 await expect(matrix.getByText('Observation withheld')).toBeVisible();
 await expect(matrix.getByText(/count is unknown, never zero/)).toBeVisible();
 await matrix.getByRole('button',{name:/Digital Multimeter/}).click();
 await expect(matrix.getByText(/physical officer check/)).toBeVisible();
 await expect(matrix.getByText(/not an official stock requirement/)).toHaveCount(0);
});

test('fixture API failure displays no invented trade requirement',async({page})=>{
 await page.route('**/api/demo/trade-proof',route=>route.fulfill({
  status:503,contentType:'application/json',body:'{"detail":"unavailable"}'
 }));
 await page.goto('/demo/mission');
 await page.getByRole('button',{name:/Equipment visibility/}).click();
 const matrix=page.getByRole('region',{name:'Trade equipment proof'});
 await expect(matrix.getByRole('alert')).toContainText('no requirement or observation is inferred');
 await expect(matrix.getByRole('button',{name:/training panel/i})).toHaveCount(0);
 await expect(matrix.getByRole('button',{name:'Retry'})).toBeVisible();
});

test('role-specific equipment proof fits narrow mobile screens',async({page})=>{
 await page.setViewportSize({width:375,height:812});
 await page.goto('/demo/mission');
 await page.getByRole('button',{name:/Equipment visibility/}).click();
 await expect(page.getByRole('heading',{name:'Equipment proof matrix'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1)).toBe(false);
});
