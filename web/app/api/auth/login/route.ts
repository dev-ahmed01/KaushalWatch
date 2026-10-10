import { NextRequest, NextResponse } from 'next/server';
import {
  createSession, protectedMode, sameOrigin, sessionCookie, upstreamBase,
} from '../../../lib/server/officer-session';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  if (!protectedMode()) return NextResponse.json({ detail: 'Protected officer login is disabled.' }, { status: 503 });
  if (!sameOrigin(request)) return NextResponse.json({ detail: 'Invalid login origin.' }, { status: 403 });
  if (Number(request.headers.get('content-length') || 0) > 2048) {
    return NextResponse.json({ detail: 'Invalid login request.' }, { status: 413 });
  }
  let payload: unknown;
  try { payload = await request.json(); } catch {
    return NextResponse.json({ detail: 'Invalid login request.' }, { status: 400 });
  }
  const key = (payload as { accessKey?: unknown } | null)?.accessKey;
  if (typeof key !== 'string' || key.length < 32 || key.length > 1024 || /\s/.test(key)) {
    return NextResponse.json({ detail: 'Officer key is invalid.' }, { status: 401 });
  }

  let response: Response;
  try {
    // The protected backend itself authenticates and authorizes the key.
    // No officer credential goes to the browser again after this login.
    response = await fetch(upstreamBase() + '/api/cases', {
      headers: { Authorization: 'Bearer ' + key, Accept: 'application/json' },
      cache: 'no-store', redirect: 'manual', signal: AbortSignal.timeout(8000),
    });
  } catch {
    return NextResponse.json({ detail: 'Officer authentication is temporarily unavailable.' }, { status: 503 });
  }
  if (!response.ok) {
    return NextResponse.json(
      { detail: response.status === 401 ? 'Officer key was not accepted.' : 'Officer authentication is unavailable.' },
      { status: response.status === 401 ? 401 : 503 },
    );
  }
  const { id } = createSession(key);
  const result = NextResponse.json({ authenticated: true });
  result.cookies.set(sessionCookie(id));
  result.headers.set('Cache-Control', 'no-store');
  return result;
}
