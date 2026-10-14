import { NextRequest, NextResponse } from 'next/server';
import {
  closeSession, COOKIE_NAME, getSession, protectedMode, sameOrigin, validCsrf,
} from '../../../lib/server/officer-session';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  if (!protectedMode()) return NextResponse.json({ detail: 'Not in protected mode.' }, { status: 503 });
  if (!sameOrigin(request)) return NextResponse.json({ detail: 'Invalid logout origin.' }, { status: 403 });
  let session;
  try { session = await getSession(request); }
  catch { return NextResponse.json({ detail: 'Officer session storage unavailable.' }, { status: 503 }); }
  if (!session || !validCsrf(request, session)) {
    return NextResponse.json({ detail: 'Session expired or CSRF token missing.' }, { status: 403 });
  }
  try { await closeSession(request); }
  catch { return NextResponse.json({ detail: 'Officer session storage unavailable.' }, { status: 503 }); }
  const result = NextResponse.json({ authenticated: false }, { headers: { 'Cache-Control': 'no-store' } });
  result.cookies.set({
    name: COOKIE_NAME, value: '', httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict', path: '/', maxAge: 0,
  });
  return result;
}
