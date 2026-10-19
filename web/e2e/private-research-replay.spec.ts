import {expect,test} from '@playwright/test';

test('private cache replay is unavailable by default',async({page})=>{
 const r=await page.request.get('/api/demo/research-replay');
 expect(r.status()).toBe(404);
 await page.goto('/demo/mission');
 await expect(page.getByRole('region',{name:'Private research replay'})).toHaveCount(0);
});

test('research replay labels supplied annotations without fake AI counts',async({page})=>{
 await page.route('**/api/demo/research-replay',r=>r.fulfill({
  status:200,contentType:'application/json',body:JSON.stringify({
   schema:'KW_PRIVATE_RESEARCH_REPLAY_STATUS_V1',status:'ready',
   research_only:true,model_inference_qualified:false,training_centre_validation:false,
   clips:[
    {id:'quality-covered',name:'Coverage change',annotation_class:'covered',fps:3,
     duration_seconds:47.333,event_start_seconds:12.333,event_end_seconds:47.333,
     source_sha256:'a'.repeat(64),source_url:'/api/demo/research-replay/quality-covered/media'},
    {id:'quality-defocused',name:'Focus change',annotation_class:'defocused',fps:3,
     duration_seconds:47.333,event_start_seconds:12.333,event_end_seconds:47.333,
     source_sha256:'b'.repeat(64),source_url:'/api/demo/research-replay/quality-defocused/media'},
    {id:'quality-moved',name:'Camera alignment change',annotation_class:'moved',fps:3,
     duration_seconds:47.333,event_start_seconds:12.333,event_end_seconds:47.333,
     source_sha256:'c'.repeat(64),source_url:'/api/demo/research-replay/quality-moved/media'},
    {id:'quality-normal',name:'Normal control',annotation_class:'normal',fps:3,
     duration_seconds:47.333,event_start_seconds:null,event_end_seconds:null,
     source_sha256:'d'.repeat(64),source_url:'/api/demo/research-replay/quality-normal/media'}
   ]
  })
 }));
 await page.goto('/demo/mission');
 const panel=page.getByRole('region',{name:'Private research replay'});
 await expect(panel.getByRole('heading',{name:'Annotated camera-quality study'})).toBeVisible();
 await expect(panel.getByText('covered interval')).toBeVisible();
 await expect(panel.getByText(/not from a skill-training centre/)).toBeVisible();
 await expect(panel.locator('video')).toHaveAttribute('src',/quality-covered\/media/);
 await panel.getByRole('button',{name:'Normal control'}).click();
 await expect(panel.getByText('No incident annotated')).toBeVisible();
 await expect(panel.getByText(/No inferred attendance/)).toBeVisible();
});
