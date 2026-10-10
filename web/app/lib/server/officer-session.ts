import 'server-only';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import type { NextRequest } from 'next/server';

export const COOKIE_NAME = 'kw_officer_session';
const TTL_MS = 30 * 60 * 1000;
const MAX_SESSIONS = 150;

type OfficerSession = {
  token: string;
  csrf: string;
  expiresAt: number;
};

const sessions = new Map<string, OfficerSession>();

export function protectedMode(): boolean {
  return process.env.KAUSHALWATCH_WEB_AUTH_MODE === 'protected';
}

export function requireProtectedMode(): boolean {
  // A server configured for protected deployment must explicitly enable it.
  // "demo" is for a local walkthrough, never an implicit fallback on pilots.
  return ['protected', 'demo'].includes(process.env.KAUSHALWATCH_WEB_AUTH_MODE || '')
    && protectedMode();
}

export function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get('origin');
  const fetchSite = request.headers.get('sec-fetch-site');
  // Browser mutations always send Origin. Reject cross-site and originless
  // requests, including form POST CSRF and unsafe replay from unrelated apps.
  return !!origin && origin === request.nextUrl.origin && fetchSite !== 'cross-site';
}

function sweep(): void {
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

export function createSession(token: string): { id: string; csrf: string } {
  sweep();
  const id = randomBytes(32).toString('base64url');
  const csrf = randomBytes(32).toString('base64url');
  sessions.set(id, { token, csrf, expiresAt: Date.now() + TTL_MS });
  return { id, csrf };
}

export function getSession(request: NextRequest): OfficerSession | null {
  const id = request.cookies.get(COOKIE_NAME)?.value;
  if (!id || id.length !== 43) return null;
  const session = sessions.get(id);
  if (!session) return null;
  if (session.expiresAt <= Date.now()) {
    sessions.delete(id);
    return null;
  }
  return session;
}

export function closeSession(request: NextRequest): void {
  const id = request.cookies.get(COOKIE_NAME)?.value;
  if (id) sessions.delete(id);
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
    sameSite: 'strict', path: '/', maxAge: TTL_MS / 1000,
  };
}

export function upstreamBase(): string {
  const value = (process.env.KAUSHALWATCH_API_INTERNAL_URL || '').replace(/\/$/, '');
  if (!value) throw new Error('The internal KaushalWatch API URL is not configured');
  const url = new URL(value);
  if (url.pathname !== '/' || url.search || url.hash || url.username || url.password) {
    throw new Error('Internal API origin must not contain path or credentials');
  }
  // Never transmit an officer key over non-TLS to a remote service.
  if (url.protocol !== 'https:' && !(url.protocol === 'http:'
    && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))) {
    throw new Error('Protected upstream requires HTTPS, except local loopback');
  }
  return url.origin;
}
