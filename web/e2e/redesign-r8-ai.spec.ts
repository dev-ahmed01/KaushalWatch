import {test,expect} from '@playwright/test';

test('R8 evidence copilot does not call provider without explicit click',async({page})=>{
  let called=0;
  await page.route('**/api/assistant/status',r=>r.fulfill({status:200,contentType:'application/json',
    body:JSON.stringify({enabled:true,configured:true,available:true,voice_configured:false,voice_available:false})}));
  await page.route('**/api/assistant/chat',r=>{
    called++;
    return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
      message:'Review grounded source evidence before deciding.',session_id:'r8-demo',
      sources:[{kind:'case',id:'c-1',label:'Saved case',href:'/cases/SIM-KA-104-ATT',timestamp:null}],tool_calls:[]})});
  });
  await page.goto('/issues');
  const context=page.getByRole('region',{name:'Contextual KaushalAI'}).first();
  await expect(context).toBeVisible();
  expect(called).toBe(0);
  const button=context.getByRole('button',{name:'Ask KaushalAI about this record'});
  if(await button.count()){
    await button.click();
    await expect(context.getByText('Review grounded source evidence before deciding.')).toBeVisible();
    expect(called).toBe(1);
  } else {
    await expect(context.getByText(/Gemini unavailable or not authorised/)).toBeVisible();
    expect(called).toBe(0);
  }
});
