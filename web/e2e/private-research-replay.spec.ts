import {expect,test} from '@playwright/test';

test('private cache replay is unavailable by default',async({page})=>{
 const r=await page.request.get('/api/demo/research-replay');
 expect(r.status()).toBe(404);
 await page.goto('/demo/mission');
 await expect(page.getByRole('region',{name:'Private research replay'})).toHaveCount(0);
});

test('research replay labels supplied annotations without fake AI counts',async({page})=>{
 await page.route('**/api/demo/research-replay/analysis',r=>r.fulfill({
   status:200,contentType:'application/json',body:JSON.stringify({
     schema:'KW_PRIVATE_RESEARCH_TRIAGE_TRACE_STATUS_V1',status:'ready',
     source_kind:'previously_inspected_research_not_field_validation',
     numeric_heuristic_trace:true,independent_holdout:false,
     physical_tamper_proven:false,reference_custody_verified:false,
     clips:['quality-covered','quality-defocused','quality-moved','quality-normal'].map((id,i)=>({
       id,source_sha256:String.fromCharCode(97+i).repeat(64),
       counts:{evidence_unusable:i===0?1:0,possible_interference:0,annotation_event_samples:0},
       samples:[{frame0:0,second:0,annotation_in_event:false,
         usability:i===0?'NOT_USABLE_FOR_VISUAL_VERIFICATION':'PROVISIONALLY_OBSERVABLE',
         interference_review:'NOT_ESTABLISHED',
         reason:i===0?'FOCUS_DEGRADED':'NO_SEVERE_QUALITY_LOSS_OBSERVED'}],
     })),
   })
 }));
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
 await page.getByRole('button',{name:'Open optional research diagnostics'}).click();
 const panel=page.getByRole('region',{name:'Private research replay'});
 await expect(panel.getByRole('heading',{name:'Annotated camera-quality study'})).toBeVisible();
 await expect(panel.getByText('covered interval')).toBeVisible();
 await expect(panel.getByText(/not a skill-training centre/)).toBeVisible();
 await expect(panel.getByText('Challenge check · difficult normal scenes')).toBeVisible();
 await expect(panel.getByText('Normal/pre-event · possible scene change')).toBeVisible();
 await expect(panel.getByText('Normal/pre-event · evidence withheld')).toBeVisible();
 await expect(panel.getByText('Annotated event · evidence withheld')).toBeVisible();
 await expect(panel.getByRole('button',{name:'Examine normal control'})).toBeVisible();
 await expect(panel.getByText('Computed frame sample')).toBeVisible();
 await expect(panel.getByText('Evidence usability')).toBeVisible();
 await expect(panel.getByText('Possible interference')).toBeVisible();
 await expect(panel.getByText(/Source-matched numeric heuristic/)).toBeVisible();
 await expect(panel.locator('video')).toHaveAttribute('src',/quality-covered\/media/);
 await panel.getByRole('button',{name:'Examine normal control'}).click();
 await expect(panel.getByRole('button',{name:'Normal control',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(panel.getByText('No incident annotated')).toBeVisible();
 await expect(panel.getByText(/No inferred attendance/)).toBeVisible();
});
