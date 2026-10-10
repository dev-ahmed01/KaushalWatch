import 'server-only';
import { createCipheriv, createDecipheriv, createHash, randomBytes, timingSafeEqual } from 'node:crypto';
import type { NextRequest } from 'next/server';

export const COOKIE_NAME = 'kw_officer_session';
const TTL_SECONDS = 30 * 60;
const TTL_MS = TTL_SECONDS * 1000;
const MAX_SESSIONS = 150;

export type OfficerSession = {
  token: string;
  csrf: string;
  expiresAt: number;
};

type SessionStore = { kind: 'memory' } | {
  kind: 'redis-rest';
  url: string;
  bearer: string;
  key: Buffer;
};

const registry = globalThis as typeof globalThis & {
  __kaushalwatchOfficerSessions?: Map<string, OfficerSession>;
};
const sessions = registry.__kaushalwatchOfficerSessions
  ?? (registry.__kaushalwatchOfficerSessions = new Map<string, OfficerSession>());

export function protectedMode(): boolean {
  return process.env.KAUSHALWATCH_WEB_AUTH_MODE === 'protected';
}

export function requireProtectedMode(): boolean {
  return ['protected', 'demo'].includes(process.env.KAUSHALWATCH_WEB_AUTH_MODE || '')
    && protectedMode();
}

export function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get('origin');
  const host = request.headers.get('host');
  const fetchSite = request.headers.get('sec-fetch-site');
  if (!origin || !host || fetchSite === 'cross-site') return false;
  try {
    const parsed = new URL(origin);
    if (parsed.host.toLowerCase() !== host.toLowerCase()) return false;
    if (parsed.protocol === 'https:') return true;
    return parsed.protocol === 'http:'
      && ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname);
  } catch {
    return false;
  }
}

function storeConfig(): SessionStore {
  const mode = process.env.KAUSHALWATCH_SESSION_STORE || '';
  if (mode === 'memory') {
    // A deliberate synthetic staging escape hatch, not a deployment default.
    if (process.env.KAUSHALWATCH_ALLOW_EPHEMERAL_SESSIONS !== 'true'
      || !['staging', 'development', 'test', 'local'].includes(process.env.KAUSHALWATCH_ENV || '')) {
      throw new Error('Ephemeral officer sessions are disabled');
    }
    return { kind: 'memory' };
  }
  if (mode !== 'redis-rest') throw new Error('A durable officer session store must be configured');
  const rawUrl = process.env.KAUSHALWATCH_SESSION_REDIS_REST_URL || '';
  const bearer = process.env.KAUSHALWATCH_SESSION_REDIS_REST_TOKEN || '';
  const rawKey = process.env.KAUSHALWATCH_SESSION_ENCRYPTION_KEY || '';
  let url: URL;
  try { url = new URL(rawUrl); }
  catch { throw new Error('Invalid session store URL'); }
  if ((url.protocol !== 'https:' && !(url.protocol === 'http:'
      && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)))
    || url.pathname !== '/' || url.search || url.hash || url.username || url.password) {
    throw new Error('Officer session store requires a bare HTTPS origin or loopback test server');
  }
  if (bearer.length < 32 || bearer.length > 1024 || /\s/.test(bearer)) {
    throw new Error('Invalid session store authentication');
  }
  const key = Buffer.from(rawKey, 'base64');
  if (key.length !== 32 || key.toString('base64') !== rawKey) {
    throw new Error('Officer session encryption key must be 32 random base64-encoded bytes');
  }
  return { kind: 'redis-rest', url: url.origin, bearer, key };
}

function redisKey(sessionId: string): string {
  return 'kaushalwatch:officer-session:v1:' + createHash('sha256').update(sessionId).digest('hex');
}

function seal(session: OfficerSession, key: Buffer, storageKey: string): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', key, iv);
  cipher.setAAD(Buffer.from(storageKey));
  const ciphertext = Buffer.concat([cipher.update(JSON.stringify(session), 'utf8'), cipher.final()]);
  return JSON.stringify({ v: 1, iv: iv.toString('base64url'),
    data: ciphertext.toString('base64url'), tag: cipher.getAuthTag().toString('base64url') });
}

function unseal(raw: string, key: Buffer, storageKey: string): OfficerSession {
  const envelope = JSON.parse(raw);
  if (envelope.v !== 1 || typeof envelope.iv !== 'string'
    || typeof envelope.tag !== 'string' || typeof envelope.data !== 'string') {
    throw new Error('Invalid session envelope');
  }
  const iv = Buffer.from(envelope.iv, 'base64url');
  const tag = Buffer.from(envelope.tag, 'base64url');
  if (iv.length !== 12 || tag.length !== 16) throw new Error('Invalid session nonce or tag');
  const decipher = createDecipheriv('aes-256-gcm', key, iv);
  decipher.setAAD(Buffer.from(storageKey));
  decipher.setAuthTag(tag);
  const obj = JSON.parse(Buffer.concat([
    decipher.update(Buffer.from(envelope.data, 'base64url')), decipher.final(),
  ]).toString('utf8'));
  if (typeof obj.token !== 'string' || typeof obj.csrf !== 'string'
    || !Number.isSafeInteger(obj.expiresAt)) throw new Error('Invalid session payload');
  return obj as OfficerSession;
}

async function redisCommand(store: Extract<SessionStore, { kind: 'redis-rest' }>,
  command: (string | number)[]): Promise<unknown> {
  // Upstash-compatible Redis REST command form; secrets never enter URLs or logs.
  const response = await fetch(store.url, {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + store.bearer, 'Content-Type': 'application/json' },
    body: JSON.stringify(command), cache: 'no-store', redirect: 'manual',
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) throw new Error('Officer session storage unavailable');
  const data: unknown = await response.json();
  if (!data || typeof data !== 'object' || !('result' in data) || 'error' in data) {
    throw new Error('Unexpected officer session storage response');
  }
  return (data as { result: unknown }).result;
}

function sweepMemory(): void {
  const now = Date.now();
  for (const [key, session] of sessions.entries()) {
    if (session.expiresAt <= now) sessions.delete(key);
  }
  while (sessions.size >= MAX_SESSIONS) {
    const oldest = sessions.keys().next().value;
    if (!oldest) break;
    sessions.delete(oldest);
  }
}

export async function createSession(token: string): Promise<{ id: string; csrf: string }> {
  const store = storeConfig();
  const id = randomBytes(32).toString('base64url');
  const csrf = randomBytes(32).toString('base64url');
  const session = { token, csrf, expiresAt: Date.now() + TTL_MS };
  if (store.kind === 'memory') {
    sweepMemory();
    sessions.set(id, session);
  } else {
    const result = await redisCommand(store, ['SET', redisKey(id),
      seal(session, store.key, redisKey(id)), 'EX', TTL_SECONDS, 'NX']);
    if (result !== 'OK') throw new Error('Officer session creation refused');
  }
  return { id, csrf };
}

export async function getSession(request: NextRequest): Promise<OfficerSession | null> {
  const store = storeConfig();
  const id = request.cookies.get(COOKIE_NAME)?.value;
  if (!id || !/^[A-Za-z0-9_-]{43}$/.test(id)) return null;
  let session: OfficerSession | null;
  if (store.kind === 'memory') {
    session = sessions.get(id) ?? null;
  } else {
    const raw = await redisCommand(store, ['GET', redisKey(id)]);
    if (raw === null) return null;
    if (typeof raw !== 'string') throw new Error('Invalid officer session storage format');
    session = unseal(raw, store.key, redisKey(id));
  }
  if (session && session.expiresAt <= Date.now()) {
    if (store.kind === 'memory') sessions.delete(id);
    else await redisCommand(store, ['DEL', redisKey(id)]);
    return null;
  }
  return session;
}

export async function closeSession(request: NextRequest): Promise<void> {
  const store = storeConfig();
  const id = request.cookies.get(COOKIE_NAME)?.value;
  if (!id || !/^[A-Za-z0-9_-]{43}$/.test(id)) return;
  if (store.kind === 'memory') sessions.delete(id);
  else await redisCommand(store, ['DEL', redisKey(id)]);
}

export function validCsrf(request: NextRequest, session: OfficerSession): boolean {
  const supplied = request.headers.get('x-kaushalwatch-csrf');
  if (!supplied || !sameOrigin(request)) return false;
  const a = Buffer.from(supplied, 'utf8');
  const b = Buffer.from(session.csrf, 'utf8');
  return a.length === b.length && timingSafeEqual(a, b);
}

export function sessionCookie(id: string): {
  name: string; value: string; httpOnly: true; secure: boolean;
  sameSite: 'strict'; path: string; maxAge: number;
} {
  return {
    name: COOKIE_NAME, value: id, httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict', path: '/', maxAge: TTL_SECONDS,
  };
}

export function upstreamBase(): string {
  const value = (process.env.KAUSHALWATCH_API_INTERNAL_URL || '').replace(/\/$/, '');
  if (!value) throw new Error('The internal KaushalWatch API URL is not configured');
  const url = new URL(value);
  if (url.pathname !== '/' || url.search || url.hash || url.username || url.password) {
    throw new Error('Internal API origin must not contain path or credentials');
  }
  if (url.protocol !== 'https:' && !(url.protocol === 'http:'
    && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))) {
    throw new Error('Protected upstream requires HTTPS, except local loopback');
  }
  return url.origin;
}
