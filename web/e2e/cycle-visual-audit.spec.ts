import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const enabled=process.env.VISUAL_AUDIT==='1';

test('cycle evidence and runtime visual audit', async ({page})=>{
  test.skip(!enabled,'temporary visual audit only');
  test.setTimeout(180_000);
  const videoPath=process.env.E2E_VIDEO_PATH;
  if(!videoPath) throw new Error('E2E_VIDEO_PATH required');
  fs.mkdirSync('cycle-visual-audit',{recursive:true});
  await page.setViewportSize({width:1536,height:900});

  await page.goto('/centres/DEMO-KA-104/practical');
  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await expect(page.locator('.workZoneBox').first()).toBeVisible();
  await page.screenshot({path:'cycle-visual-audit/01-practical-zones.png',fullPage:true});
  await page.getByRole('button',{name:'Analyse Practical Work'}).click();
  await expect(page.getByText(/decision withheld/i).first()).toBeVisible({timeout:45_000});
  await page.screenshot({path:'cycle-visual-audit/02-practical-result.png',fullPage:true});

  await page.goto('/centres/DEMO-KA-104/infrastructure');
  await page.locator('.infraSetupCard select').selectOption('discrepancy');
  await page.locator('input[name="file"]').setInputFiles(path.resolve(videoPath));
  await page.getByRole('button',{name:'Analyse Infrastructure'}).click();
  await expect(page.locator('.evidenceGallery img').first()).toBeVisible({timeout:35_000});
  await page.screenshot({path:'cycle-visual-audit/03-infrastructure-evidence.png',fullPage:true});

  await page.goto('/centres/DEMO-KA-104/review');
  await expect(page.locator('.caseListItem').first()).toBeVisible();
  await page.locator('.caseListItem').first().click();
  await expect(page.getByRole('link',{name:'Open Evidence Pack'})).toBeVisible();
  await page.screenshot({path:'cycle-visual-audit/04-review-evidence.png',fullPage:true});

  for(const name of ['01-practical-zones','02-practical-result','03-infrastructure-evidence','04-review-evidence']){
    // Each audited screen must stay inside the desktop viewport.
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth);
    expect(overflow,name+' horizontal overflow').toBeLessThanOrEqual(2);
  }
});
