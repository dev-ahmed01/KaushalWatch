import {expect,test} from '@playwright/test';

/** Offline browser presentation smoke: no page asset/CDN/API call may leave
 *  the loopback machine, including font stylesheets and embedded media.
 *  Does not claim that backend models or speech integrations work air-gapped.
 */
test('built four-module journey keeps both branded fonts and procedural media on localhost',async({page})=>{
 const outbound:string[]=[];
 const runtimeErrors:string[]=[];
 page.on('pageerror',e=>runtimeErrors.push(e.message));
 await page.route('**/*',route=>{
   const url=new URL(route.request().url());
   if(url.protocol==='data:'||url.protocol==='blob:'){
     void route.continue();return;
   }
   if(!['127.0.0.1','localhost'].includes(url.hostname) ||
     !['http:','https:'].includes(url.protocol)){
     outbound.push(url.origin);
     void route.abort('internetdisconnected');
     return;
   }
   void route.continue();
 });
 const visited=['/','/demo/mission','/centres','/centres/DEMO-KA-104/camera-trust','/insights','/actions'];
 for(const path of visited){
   await page.goto(path);
   await expect(page.getByRole('navigation',{name:'Primary navigation'})).toBeVisible();
   expect(outbound,'Unexpected external browser request at '+path).toEqual([]);
 }
 await page.goto('/demo/mission');
 await expect(page.getByRole('heading',{name:/A centre reports. Evidence responds/})).toBeVisible();
 await expect(page.getByRole('region',{name:'Source-locked replay'}).getByText('Manifest hash matched')).toBeVisible();
 const fonts=await page.evaluate(async()=>{
   await document.fonts.ready;
   const heading=document.querySelector('h1');
   return {
     body:getComputedStyle(document.body).fontFamily,
     heading:heading?getComputedStyle(heading).fontFamily:'',
     loaded:[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family),
   };
 });
 expect(fonts.body).toMatch(/Poppins/i);
 expect(fonts.heading).toMatch(/Bricolage/i);
 expect(fonts.loaded.some(f=>/Poppins/i.test(f)),'Poppins should render without internet').toBe(true);
 expect(fonts.loaded.some(f=>/Bricolage/i.test(f)),'Bricolage should render without internet').toBe(true);
 expect(outbound).toEqual([]);
 expect(runtimeErrors).toEqual([]);
});

test('browser disconnected from remote network still handles officer case and PDF locally',async({page,request})=>{
 const external:string[]=[];
 await page.route('**/*',route=>{
   const url=new URL(route.request().url());
   if(!['localhost','127.0.0.1'].includes(url.hostname)){
     external.push(url.href);void route.abort('internetdisconnected');
   }else void route.continue();
 });
 await page.goto('/demo/mission');
 const chain=page.getByRole('region',{name:'Officer evidence chain'});
 await expect(chain.getByText('Controlled case')).toBeVisible();
 await chain.getByRole('link',{name:/Review saved case/}).click();
 await expect(page.getByText('Simulated').first()).toBeVisible();
 await page.getByRole('link',{name:'Return to walkthrough'}).click();
 await expect(page.getByRole('heading',{name:'Attendance gap'})).toBeVisible();
 const pdf=await request.get((process.env.E2E_API_BASE_URL||'http://127.0.0.1:8000')+
   '/api/centres/DEMO-KA-104/report.pdf');
 expect(pdf.status()).toBe(200);
 expect((await pdf.body()).subarray(0,5).toString()).toBe('%PDF-');
 expect(external).toEqual([]);
});


test('320px Insights heatmap scrolls in its own viewport, not the document',async({page})=>{
 await page.setViewportSize({width:320,height:680});
 await page.goto('/insights');
 const region=page.getByRole('region',{name:'Activity heatmap, horizontally scrollable'});
 await expect(region).toBeVisible();
 const before=await region.evaluate(el=>({
   width:el.clientWidth,contentWidth:el.scrollWidth,
   docWidth:document.documentElement.scrollWidth,
   viewport:document.documentElement.clientWidth,
 }));
 expect(before.contentWidth).toBeGreaterThan(before.width);
 expect(before.docWidth-before.viewport).toBeLessThanOrEqual(1);
 await region.evaluate(el=>el.scrollLeft=el.scrollWidth);
 const after=await region.evaluate(el=>({
   left:el.scrollLeft,docWidth:document.documentElement.scrollWidth,
   viewport:document.documentElement.clientWidth,
 }));
 expect(after.left).toBeGreaterThan(0);
 expect(after.docWidth-after.viewport).toBeLessThanOrEqual(1);
});
