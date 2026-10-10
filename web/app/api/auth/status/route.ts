import { NextRequest, NextResponse } from 'next/server';
import { getSession, protectedMode } from '../../../lib/server/officer-session';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const mode = process.env.KAUSHALWATCH_WEB_AUTH_MODE;
  if (mode !== 'protected' && mode !== 'demo') {
    return NextResponse.json({ mode: 'unconfigured', authenticated: false }, {
      status: 503, headers: { 'Cache-Control': 'no-store' },
    });
  }
  let session = null;
  try { session = protectedMode() ? await getSession(request) : null; }
  catch { return NextResponse.json({ mode, authenticated: false,
    detail: 'Officer session storage unavailable.' },
    { status: 503, headers: { 'Cache-Control': 'no-store' } }); }
  return NextResponse.json({
    mode,
    authenticated: mode === 'demo' || Boolean(session),
    // CSRF is NOT the officer credential. Never expose the backend token here.
    csrfToken: session?.csrf || null,
  }, { headers: { 'Cache-Control': 'no-store' } });
}
