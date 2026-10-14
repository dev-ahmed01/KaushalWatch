import { NextRequest, NextResponse } from 'next/server';
import { timingSafeEqual } from 'node:crypto';
import {
  createSession, protectedMode, sessionCookie, upstreamBase,
} from '../../../../lib/server/officer-session';
import {
  readPendingLogin, oidcConfig, oidcCookie, ssoEnabled,
} from '../../../../lib/server/oidc-flow';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function reject(status: number) {
  const reply = NextResponse.json(
    { detail: 'The organization sign-in could not be completed.' },
    { status, headers: { 'Cache-Control': 'no-store' } });
  reply.cookies.set(oidcCookie('', 0));
  return reply;
}

function constantMatch(a: string, b: string): boolean {
  const one = Buffer.from(a);
  const two = Buffer.from(b);
  return one.length === two.length && timingSafeEqual(one, two);
}

export async function GET(request: NextRequest) {
  if (!protectedMode() || !ssoEnabled()) return reject(503);
  const pending = readPendingLogin(request);
  const state = request.nextUrl.searchParams.get('state') || '';
  const code = request.nextUrl.searchParams.get('code') || '';
  if (!pending || !constantMatch(state, pending.state)
      || !/^[A-Za-z0-9._~+\/-]{1,2048}$/.test(code)
      || request.nextUrl.searchParams.has('error')) return reject(403);

  let config: ReturnType<typeof oidcConfig>;
  try { config = oidcConfig(); }
  catch { return reject(503); }
  let accessToken: string;
  let expirySeconds: number;
  try {
    const form = new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: config.clientId,
      code, code_verifier: pending.verifier,
      redirect_uri: config.redirect.toString(),
    });
    const headers = new Headers({ 'Content-Type': 'application/x-www-form-urlencoded' });
    if (config.secret) {
      headers.set('Authorization', 'Basic ' + Buffer.from(
        config.clientId + ':' + config.secret).toString('base64'));
    }
    const issued = await fetch(config.token.toString(), {
      method: 'POST', headers, body: form.toString(), cache: 'no-store',
      redirect: 'manual', signal: AbortSignal.timeout(8000),
    });
    if (!issued.ok || Number(issued.headers.get('content-length') || 0) > 16000) {
      return reject(401);
    }
    const body: unknown = await issued.json();
    const data = body as { access_token?: unknown; token_type?: unknown; expires_in?: unknown } | null;
    if (!data || typeof data.access_token !== 'string' || data.access_token.length > 8192
        || data.access_token.length < 50 || data.token_type !== 'Bearer'
        || typeof data.expires_in !== 'number'
        || !Number.isFinite(data.expires_in) || data.expires_in <= 60
        || data.expires_in > 3600) return reject(401);
    accessToken = data.access_token;
    expirySeconds = data.expires_in;
  } catch {
    return reject(503);
  }

  try {
    // Only the trusted FastAPI API validates the signed access JWT and
    // resolves locally provisioned officer rights, not the browser callback.
    const validated = await fetch(upstreamBase() + '/api/officer-validate', {
      headers: { Authorization: 'Bearer ' + accessToken, Accept: 'application/json' },
      cache: 'no-store', redirect: 'manual', signal: AbortSignal.timeout(8000),
    });
    if (!validated.ok) return reject(validated.status === 403 ? 403 : 401);
    const { id } = await createSession(accessToken, expirySeconds - 30);
    const response = NextResponse.redirect(new URL(pending.destination,
      config.redirect.origin), { status: 303 });
    response.cookies.set(oidcCookie('', 0));
    response.cookies.set(sessionCookie(id));
    response.headers.set('Cache-Control', 'no-store');
    return response;
  } catch {
    return reject(503);
  }
}
