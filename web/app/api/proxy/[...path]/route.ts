import { NextRequest, NextResponse } from 'next/server';
import {
  getSession, protectedMode, sameOrigin, upstreamBase, validCsrf,
} from '../../../lib/server/officer-session';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const METHODS = new Set(['GET', 'POST', 'PUT']);
const SEGMENT = /^[A-Za-z0-9_.-]{1,128}$/;

async function relay(request: NextRequest, params: Promise<{ path: string[] }>): Promise<NextResponse> {
  if (!protectedMode()) return NextResponse.json({ detail: 'Protected proxy is disabled.' }, { status: 503 });
  let session;
  try { session = await getSession(request); }
  catch { return NextResponse.json({ detail: 'Officer session storage unavailable.' },
    { status: 503, headers: { 'Cache-Control': 'no-store' } }); }
  if (!session) return NextResponse.json({ detail: 'Officer session required.' }, {
    status: 401, headers: { 'Cache-Control': 'no-store' },
  });
  if (!METHODS.has(request.method)) return NextResponse.json({ detail: 'Unsupported method.' }, { status: 405 });
  if (request.method !== 'GET' && (!sameOrigin(request) || !validCsrf(request, session))) {
    return NextResponse.json({ detail: 'CSRF verification failed.' }, { status: 403 });
  }
  const { path } = await params;
  if (!Array.isArray(path) || !path.length || !path.every(p => SEGMENT.test(p) && p !== '.' && p !== '..')) {
    return NextResponse.json({ detail: 'Invalid proxy path.' }, { status: 400 });
  }
  const root = path[0];
  const evidence = root === 'evidence' && request.method === 'GET'
    && path.length === 2 && /^[A-Za-z0-9_-]{1,100}\.jpg$/.test(path[1]);
  const api = root === 'api' && path.length > 1
    && path[1] !== 'edge' && path[1] !== 'health' && path[1] !== 'review-access'
    && !path.some(p => p.toLowerCase().includes('openapi'));
  if (!evidence && !api) {
    return NextResponse.json({ detail: 'Endpoint unavailable through officer proxy.' }, { status: 404 });
  }
  const query = request.nextUrl.search;
  let url: string;
  try { url = upstreamBase() + '/' + path.map(encodeURIComponent).join('/') + query; }
  catch { return NextResponse.json({ detail: 'Backend connection unavailable.' }, { status: 503 }); }
  const headers = new Headers({
    Authorization: 'Bearer ' + session.token,
    Accept: request.headers.get('accept') || '*/*',
  });
  const contentType = request.headers.get('content-type');
  if (contentType && request.method !== 'GET') headers.set('Content-Type', contentType);
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: request.method,
      headers,
      body: request.method === 'GET' ? undefined : request.body,
      // Required for streaming multipart video bodies without buffering them.
      ...(request.method === 'GET' ? {} : { duplex: 'half' }),
      redirect: 'manual', cache: 'no-store',
      signal: AbortSignal.timeout(120_000),
    } as RequestInit & { duplex?: 'half' });
  } catch {
    return NextResponse.json({ detail: 'Backend is temporarily unavailable.' }, { status: 502 });
  }
  if (upstream.status >= 300 && upstream.status < 400) {
    return NextResponse.json({ detail: 'Backend redirect refused.' }, { status: 502 });
  }
  const outgoing = new Headers({ 'Cache-Control': 'private, no-store', Pragma: 'no-cache' });
  for (const field of ['content-type', 'content-disposition']) {
    const value = upstream.headers.get(field);
    if (value) outgoing.set(field, value);
  }
  return new NextResponse(upstream.body, { status: upstream.status, headers: outgoing });
}
type Ctx = { params: Promise<{ path: string[] }> };
export const GET = (request: NextRequest, ctx: Ctx) => relay(request, ctx.params);
export const POST = (request: NextRequest, ctx: Ctx) => relay(request, ctx.params);
export const PUT = (request: NextRequest, ctx: Ctx) => relay(request, ctx.params);
