import { expect, test } from '@playwright/test';

test('camera recordings are preloaded and monitor has working review controls', async ({ page }) => {
  await page.goto('/centres/DEMO-KA-104/camera-trust');
  await expect(page.getByRole('heading',{name:'Camera Trust'})).toBeVisible();
  await expect(page.getByRole('navigation',{name:'Centre sections'}).getByRole('link',{name:'Camera Trust'}))
    .toHaveAttribute('aria-current','page');
  await expect(page.getByText('3 sources ready')).toBeVisible();
  await expect(page.getByText('PLAYBACK')).toBeVisible();
  const video=page.locator('video[aria-label*="recorded footage"]');
  await expect(video).toHaveAttribute('src',/training-bay\.mp4/);
  await expect(page.getByRole('button',{name:/Workshop floor/})).toBeVisible();
  await page.getByRole('button',{name:/Workshop floor/}).click();
  await expect(video).toHaveAttribute('src',/workshop-floor\.mp4/);
  await page.getByRole('button',{name:'Inspect'}).click();
  await expect(page.getByText('Visibility change').first()).toBeVisible();
  await page.getByRole('button',{name:'Mark reviewed'}).click();
  await expect(page.getByRole('button',{name:/Reviewed — undo/})).toBeVisible();
  await expect(page.getByRole('button',{name:'Export'})).toBeVisible();
});

test('camera monitor fits on mobile without document overflow',async ({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/centres/DEMO-KA-104/camera-trust');
  await expect(page.locator('video')).toBeVisible();
  await expect(page.getByRole('button',{name:'Playback speed'})).toBeVisible();
  const width=await page.evaluate(()=>document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(391);
});
