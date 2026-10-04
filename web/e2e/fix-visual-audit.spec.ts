import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const centre='DEMO-KA-104';
const routes=[
  ['01-network','/','Training Centre Network'],
  ['02-centres','/centres','Training Centres'],
  ['03-centre','/centres/'+centre,'Bengaluru TC-04'],
  ['04-analysis','/centres/'+centre+'/analysis','Centre Analysis'],
  ['05-attendance','/centres/'+centre+'/attendance','Attendance Verification'],
  ['06-practical','/centres/'+centre+'/practical','Practical Work Verification'],
  ['07-infrastructure','/centres/'+centre+'/infrastructure','Infrastructure & Asset Verification'],
  ['08-review','/centres/'+centre+'/review','Review Queue'],
  ['09-outcome','/centres/'+centre+'/outcome','Final Review Outcome'],
  ['10-history','/centres/'+centre+'/history','Analysis History'],
  ['11-escalations','/escalations','Escalations & Review'],
  ['12-reports','/reports?centre='+centre+'&period=7d','Compliance Reports'],
  ['13-analytics','/analytics','Monitoring Analytics'],
  ['14-settings','/settings','Settings & Configuration'],
] as const;

test('capture corrected screens and verify no desktop overflow', async ({page})=>{
  test.setTimeout(120_000);
  fs.mkdirSync('fix-visual-audit',{recursive:true});
  await page.setViewportSize({width:1536,height:900});

  for(const [slug,url,heading] of routes){
    await page.goto(url);
    await expect(page.getByRole('heading',{name:heading}).first()).toBeVisible({timeout:20_000});
    await page.waitForTimeout(400);
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth);
    expect(overflow,slug+' horizontal overflow').toBeLessThanOrEqual(2);
    await page.screenshot({path:'fix-visual-audit/'+slug+'.png',fullPage:true});
  }
});

test('capture one-click full analysis and truthful result states', async ({page})=>{
  test.setTimeout(180_000);
  const videoPath=process.env.E2E_VIDEO_PATH;
  if(!videoPath) throw new Error('E2E_VIDEO_PATH required');
  await page.setViewportSize({width:1536,height:900});

  await page.goto('/centres/'+centre+'/outcome');
  await expect(page.getByRole('heading',{name:'Verification incomplete'})).toBeVisible();
  await page.screenshot({path:'fix-visual-audit/15-outcome-before-analysis.png',fullPage:true});

  await page.goto('/centres/'+centre+'/analysis');
  await page.locator('input[name="analysis-file"]').setInputFiles(path.resolve(videoPath));
  await page.getByRole('button',{name:'Start Full Analysis'}).click();
  await expect(page.getByText('Centre result, history and report data refreshed.')).toBeVisible({timeout:90_000});
  const fullRunOverflow=await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth);
  expect(fullRunOverflow,'full analysis horizontal overflow').toBeLessThanOrEqual(2);
  await page.screenshot({path:'fix-visual-audit/16-full-analysis-complete.png',fullPage:true});

  await page.goto('/centres/'+centre);
  await page.screenshot({path:'fix-visual-audit/17-centre-after-analysis.png',fullPage:true});

  await page.goto('/centres/'+centre+'/outcome');
  await expect(page.getByRole('heading',{name:/Verification blocked|Human review required|Compliant/})).toBeVisible();
  await page.screenshot({path:'fix-visual-audit/18-outcome-after-analysis.png',fullPage:true});

  await page.goto('/analytics');
  await page.screenshot({path:'fix-visual-audit/19-analytics-live.png',fullPage:true});
});
