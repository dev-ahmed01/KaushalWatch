import {expect,test} from '@playwright/test';

test('all five modules share one active primary navigation and one assistant action',async({page})=>{
 const routes:[
  string,string,string
 ][]=[
   ['/','Overview','Overview'],
   ['/issues','Issues','Issues'],
   ['/insights','Insights','Insights'],
   ['/centre-desk','Centre Desk','Centre Desk'],
   ['/chatbox','Chatbox','Chatbox'],
 ];
 await page.goto('/');
 for(const [path,navLabel,heading] of routes){
   await page.getByRole('navigation',{name:'Primary navigation'})
     .getByRole('link',{name:navLabel,exact:true}).click();
   await expect(page).toHaveURL(new RegExp(path==='/'?'\\/$':path+'$'));
   const primary=page.getByRole('navigation',{name:'Primary navigation'});
   await expect(primary.getByRole('link',{name:navLabel,exact:true}))
     .toHaveAttribute('aria-current','page');
   await expect(page.getByRole('heading',{name:heading,exact:true}).first()).toBeVisible();
   await expect(page.getByRole('button',{name:'Ask KaushalAI'})).toHaveCount(1);
 }
});

test('judge and saved-case views have relevant headers, no misleading date range',async({page})=>{
 await page.goto('/demo/mission');
 await expect(page.getByText('Proof of Training',{exact:true}).first()).toBeVisible();
 await expect(page.getByRole('combobox',{name:'Date range'})).toHaveCount(0);
 await expect(page.getByRole('group',{name:'Date range'})).toHaveCount(0);
 await page.goto('/cases/SIM-KA-104-ATT');
 await expect(page.getByRole('heading',{name:'Attendance discrepancy'}).first()).toBeVisible();
 await expect(page.getByRole('combobox',{name:'Date range'})).toHaveCount(0);
 await expect(page.getByRole('group',{name:'Date range'})).toHaveCount(0);
 await page.goto('/insights');
 await expect(page.getByRole('combobox',{name:'Date range'})).toBeVisible();
});

test('direct deep centre section and horizontal tabs remain visible, keyboard-accessible at 320px',async({page})=>{
 await page.setViewportSize({width:320,height:680});
 await page.goto('/centres/DEMO-KA-104/camera-trust');
 const tabs=page.getByRole('navigation',{name:'Centre sections'});
 const current=tabs.getByRole('link',{name:'Camera Trust',exact:true});
 await expect(current).toHaveAttribute('aria-current','page');
 await expect(current).toBeInViewport({ratio:0.7});
 const positions=await tabs.evaluate(el=>({
    left:el.scrollLeft,
    width:el.scrollWidth,
    client:el.clientWidth,
 }));
 expect(positions.width).toBeGreaterThan(positions.client);
 expect(positions.left).toBeGreaterThan(0);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth-
    document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
 await current.focus();
 await expect(current).toBeFocused();
 await page.keyboard.press('Tab');
 await expect(tabs.getByRole('link',{name:'Overview'})).toHaveCount(1);
 await tabs.getByRole('link',{name:'Overview'}).click();
 await expect(page).toHaveURL(/\/centres\/DEMO-KA-104$/);
 await expect(tabs.getByRole('link',{name:'Overview',exact:true})).toBeInViewport();
});

test('tight mobile header and primary navigation remain within view across all modules and mission',async({page})=>{
 await page.setViewportSize({width:320,height:680});
 for(const route of ['/','/centres','/insights','/actions','/demo/mission','/cases/SIM-KA-104-ATT']){
   await page.goto(route);
   await expect(page.getByRole('navigation',{name:'Mobile primary navigation'})).toBeVisible();
   const diagnostics=await page.evaluate(()=>{
      const width=document.documentElement.clientWidth;
      return {
        overflow:document.documentElement.scrollWidth-width,
        offenders:[...document.querySelectorAll<HTMLElement>('body *')]
          .map(el=>({tag:el.tagName,cls:String(el.className).slice(0,100),
                     content:(el.textContent||'').trim().slice(0,70),
                     right:Math.round(el.getBoundingClientRect().right),
                     left:Math.round(el.getBoundingClientRect().left)}))
          .filter(el=>el.right>width+1||el.left< -1).slice(0,12),
      };
   });
   expect(diagnostics.overflow,route+' overflow: '+JSON.stringify(diagnostics.offenders))
     .toBeLessThanOrEqual(1);
 }
});
