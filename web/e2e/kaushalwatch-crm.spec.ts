import { expect, test } from '@playwright/test';

test('CRM work queue searches by centre and provides contextual evidence and reports',async ({page})=>{
  await page.goto('/actions');
  await expect(page.getByRole('heading',{name:'Action queue'})).toBeVisible();
  const side=page.getByRole('region',{name:'Selected work item'});
  await expect(side.getByRole('heading',{name:'Case at a glance'})).toBeVisible();
  await page.getByRole('textbox',{name:'Search work queue'}).fill('Hubballi');
  await expect(page.getByRole('button',{name:/Inspect Hubballi/})).toHaveCount(1);
  await expect(side.getByRole('link',{name:'Approved pilot site'})).toHaveCount(0);
  await expect(side.getByRole('link',{name:'Centre PDF'}))
    .toHaveAttribute('href',/DEMO-KA-303.*report\.pdf/);
  await expect(side.getByRole('link',{name:'Open case & audit'})).toHaveAttribute('href',/\/cases\/SIM-KA-303-INF$/);
  await page.getByRole('textbox',{name:'Search work queue'}).fill('no-such-case');
  await expect(page.getByText('No matching work items.')).toBeVisible();
  await expect(side.getByText('Select a work item to inspect its centre, evidence, and audit links.')).toBeVisible();
  await page.getByRole('button',{name:'Clear filters'}).click();
  await expect(page.getByText('4 actions')).toBeVisible();
});

test('CRM stage and priority filters never change recorded case status',async ({page})=>{
  await page.goto('/actions');
  await page.getByRole('combobox',{name:'Case status filter'}).selectOption('virtual_verification');
  await expect(page.getByText('No matching work items.')).toBeVisible();
  await page.getByRole('combobox',{name:'Case status filter'}).selectOption('open');
  await expect(page.getByRole('link',{name:'Open case & audit'})).toBeVisible();
  await page.getByRole('combobox',{name:'Priority filter'}).selectOption('high');
  await expect(page.getByRole('link',{name:'Open case & audit'})).toBeVisible();
  const status=await page.request.get('http://127.0.0.1:8000/api/cases');
  expect(status.ok()).toBeTruthy();
  const cases=await status.json();
  expect(cases.find((c:{case_id:string})=>c.case_id==='SIM-KA-104-ATT').status).toBe('open');
});

test('case CRM header opens centre record and source-scoped PDF',async ({page})=>{
  await page.goto('/cases/SIM-KA-104-ATT');
  const navigation=page.getByRole('navigation',{name:'Case record navigation'});
  await expect(navigation.getByRole('link',{name:'Centre record'}))
    .toHaveAttribute('href','/centres/DEMO-KA-104');
  await expect(navigation.getByRole('link',{name:'Centre PDF'}))
    .toHaveAttribute('href',/DEMO-KA-104.*report\.pdf/);
  await expect(page.getByRole('heading',{name:'Officer review'})).toBeVisible();
  await expect(page.getByRole('textbox',{name:'Decision note'})).toBeVisible();
});

test('centre report workspace has one centre selector and PDF link',async ({page})=>{
  await page.goto('/insights?centre=DEMO-KA-303');
  const reports=page.getByRole('region',{name:'Centre report workspace'});
  await expect(reports.getByRole('heading',{name:'Centre verification reports'})).toBeVisible();
  const centre=reports.getByRole('combobox',{name:'Report centre'});
  await expect(centre).toHaveValue('DEMO-KA-303');
  await expect(reports.getByText('Equipment gaps')).toBeVisible();
  await expect(reports.getByRole('link',{name:'Download PDF'})).toHaveAttribute('href',/DEMO-KA-303.*report\.pdf/);
  await centre.selectOption('DEMO-KA-104');
  await expect(reports.getByRole('link',{name:'Download PDF'})).toHaveAttribute('href',/DEMO-KA-104.*report\.pdf/);
  await expect(reports.getByRole('link',{name:'Open centre record'})).toHaveAttribute('href','/centres/DEMO-KA-104');
});

test('CRM inspector and report selector remain usable on narrow screens',async ({page})=>{
  await page.setViewportSize({width:390,height:844});
  for(const route of ['/actions','/insights']){
    await page.goto(route);
    if(route==='/actions')await expect(page.getByRole('region',{name:'Selected work item'})).toBeVisible();
    else await expect(page.getByRole('combobox',{name:'Report centre'})).toBeVisible();
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  }
});
