import {test,expect} from '@playwright/test';

test('private equipment video stays unavailable unless explicitly admitted by local operator',async({page})=>{
 const result=await page.request.get('/api/demo/equipment-replay');
 expect(result.status()).toBe(404);
 const video=await page.request.get('/api/demo/equipment-replay/media');
 expect(video.status()).toBe(404);
 await page.goto('/demo/mission');
 await page.getByRole('button',{name:/Equipment visibility/}).click();
 await expect(page.getByRole('region',{name:'Recorded equipment model replay'})).toHaveCount(0);
});

test('operator source-matched fixture receipt renders unreviewed proposals only and respects camera abstention',async({page})=>{
 await page.route('**/api/demo/equipment-replay',route=>route.fulfill({
  status:200,contentType:'application/json',body:JSON.stringify({
   schema:'KW_PRIVATE_EQUIPMENT_REPLAY_V1',
   status:'source_and_receipt_matched_unqualified',
   source_type:'operator_supplied_research_or_approved_video',
   training_centre_certified:false,model_execution_independently_verified:false,
   independent_accuracy_qualified:false,equipment_compliance_qualified:false,
   camera_quality_independently_verified:false,
   video_url:'/api/demo/equipment-replay/media',source_sha256:'a'.repeat(64),
   receipt_sha256:'b'.repeat(64),source_origin:'test-only generated workshop data',
   permission_basis:'CI-authored synthetic sample',privacy_basis:'no people in fixture',
   width:640,height:360,duration:10,
   roi:{x:.1,y:.1,width:.8,height:.8},model_artifact_count:3,
   timestamps:[{second:0,detections:[{label:'training_panel',score:.84,x:.2,y:.2,width:.15,height:.3}],
    counts:[{id:'training_panel',count:1},{id:'drill_machine',count:0}]}]
  })
 }));
 await page.goto('/demo/mission');
 await page.getByRole('button',{name:/Equipment visibility/}).click();
 const p=page.getByRole('region',{name:'Recorded equipment model replay'});
 await expect(p.getByRole('heading',{name:'Recorded equipment model proposals'})).toBeVisible();
 await expect(p.getByText(/not independently verified model accuracy/)).toBeVisible();
 await expect(p.locator('video')).toHaveAttribute('src','/api/demo/equipment-replay/media');
 await expect(p.getByText(/Video aaaaaaaaaaaaaaaaaa/)).toBeVisible();
 await page.getByRole('region',{name:'Trade equipment proof'}).getByRole('button',{name:/Illustrate camera blocked/}).click();
 await expect(p.getByText(/model proposals withheld/)).toBeVisible();
 await expect(p.getByRole('button',{name:/0.0s/})).toBeDisabled();
});

test('untrusted local receipt shows no video proposals or overlay',async({page})=>{
 await page.route('**/api/demo/equipment-replay',route=>route.fulfill({
   status:503,contentType:'application/json',body:'{"detail":"unavailable"}'
 }));
 await page.goto('/demo/mission');
 await page.getByRole('button',{name:/Equipment visibility/}).click();
 const p=page.getByRole('region',{name:'Recorded equipment model replay'});
 await expect(p.getByRole('alert')).toContainText('no equipment proposals can be shown');
 await expect(p.locator('video')).toHaveCount(0);
});
