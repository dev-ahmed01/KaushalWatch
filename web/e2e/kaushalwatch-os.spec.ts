import { expect, test } from '@playwright/test';

test('OS navigation exposes four focused workflows and keyboard-active centre tabs',async ({page})=>{
  await page.goto('/');
  const nav=page.getByRole('navigation',{name:'Primary navigation'});
  await expect(nav.getByRole('link')).toHaveCount(4);
  for(const label of ['KaushalAI','Centres','Insights','Actions'])
    await expect(nav.getByRole('link',{name:label})).toBeAttached();
  await page.goto('/centres/DEMO-KA-104');
  const centreNav=page.getByRole('navigation',{name:'Centre sections'});
  await expect(centreNav.getByRole('link')).toHaveCount(6);
  await expect(centreNav.getByRole('link',{name:'Overview',exact:true})).toHaveAttribute('aria-current','page');
  await centreNav.getByRole('link',{name:'Attendance'}).click();
  await expect(page).toHaveURL(/\/attendance$/);
});

test('OS centre search and state filter reduce the visible list',async ({page})=>{
  await page.goto('/centres');
  await expect(page.getByRole('heading',{name:'Centres',exact:true})).toBeVisible();
  const search=page.getByRole('textbox',{name:'Search centres'});
  await search.fill('Bengaluru');
  await expect(page.getByRole('link',{name:'View',exact:true})).toHaveCount(1);
  await search.fill('zz-no-such-centre');
  await expect(page.getByText('No centres match your filters.')).toBeVisible();
  await search.fill('');
  await page.getByRole('combobox',{name:'Centre status filter'}).selectOption('uncertain');
  const count=await page.getByRole('link',{name:'View',exact:true}).count();
  expect(count).toBeGreaterThanOrEqual(1);
});

test('OS uses heading and body font families with narrow-screen navigation',async ({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  const fonts=await page.evaluate(()=>({
    h:getComputedStyle(document.querySelector('h1')!).fontFamily,
    body:getComputedStyle(document.body).fontFamily,
    overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,
  }));
  expect(fonts.h).toContain('Bricolage Grotesque');
  expect(fonts.body).toContain('Poppins');
  expect(fonts.overflow).toBeLessThanOrEqual(1);
  await expect(page.getByRole('navigation',{name:'Mobile primary navigation'})).toBeVisible();
});
