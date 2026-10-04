import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const enabled=process.env.VISUAL_AUDIT==='1';
const centre='DEMO-KA-104';

async function shot(page:any,name:string){
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth);
  expect(overflow,name+' horizontal overflow').toBeLessThanOrEqual(2);
  await page.screenshot({path:'cycle5-visual-audit/'+name+'.png',fullPage:true});
}

test('cycle 5 complete visual fidelity audit', async ({page})=>{
  test.skip(!enabled,'temporary visual audit only');
  test.setTimeout(240_000);
  const videoPath=process.env.E2E_VIDEO_PATH;
  if(!videoPath) throw new Error('E2E_VIDEO_PATH required');
  fs.mkdirSync('cycle5-visual-audit',{recursive:true});
  await page.setViewportSize({width:1536,height:900});

  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Training Centre Network'})).toBeVisible();
  await shot(page,'01-network');

  await page.goto('/centres');
  await expect(page.getByRole('heading',{name:'Training Centres'})).toBeVisible();
  await shot(page,'02-centres');

  await page.goto('/centres/'+centre);
  await expect(page.locator('.centreVisualCard')).toBeVisible();
  await shot(page,'03-centre');

  await page.goto('/centres/'+centre+'/analysis');
  await expect(page.getByRole('heading',{name:'Centre Analysis'})).toBeVisible();
  await shot(page,'04-analysis');

  await page.goto('/centres/'+centre+'/attendance');
  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await page.getByRole('button',{name:'Analyse Attendance'}).click();
  await expect(page.locator('.overlayMode')).toBeVisible({timeout:45_000});
  await shot(page,'05-attendance');

  await page.goto('/centres/'+centre+'/practical');
  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await expect(page.locator('.workZoneBox').first()).toBeVisible();
  await page.getByRole('button',{name:'Analyse Practical Work'}).click();
  await expect(page.getByText(/decision withheld/i).first()).toBeVisible({timeout:45_000});
  await shot(page,'06-practical');

  await page.goto('/centres/'+centre+'/infrastructure');
  await page.locator('.infraSetupCard select').selectOption('discrepancy');
  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await page.getByRole('button',{name:'Analyse Infrastructure'}).click();
  await expect(page.locator('.evidenceGallery img').first()).toBeVisible({timeout:35_000});
  await shot(page,'07-infrastructure');

  await page.goto('/centres/'+centre+'/review');
  await expect(page.locator('.caseListItem').first()).toBeVisible();
  await page.locator('.caseListItem').first().click();
  await shot(page,'08-review');

  await page.goto('/centres/'+centre+'/outcome');
  await expect(page.getByRole('heading',{name:/Human review required|Verification blocked|Confirmed compliance issue|Compliant/})).toBeVisible();
  await shot(page,'09-outcome');

  await page.goto('/centres/'+centre+'/history');
  await expect(page.getByRole('heading',{name:'Analysis History'})).toBeVisible();
  await shot(page,'10-history');

  await page.goto('/escalations');
  await expect(page.getByRole('heading',{name:'Escalations & Review'})).toBeVisible();
  await shot(page,'11-escalations');

  await page.goto('/reports?centre='+centre+'&period=7d');
  await expect(page.getByRole('heading',{name:'Compliance Reports'})).toBeVisible();
  await shot(page,'12-reports');

  await page.goto('/analytics');
  await expect(page.getByRole('heading',{name:'Monitoring Analytics'})).toBeVisible();
  await shot(page,'13-analytics');

  await page.goto('/settings');
  await expect(page.getByRole('heading',{name:'Settings & Configuration'})).toBeVisible();
  await shot(page,'14-settings');
});
