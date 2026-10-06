import type { AssistantReply, AssistantStatus, CaseRecord, Centre, KaushalBrief, CentreIntelligence } from './types';

export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function parse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(payload?.detail || 'KaushalWatch API request failed');
  return payload as T;
}

export async function getKaushalBrief(period = 'yesterday') {
  return parse<KaushalBrief>(await fetch(`${API}/api/kaushalai/brief?period=${encodeURIComponent(period)}`, { cache: 'no-store' }));
}

export async function getCentres() {
  return parse<{ centres: Centre[]; total: number }>(await fetch(`${API}/api/centres`, { cache: 'no-store' }));
}

export async function getCentreIntelligence(centreId: string, period = 'last_7_days') {
  return parse<CentreIntelligence>(await fetch(`${API}/api/centres/${encodeURIComponent(centreId)}/intelligence?period=${encodeURIComponent(period)}`, { cache: 'no-store' }));
}

export async function getCentre(centreId: string) {
  return parse<Centre>(await fetch(`${API}/api/centres/${encodeURIComponent(centreId)}`, { cache: 'no-store' }));
}

export async function getDashboard(centreId?: string, batchId?: string) {
  const params = new URLSearchParams();
  if (centreId) params.set('centre_id', centreId);
  if (batchId) params.set('batch_id', batchId);
  return parse<any>(await fetch(`${API}/api/dashboard?${params.toString()}`, { cache: 'no-store' }));
}

export async function getHistory(centreId: string, limit = 100) {
  return parse<{ rows: any[] }>(await fetch(`${API}/api/analysis-history?centre_id=${encodeURIComponent(centreId)}&limit=${limit}`, { cache: 'no-store' }));
}

export async function getCases() {
  return parse<CaseRecord[]>(await fetch(`${API}/api/cases`, { cache: 'no-store' }));
}

export async function getEvidencePack(caseId: string) {
  return parse<{ prototype: boolean; case: CaseRecord; integrity: any[]; decision_policy: string }>(
    await fetch(`${API}/api/cases/${encodeURIComponent(caseId)}/evidence-pack`, { cache: 'no-store' }),
  );
}

export async function reviewCase(caseId: string, action: string, note?: string) {
  return parse<CaseRecord>(await fetch(`${API}/api/cases/${encodeURIComponent(caseId)}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, note: note || null }),
  }));
}

export async function askAssistant(centreId: string, message: string, sessionId?: string, signal?: AbortSignal) {
  return parse<AssistantReply>(await fetch(`${API}/api/assistant/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ centre_id: centreId, message, ...(sessionId ? { session_id: sessionId } : {}) }),
    signal,
  }));
}

export async function getAssistantStatus() {
  return parse<AssistantStatus>(await fetch(`${API}/api/assistant/status`, { cache: 'no-store' }));
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
  return parse<{ text: string }>(await fetch(`${API}/api/assistant/transcribe`, {
    method: 'POST',
    body: form,
    signal,
  }));
}

export async function synthesizeAssistantSpeech(text: string, signal?: AbortSignal) {
  const response = await fetch(`${API}/api/assistant/speech`, {
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
  return parse<any>(await fetch(`${API}/api/centres/${encodeURIComponent(centreId)}/settings`, { cache: 'no-store' }));
}

export async function saveSettings(centreId: string, payload: Record<string, unknown>) {
  return parse<any>(await fetch(`${API}/api/centres/${encodeURIComponent(centreId)}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }));
}

export async function getRuntimeReadiness() {
  return parse<any>(await fetch(`${API}/api/runtime-readiness`, { cache: 'no-store' }));
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
