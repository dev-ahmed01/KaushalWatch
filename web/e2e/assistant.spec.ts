import { test, expect, type Page, type Route } from '@playwright/test';


const centre = {
  centre_id: 'DEMO-KA-104',
  name: 'Bengaluru TC-04',
  location: 'Bengaluru, Karnataka',
  district: 'Bengaluru Urban',
  state: 'Karnataka',
  batch_id: 'ELEC-2026-08',
  job_role: 'Construction Electrician - LV',
  trainees: 120,
  camera_id: 'LAB-CAM-01',
  connectivity_mode: 'low_bandwidth',
  status: 'attention',
  pending_cases: 1,
  confirmed_cases: 0,
  attendance_status: 'attention',
  practical_status: 'pending',
  infrastructure_status: 'pending',
  camera_status: 'nominal',
  evidence_integrity_status: 'clear',
  verification_complete: false,
  analysis_count: 1,
  escalation: {
    level: 1,
    label: 'Centre review',
    reasons: ['1 pending exception'],
    next_action: 'Review the case.',
  },
  last_analysis: '2026-10-05T06:00:00+00:00',
  recent_analyses: [],
};


async function openAssistant(
  page:Page,
  assistantStatus = { enabled: true, configured: true, available: true, voice_configured: true, voice_available: true },
) {
  await page.route('**/api/assistant/status', route =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(assistantStatus) })
  );
  await page.route('**/api/centres/DEMO-KA-104', (route:Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(centre) })
  );
  await page.route('**/api/centres', (route:Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ centres: [centre], total: 1 }),
    })
  );
  await page.goto('/centres/DEMO-KA-104');
  await expect(page.getByText('Kaushal Assistant', { exact: true })).toBeVisible();
}

async function installVoiceMocks(page:Page) {
  await page.addInitScript(() => {
    const voiceMock = {
      getUserMediaCalls: 0,
      trackStopCalls: 0,
      playCalls: 0,
      pauseCalls: 0,
      revokedUrls: 0,
      rejectPermission: false,
      emptyRecording: false,
      unsupportedFormat: false,
      rejectNextPlay: false,
    };
    Object.defineProperty(window, '__voiceMock', { value: voiceMock, writable: false });

    class FakeMediaRecorder {
      static isTypeSupported(type:string) {
        if ((window as unknown as {__voiceMock:typeof voiceMock}).__voiceMock.unsupportedFormat) return false;
        return type === 'audio/webm;codecs=opus' || type === 'audio/webm';
      }

      state = 'inactive';
      mimeType = 'audio/webm;codecs=opus';
      ondataavailable:((event:{data:Blob})=>void)|null = null;
      onstop:(()=>void)|null = null;
      onerror:((event:Event)=>void)|null = null;

      constructor() {
        Object.defineProperty(window, '__lastMediaRecorder', { value: this, configurable: true });
      }

      start() {
        this.state = 'recording';
      }

      stop() {
        this.state = 'inactive';
        const state = (window as unknown as {__voiceMock:typeof voiceMock}).__voiceMock;
        const blob = new Blob([state.emptyRecording ? '' : 'recorded-audio'], { type: this.mimeType });
        this.ondataavailable?.({ data: blob });
        this.onstop?.();
      }
    }

    Object.defineProperty(window, 'MediaRecorder', { value: FakeMediaRecorder, configurable: true });
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: async () => {
          voiceMock.getUserMediaCalls += 1;
          if (voiceMock.rejectPermission) throw new DOMException('Permission denied', 'NotAllowedError');
          return {
            getTracks: () => [{ stop: () => { voiceMock.trackStopCalls += 1; } }],
          };
        },
      },
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'play', {
      configurable: true,
      value() {
        voiceMock.playCalls += 1;
        if (voiceMock.rejectNextPlay) {
          voiceMock.rejectNextPlay = false;
          return Promise.reject(new DOMException('Autoplay blocked', 'NotAllowedError'));
        }
        return Promise.resolve();
      },
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
      configurable: true,
      value() {
        voiceMock.pauseCalls += 1;
      },
    });
    const revokeObjectURL = URL.revokeObjectURL.bind(URL);
    URL.revokeObjectURL = (url:string) => {
      voiceMock.revokedUrls += 1;
      revokeObjectURL(url);
    };
  });
}


test('typed assistant keeps context, renders sources, and starts a new conversation', async ({ page }) => {
  const requests: Array<Record<string, unknown>> = [];
  await page.route('**/api/assistant/chat', async route => {
    const request = route.request().postDataJSON();
    requests.push(request);
    const first = requests.length === 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        message: first
          ? 'The system recorded one attendance discrepancy.'
          : 'That attendance discrepancy is the only unresolved issue.',
        session_id: first ? 'session-1' : request.session_id || 'session-2',
        sources: first
          ? [{
              kind: 'analysis',
              id: 'AN-1',
              label: 'Attendance analysis',
              timestamp: '2026-10-05T06:00:00+00:00',
              href: '/centres/DEMO-KA-104/history',
            }]
          : [],
        tool_calls: [{ name: 'get_operational_history', status: 'success', duration_ms: 3 }],
      }),
    });
  });

  await openAssistant(page);
  await page.getByRole('button', { name: 'What happened today?' }).click();
  await expect(page.getByText('The system recorded one attendance discrepancy.')).toBeVisible();
  await expect(page.getByRole('link', { name: /Attendance analysis/ })).toHaveAttribute(
    'href',
    '/centres/DEMO-KA-104/history'
  );

  await page.getByPlaceholder('Ask Kaushal anything...').fill('Which one was most serious?');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('That attendance discrepancy is the only unresolved issue.')).toBeVisible();
  expect(requests[1]).toMatchObject({
    centre_id: 'DEMO-KA-104',
    message: 'Which one was most serious?',
    session_id: 'session-1',
  });

  await page.getByRole('button', { name: 'New conversation' }).click();
  await expect(page.getByText('The system recorded one attendance discrepancy.')).not.toBeVisible();
  await page.getByPlaceholder('Ask Kaushal anything...').fill('Is the vision system ready?');
  await page.getByRole('button', { name: 'Send message' }).click();
  expect(requests[2].session_id).toBeUndefined();
});

test('voice question records, transcribes, uses chat, speaks, and supports stop and replay', async ({ page }) => {
  await installVoiceMocks(page);
  const chatRequests:Array<Record<string, unknown>> = [];
  const speechRequests:Array<Record<string, unknown>> = [];
  await page.route('**/api/assistant/transcribe', async route => {
    await new Promise(resolve => setTimeout(resolve, 1000));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ text: 'What happened in the latest analysis?' }),
    });
  });
  await page.route('**/api/assistant/chat', async route => {
    chatRequests.push(route.request().postDataJSON());
    const responseText = chatRequests.length === 1
      ? 'The latest analysis flagged one attendance discrepancy.'
      : chatRequests.length === 2
        ? 'The main discrepancy was the attendance mismatch.'
        : 'Investigate the unresolved attendance case first.';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        message: responseText,
        session_id: 'voice-session',
        sources: [],
        tool_calls: [{ name: 'get_operational_history', status: 'success', duration_ms: 2 }],
      }),
    });
  });
  await page.route('**/api/assistant/speech', async route => {
    speechRequests.push(route.request().postDataJSON());
    await route.fulfill({ status: 200, contentType: 'audio/wav', body: 'mock-mp3' });
  });

  await openAssistant(page);
  await page.getByRole('button', { name: 'Start voice question' }).click();
  await expect(page.getByText('Listening...')).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as unknown as {__voiceMock:{getUserMediaCalls:number}}).__voiceMock.getUserMediaCalls)).toBe(1);

  await page.getByRole('button', { name: 'Stop recording' }).click();
  await expect(page.getByText('Understanding your question...')).toBeVisible();
  await expect(page.getByText('What happened in the latest analysis?')).toBeVisible();
  await expect(page.getByText('The latest analysis flagged one attendance discrepancy.')).toBeVisible();
  await expect(page.getByText('AI-generated voice')).toBeVisible();

  expect(chatRequests).toEqual([{ centre_id: 'DEMO-KA-104', message: 'What happened in the latest analysis?' }]);
  expect(speechRequests).toEqual([{ text: 'The latest analysis flagged one attendance discrepancy.' }]);
  await expect.poll(() => page.evaluate(() => (window as unknown as {__voiceMock:{trackStopCalls:number}}).__voiceMock.trackStopCalls)).toBe(1);
  await expect.poll(() => page.evaluate(() => (window as unknown as {__voiceMock:{playCalls:number}}).__voiceMock.playCalls)).toBe(1);

  await page.getByRole('button', { name: 'Stop response' }).click();
  await expect.poll(() => page.evaluate(() => (window as unknown as {__voiceMock:{pauseCalls:number}}).__voiceMock.pauseCalls)).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Replay response' }).click();
  await expect.poll(() => page.evaluate(() => (window as unknown as {__voiceMock:{playCalls:number}}).__voiceMock.playCalls)).toBe(2);
  await page.getByRole('button', { name: 'Stop response' }).click();

  await page.getByPlaceholder('Ask Kaushal anything...').fill('What were the main discrepancies?');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('The main discrepancy was the attendance mismatch.')).toBeVisible();
  await page.getByPlaceholder('Ask Kaushal anything...').fill('Which one should I investigate first?');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Investigate the unresolved attendance case first.')).toBeVisible();
  expect(chatRequests.slice(1)).toEqual([
    { centre_id: 'DEMO-KA-104', message: 'What were the main discrepancies?', session_id: 'voice-session' },
    { centre_id: 'DEMO-KA-104', message: 'Which one should I investigate first?', session_id: 'voice-session' },
  ]);
  expect(speechRequests).toHaveLength(1);
});

test('typed replies stay quiet until requested and microphone failures remain isolated', async ({ page }) => {
  await installVoiceMocks(page);
  let speechCalls = 0;
  await page.route('**/api/assistant/chat', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ message: 'Vision readiness is available in runtime status.', session_id: 'typed-session', sources: [], tool_calls: [] }),
  }));
  await page.route('**/api/assistant/speech', route => {
    speechCalls += 1;
    return route.fulfill({ status: 200, contentType: 'audio/wav', body: 'mock-mp3' });
  });

  await openAssistant(page);
  await page.getByPlaceholder('Ask Kaushal anything...').fill('Is the vision system ready?');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Vision readiness is available in runtime status.')).toBeVisible();
  expect(speechCalls).toBe(0);
  await page.getByRole('button', { name: 'Play response' }).click();
  await expect.poll(() => speechCalls).toBe(1);

  await page.getByRole('button', { name: 'Stop response' }).click();
  await page.evaluate(() => {
    (window as unknown as {__voiceMock:{rejectPermission:boolean}}).__voiceMock.rejectPermission = true;
  });
  await page.getByRole('button', { name: 'Start voice question' }).click();
  await expect(page.locator('.neoAssistantError')).toContainText('Microphone permission was denied');
  await expect(page.getByText('Kaushal Assistant', { exact: true })).toBeVisible();

  await page.evaluate(() => {
    const mock = (window as unknown as {__voiceMock:{rejectPermission:boolean;unsupportedFormat:boolean}}).__voiceMock;
    mock.rejectPermission = false;
    mock.unsupportedFormat = true;
  });
  await page.getByRole('button', { name: 'Start voice question' }).click();
  await expect(page.locator('.neoAssistantError')).toContainText('compatible audio recording format');

  await page.evaluate(() => {
    const mock = (window as unknown as {__voiceMock:{unsupportedFormat:boolean;emptyRecording:boolean}}).__voiceMock;
    mock.unsupportedFormat = false;
    mock.emptyRecording = true;
  });
  await page.getByRole('button', { name: 'Start voice question' }).click();
  await page.getByRole('button', { name: 'Stop recording' }).click();
  await expect(page.locator('.neoAssistantError')).toContainText('No audio was captured');
});

test('collapsing the assistant releases an active microphone stream', async ({ page }) => {
  await installVoiceMocks(page);
  await openAssistant(page);
  await page.getByRole('button', { name: 'Start voice question' }).click();
  await expect(page.getByText('Listening...')).toBeVisible();
  await page.getByRole('button', { name: 'Collapse assistant' }).click();
  await expect(page.getByRole('button', { name: 'Ask Kaushal' })).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as unknown as {__voiceMock:{trackStopCalls:number}}).__voiceMock.trackStopCalls)).toBe(1);
});

test('blocked voice autoplay exposes an explicit play control', async ({ page }) => {
  await installVoiceMocks(page);
  await page.route('**/api/assistant/transcribe', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ text: 'Any discrepancies?' }),
  }));
  await page.route('**/api/assistant/chat', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      message: 'No discrepancy data is available.',
      session_id: 'blocked-session',
      sources: [{
        kind: 'analysis',
        id: 'AN-1',
        label: 'Attendance analysis',
        timestamp: null,
        href: '/',
      }],
      tool_calls: [],
    }),
  }));
  await page.route('**/api/assistant/speech', route => route.fulfill({
    status: 200,
    contentType: 'audio/wav',
    body: 'mock-mp3',
  }));

  await openAssistant(page);
  await page.evaluate(() => {
    (window as unknown as {__voiceMock:{rejectNextPlay:boolean}}).__voiceMock.rejectNextPlay = true;
  });
  await page.getByRole('button', { name: 'Start voice question' }).click();
  await page.getByRole('button', { name: 'Stop recording' }).click();
  await expect(page.getByText('Autoplay was blocked. Select Play response.')).toBeVisible();
  await page.getByRole('button', { name: 'Play response' }).click();
  await expect(page.getByRole('button', { name: 'Stop response' })).toBeVisible();
  await page.getByRole('link', { name: /Attendance analysis/ }).click();
  await expect.poll(() => page.evaluate(() => (window as unknown as {__voiceMock:{revokedUrls:number}}).__voiceMock.revokedUrls)).toBeGreaterThan(0);
});

test('recorder errors cannot submit partial audio', async ({ page }) => {
  await installVoiceMocks(page);
  let transcriptionCalls = 0;
  await page.route('**/api/assistant/transcribe', route => {
    transcriptionCalls += 1;
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ text: 'partial' }) });
  });
  await openAssistant(page);

  await page.getByRole('button', { name: 'Start voice question' }).click();
  await page.evaluate(() => {
    const recorder = (window as unknown as {__lastMediaRecorder:{onerror:((event:Event)=>void)|null;stop:()=>void}}).__lastMediaRecorder;
    recorder.onerror?.(new Event('error'));
    recorder.stop();
  });

  await expect(page.locator('.neoAssistantError')).toContainText('recording failed');
  expect(transcriptionCalls).toBe(0);
  await expect.poll(() => page.evaluate(() => (window as unknown as {__voiceMock:{trackStopCalls:number}}).__voiceMock.trackStopCalls)).toBe(1);
});

test('new conversation cancels pending transcription without submitting stale text', async ({ page }) => {
  await installVoiceMocks(page);
  let chatCalls = 0;
  await page.route('**/api/assistant/transcribe', async route => {
    await new Promise(resolve => setTimeout(resolve, 700));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ text: 'Stale voice question' }),
    }).catch(() => undefined);
  });
  await page.route('**/api/assistant/chat', route => {
    chatCalls += 1;
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Should not render', session_id: 'stale', sources: [], tool_calls: [] }),
    });
  });
  await openAssistant(page);

  await page.getByRole('button', { name: 'Start voice question' }).click();
  await page.getByRole('button', { name: 'Stop recording' }).click();
  await expect(page.getByText('Understanding your question...')).toBeVisible();
  await page.getByRole('button', { name: 'New conversation' }).click();

  await page.waitForTimeout(900);
  expect(chatCalls).toBe(0);
  await expect(page.getByText('Stale voice question')).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Start voice question' })).toBeEnabled();
});

test('latest speech request wins and reset cancels pending playback', async ({ page }) => {
  await installVoiceMocks(page);
  let chatCalls = 0;
  let speechCalls = 0;
  await page.route('**/api/assistant/chat', route => {
    chatCalls += 1;
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        message: `Assistant response ${chatCalls}`,
        session_id: 'speech-race-session',
        sources: [],
        tool_calls: [],
      }),
    });
  });
  await page.route('**/api/assistant/speech', async route => {
    speechCalls += 1;
    await new Promise(resolve => setTimeout(resolve, speechCalls === 2 ? 50 : 700));
    await route.fulfill({ status: 200, contentType: 'audio/wav', body: `mock-mp3-${speechCalls}` }).catch(() => undefined);
  });
  await openAssistant(page);

  for (const question of ['First question', 'Second question']) {
    await page.getByPlaceholder('Ask Kaushal anything...').fill(question);
    await page.getByRole('button', { name: 'Send message' }).click();
    await expect(page.getByText(`Assistant response ${chatCalls}`)).toBeVisible();
  }

  const playButtons = page.getByRole('button', { name: 'Play response' });
  await playButtons.nth(0).click();
  await expect.poll(() => speechCalls).toBe(1);
  await playButtons.nth(1).click();
  await expect(page.getByRole('button', { name: 'Stop response' })).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as unknown as {__voiceMock:{playCalls:number}}).__voiceMock.playCalls)).toBe(1);

  await page.getByRole('button', { name: 'Stop response' }).click();
  await page.getByRole('button', { name: 'Play response' }).first().click();
  await expect.poll(() => speechCalls).toBe(3);
  await page.getByRole('button', { name: 'New conversation' }).click();
  await page.waitForTimeout(900);
  await expect.poll(() => page.evaluate(() => (window as unknown as {__voiceMock:{playCalls:number}}).__voiceMock.playCalls)).toBe(1);
  await expect(page.getByText('Assistant response 1')).not.toBeVisible();
});

test('transcription and speech failures leave typed chat usable', async ({ page }) => {
  await installVoiceMocks(page);
  let transcriptionCalls = 0;
  await page.route('**/api/assistant/transcribe', route => {
    transcriptionCalls += 1;
    if (transcriptionCalls === 1) {
      return route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Speech transcription is temporarily unavailable.' }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ text: 'What happened today?' }),
    });
  });
  await page.route('**/api/assistant/chat', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ message: 'The text response is ready.', session_id: 'failure-session', sources: [], tool_calls: [] }),
  }));
  await page.route('**/api/assistant/speech', async route => {
    await new Promise(resolve => setTimeout(resolve, 500));
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Speech generation is temporarily unavailable.' }),
    });
  });
  await openAssistant(page);

  await page.getByRole('button', { name: 'Start voice question' }).click();
  await page.getByRole('button', { name: 'Stop recording' }).click();
  await expect(page.locator('.neoAssistantError')).toContainText('transcription is temporarily unavailable');

  await page.getByRole('button', { name: 'Start voice question' }).click();
  await page.getByRole('button', { name: 'Stop recording' }).click();
  await expect(page.getByText('The text response is ready.')).toBeVisible();
  await expect(page.getByPlaceholder('Ask Kaushal anything...')).toBeEnabled();
  await expect(page.locator('.neoAssistantError')).toContainText('generation is temporarily unavailable');
  await expect(page.getByPlaceholder('Ask Kaushal anything...')).toBeEnabled();
});

test('missing AI configuration is visible without affecting the dashboard', async ({ page }) => {
  await installVoiceMocks(page);
  await openAssistant(page, {
    enabled: true,
    configured: false,
    available: false,
    voice_configured: false,
    voice_available: false,
  });

  await expect(page.getByText('Setup required')).toBeVisible();
  await expect(page.getByText(/requires a Gemini API key/i)).toBeVisible();
  await expect(page.getByPlaceholder('Ask Kaushal anything...')).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Start voice question' })).toBeDisabled();
  await expect(page.getByRole('heading', { name: 'Bengaluru TC-04', level: 1 })).toBeVisible();
});

test('missing Groq configuration leaves typed Gemini chat available', async ({ page }) => {
  await installVoiceMocks(page);
  await page.route('**/api/assistant/chat', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      message: 'Typed chat remains available.',
      session_id: 'gemini-only-session',
      sources: [],
      tool_calls: [],
    }),
  }));
  await openAssistant(page, {
    enabled: true,
    configured: true,
    available: true,
    voice_configured: false,
    voice_available: false,
  });

  await expect(page.getByText(/Voice requires a Groq API key/i)).toBeVisible();
  await expect(page.getByPlaceholder('Ask Kaushal anything...')).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Start voice question' })).toBeDisabled();

  await page.getByPlaceholder('Ask Kaushal anything...').fill('What happened today?');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Typed chat remains available.')).toBeVisible();
});

