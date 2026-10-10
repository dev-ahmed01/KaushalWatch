import type { ActionQueue, ActivityIntelligence, AssistantReply, AssistantStatus, CaseRecord, Centre, KaushalBrief, CentreIntelligence, EvidenceReviewPack, NetworkInsights } from './types';

// Explicit build-time switch. The local SIH demo keeps its existing direct
// API path; protected deployments use the same-origin, cookie-authenticated BFF.
export const SECURE_PROXY = process.env.NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY === 'true';
export const API = SECURE_PROXY ? '/api/proxy' : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000');

export async function officerFetch(url: string, init: RequestInit = {}): Promise<Response> {
  if (!SECURE_PROXY) return fetch(url, init);
  const headers = new Headers(init.headers);
  const method = (init.method || 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD') {
    const response = await fetch('/api/auth/status', { cache: 'no-store', credentials: 'same-origin' });
    if (!response.ok) throw new Error('Officer session unavailable.');
    const status = await response.json() as { csrfToken?: string | null };
    if (!status.csrfToken) throw new Error('Officer session expired. Sign in again.');
    headers.set('X-KaushalWatch-CSRF', status.csrfToken);
  }
  const response = await fetch(url, { ...init, headers, credentials: 'same-origin', cache: 'no-store' });
  if (response.status === 401 && typeof window !== 'undefined') {
    window.location.assign('/login?next=' + encodeURIComponent(window.location.pathname));
  }
  return response;
}

async function parse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(payload?.detail || 'KaushalWatch API request failed');
  return payload as T;
}

export async function getActionQueue(period = 'yesterday') {
  return parse<ActionQueue>(await officerFetch(`${API}/api/actions?period=${encodeURIComponent(period)}`, { cache: 'no-store' }));
}

export async function getNetworkInsights(period = 'last_7_days') {
  return parse<NetworkInsights>(await officerFetch(`${API}/api/insights?period=${encodeURIComponent(period)}`, { cache: 'no-store' }));
}

export async function getKaushalBrief(period = 'yesterday') {
  return parse<KaushalBrief>(await officerFetch(`${API}/api/kaushalai/brief?period=${encodeURIComponent(period)}`, { cache: 'no-store' }));
}

export async function getCentres() {
  return parse<{ centres: Centre[]; total: number }>(await officerFetch(`${API}/api/centres`, { cache: 'no-store' }));
}

export async function getActivityIntelligence(centreId: string, period = 'yesterday') {
  return parse<ActivityIntelligence>(await officerFetch(`${API}/api/centres/${encodeURIComponent(centreId)}/activity-intelligence?period=${encodeURIComponent(period)}`, { cache: 'no-store' }));
}

export async function getCentreIntelligence(centreId: string, period = 'last_7_days') {
  return parse<CentreIntelligence>(await officerFetch(`${API}/api/centres/${encodeURIComponent(centreId)}/intelligence?period=${encodeURIComponent(period)}`, { cache: 'no-store' }));
}

export async function getCentre(centreId: string) {
  return parse<Centre>(await officerFetch(`${API}/api/centres/${encodeURIComponent(centreId)}`, { cache: 'no-store' }));
}

export async function getDashboard(centreId?: string, batchId?: string) {
  const params = new URLSearchParams();
  if (centreId) params.set('centre_id', centreId);
  if (batchId) params.set('batch_id', batchId);
  return parse<any>(await officerFetch(`${API}/api/dashboard?${params.toString()}`, { cache: 'no-store' }));
}

export async function getHistory(centreId: string, limit = 100) {
  return parse<{ rows: any[] }>(await officerFetch(`${API}/api/analysis-history?centre_id=${encodeURIComponent(centreId)}&limit=${limit}`, { cache: 'no-store' }));
}

export async function getCases() {
  return parse<CaseRecord[]>(await officerFetch(`${API}/api/cases`, { cache: 'no-store' }));
}

export async function getEvidencePack(caseId: string) {
  return parse<EvidenceReviewPack>(
    await officerFetch(`${API}/api/cases/${encodeURIComponent(caseId)}/evidence-pack`, { cache: 'no-store' }),
  );
}

export type ReviewAccessStatus = {
  mode: 'demo' | 'token'; required: boolean; prototype_only: boolean;
  can_write?: boolean; can_use_network_assistant?: boolean; role?: string; centre_ids?: string[];
};

export async function getOfficerContext() {
  return parse<{
    role: string; centre_ids: string[]; can_review: boolean; can_use_network_assistant: boolean;
  }>(await officerFetch(`${API}/api/officer-context`, { cache: 'no-store' }));
}

export async function getReviewAccess(): Promise<ReviewAccessStatus> {
  // Protected login already bound an officer actor on the server; the case
  // page must never ask for a second raw bearer secret in its client state.
  if (SECURE_PROXY) {
    const permissions = await getOfficerContext();
    return { mode: 'token', required: false, prototype_only: true,
      can_write: permissions.can_review, role: permissions.role,
      centre_ids: permissions.centre_ids,
      can_use_network_assistant: permissions.can_use_network_assistant };
  }
  return parse<ReviewAccessStatus>(await officerFetch(`${API}/api/review-access`, { cache: 'no-store' }));
}

export async function reviewCase(caseId: string, action: string, note?: string, officerAccessKey?: string) {
  return parse<CaseRecord>(await officerFetch(`${API}/api/cases/${encodeURIComponent(caseId)}/review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(!SECURE_PROXY && officerAccessKey ? { Authorization: `Bearer ${officerAccessKey}` } : {}),
    },
    body: JSON.stringify({ action, note: note || null }),
  }));
}

export async function askAssistant(centreId: string, message: string, sessionId?: string, signal?: AbortSignal) {
  return parse<AssistantReply>(await officerFetch(`${API}/api/assistant/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ centre_id: centreId, message, ...(sessionId ? { session_id: sessionId } : {}) }),
    signal,
  }));
}

export async function getAssistantStatus() {
  return parse<AssistantStatus>(await officerFetch(`${API}/api/assistant/status`, { cache: 'no-store' }));
}

export async function transcribeAssistantAudio(audio: Blob, signal?: AbortSignal) {
  const form = new FormData();
  const mediaType = audio.type.split(';', 1)[0].toLowerCase();
  const extension = mediaType.includes('wav')
    ? 'wav'
    : mediaType.includes('mpeg')
      ? 'mp3'
      : mediaType.includes('mp4')
        ? 'mp4'
        : 'webm';
  form.append('audio', audio, `recording.${extension}`);
  return parse<{ text: string }>(await officerFetch(`${API}/api/assistant/transcribe`, {
    method: 'POST',
    body: form,
    signal,
  }));
}

export async function synthesizeAssistantSpeech(text: string, signal?: AbortSignal) {
  const response = await officerFetch(`${API}/api/assistant/speech`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    signal,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || 'Speech generation failed');
  }
  return response.blob();
}

export async function getSettings(centreId: string) {
  return parse<any>(await officerFetch(`${API}/api/centres/${encodeURIComponent(centreId)}/settings`, { cache: 'no-store' }));
}

export async function saveSettings(centreId: string, payload: Record<string, unknown>) {
  return parse<any>(await officerFetch(`${API}/api/centres/${encodeURIComponent(centreId)}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }));
}

export async function getRuntimeReadiness() {
  return parse<any>(await officerFetch(`${API}/api/runtime-readiness`, { cache: 'no-store' }));
}

export function reportUrl(centreId: string, period = '7d', startDate?: string, endDate?: string) {
  const params = new URLSearchParams({ period });
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  return `${API}/api/centres/${encodeURIComponent(centreId)}/report?${params.toString()}`;
}

export function reportPdfUrl(centreId: string, period = '7d', startDate?: string, endDate?: string) {
  const params = new URLSearchParams({ period });
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  return `${API}/api/centres/${encodeURIComponent(centreId)}/report.pdf?${params.toString()}`;
}


export async function logoutOfficer(): Promise<void> {
  if (!SECURE_PROXY) return;
  const status = await fetch('/api/auth/status', { cache: 'no-store', credentials: 'same-origin' });
  const body = status.ok ? await status.json() as { csrfToken?: string } : null;
  if (!body?.csrfToken) throw new Error('Officer session expired.');
  const response = await fetch('/api/auth/logout', {
    method: 'POST', cache: 'no-store', credentials: 'same-origin',
    headers: { 'X-KaushalWatch-CSRF': body.csrfToken },
  });
  if (!response.ok) throw new Error('Could not sign out.');
}
