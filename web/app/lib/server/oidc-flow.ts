import 'server-only';
import { createCipheriv, createDecipheriv, createHash, randomBytes } from 'node:crypto';
import type { NextRequest } from 'next/server';

export const OIDC_COOKIE = 'kw_oidc_transaction';
const TTL_MS = 5 * 60 * 1000;

export type PendingLogin = {
  state: string;
  verifier: string;
  destination: string;
  expiresAt: number;
};

export function ssoEnabled(): boolean {
  return process.env.KAUSHALWATCH_WEB_IDENTITY_MODE === 'oidc';
}

function requiredUrl(key: string): URL {
  const value = process.env[key] || '';
  let url: URL;
  try { url = new URL(value); }
  catch { throw new Error('Identity provider URL is not configured'); }
  const allowCiLoopback = process.env.KAUSHALWATCH_ENV === 'staging'
    && process.env.KAUSHALWATCH_ALLOW_LOOPBACK_OIDC_TEST === 'true'
    && process.env.KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT !== 'true'
    && url.protocol === 'http:' && url.hostname === '127.0.0.1';
  if ((url.protocol !== 'https:' && !allowCiLoopback)
      || !url.hostname || url.username || url.password
      || url.hash || url.search) {
    throw new Error('Identity provider must use a fixed HTTPS URL');
  }
  return url;
}

export function oidcConfig() {
  const authorization = requiredUrl('KAUSHALWATCH_OIDC_AUTHORIZATION_ENDPOINT');
  const token = requiredUrl('KAUSHALWATCH_OIDC_TOKEN_ENDPOINT');
  const redirect = requiredUrl('KAUSHALWATCH_OIDC_REDIRECT_URI');
  const clientId = process.env.KAUSHALWATCH_OIDC_CLIENT_ID || '';
  const secret = process.env.KAUSHALWATCH_OIDC_CLIENT_SECRET || '';
  if (authorization.hostname !== token.hostname || authorization.port !== token.port
      || !/^[A-Za-z0-9._:\/-]{3,180}$/.test(clientId) || secret.length > 1024) {
    throw new Error('Identity provider endpoints/client ID are inconsistent');
  }
  if (!redirect.pathname.endsWith('/api/auth/oidc/callback')) {
    throw new Error('OIDC redirect URI must point to the fixed callback');
  }
  return { authorization, token, redirect, clientId, secret };
}

function transactionKey(): Buffer {
  const raw = process.env.KAUSHALWATCH_SESSION_ENCRYPTION_KEY || '';
  const key = Buffer.from(raw, 'base64');
  if (key.length !== 32 || key.toString('base64') !== raw) {
    throw new Error('OIDC transaction requires a shared 256-bit session encryption key');
  }
  return key;
}

export function sanitizeDestination(next: string | null): string {
  const candidate = next || '/';
  if (!candidate.startsWith('/') || candidate.startsWith('//') ||
      /[\\\u0000-\u001f\u007f]/.test(candidate) || candidate.length > 512) return '/';
  return candidate;
}

export function createPendingLogin(destination: string): {
  transaction: PendingLogin; cookie: string; challenge: string;
} {
  const state = randomBytes(32).toString('base64url');
  const verifier = randomBytes(32).toString('base64url');
  const transaction: PendingLogin = {
    state, verifier, destination: sanitizeDestination(destination),
    expiresAt: Date.now() + TTL_MS,
  };
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', transactionKey(), iv);
  cipher.setAAD(Buffer.from('kw-oidc-transaction-v1'));
  const encrypted = Buffer.concat([cipher.update(JSON.stringify(transaction)), cipher.final()]);
  const cookie = [
    iv.toString('base64url'),
    cipher.getAuthTag().toString('base64url'),
    encrypted.toString('base64url'),
  ].join('.');
  const challenge = createHash('sha256').update(verifier).digest('base64url');
  return { transaction, cookie, challenge };
}

export function readPendingLogin(request: NextRequest): PendingLogin | null {
  const raw = request.cookies.get(OIDC_COOKIE)?.value || '';
  if (!/^[A-Za-z0-9_-]{16}\.[A-Za-z0-9_-]{20,32}\.[A-Za-z0-9_-]{20,900}$/.test(raw)) {
    return null;
  }
  try {
    const [iv, tag, encrypted] = raw.split('.');
    const decipher = createDecipheriv('aes-256-gcm', transactionKey(),
      Buffer.from(iv, 'base64url'));
    decipher.setAAD(Buffer.from('kw-oidc-transaction-v1'));
    decipher.setAuthTag(Buffer.from(tag, 'base64url'));
    const data: unknown = JSON.parse(Buffer.concat([
      decipher.update(Buffer.from(encrypted, 'base64url')), decipher.final(),
    ]).toString('utf8'));
    if (!data || typeof data !== 'object') return null;
    const item = data as PendingLogin;
    if (typeof item.state !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(item.state)
        || typeof item.verifier !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(item.verifier)
        || typeof item.destination !== 'string'
        || sanitizeDestination(item.destination) !== item.destination
        || !Number.isSafeInteger(item.expiresAt)
        || item.expiresAt < Date.now() || item.expiresAt > Date.now() + TTL_MS) return null;
    return item;
  } catch {
    return null;
  }
}

export function oidcCookie(value: string, maxAge = 300) {
  return {
    name: OIDC_COOKIE, value, httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax' as const, path: '/api/auth/oidc', maxAge,
  };
}
