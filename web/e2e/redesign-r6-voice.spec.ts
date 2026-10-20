import {expect,test} from '@playwright/test';

test('R6 voice-note composer is explicit and never sends on microphone denial', async ({page}) => {
  await page.addInitScript(() => {
    if (navigator.mediaDevices) Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {
      configurable: true, value: () => Promise.reject(new DOMException('Permission denied', 'NotAllowedError')),
    });
  });
  await page.goto('/chatbox?centre=DEMO-KA-104&person=demo-head-DEMO-KA-104');
  await expect(page.getByRole('region',{name:'Chatbox workspace'})).toBeVisible();
  const voice=page.getByRole('region',{name:'Voice note composer'});
  await expect(voice.getByRole('button',{name:'Record voice note'})).toBeVisible();
  const writes: string[]=[];
  page.on('request',req=>{if(req.method()==='POST'&&req.url().includes('/voice'))writes.push(req.url())});
  await voice.getByRole('button',{name:'Record voice note'}).click();
  await expect(voice.getByText(/Microphone access was denied|Microphone recording is not supported|no supported voice-note format/)).toBeVisible();
  expect(writes).toHaveLength(0);
});
