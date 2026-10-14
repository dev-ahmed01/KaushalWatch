import { NextRequest, NextResponse } from 'next/server';
import { protectedMode } from '../../../../lib/server/officer-session';
import {
  createPendingLogin, oidcConfig, oidcCookie, sanitizeDestination, ssoEnabled,
} from '../../../../lib/server/oidc-flow';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  if (!protectedMode() || !ssoEnabled()) {
    return NextResponse.json({ detail: 'Organization SSO is unavailable.' },
      { status: 503, headers: { 'Cache-Control': 'no-store' } });
  }
  try {
    const config = oidcConfig();
    const { transaction, cookie, challenge } = createPendingLogin(
      sanitizeDestination(request.nextUrl.searchParams.get('next')));
    const target = new URL(config.authorization);
    target.searchParams.set('response_type', 'code');
    target.searchParams.set('client_id', config.clientId);
    target.searchParams.set('redirect_uri', config.redirect.toString());
    target.searchParams.set('scope', 'openid');
    target.searchParams.set('state', transaction.state);
    target.searchParams.set('code_challenge', challenge);
    target.searchParams.set('code_challenge_method', 'S256');
    // Provider-specific API-audience request may be configured separately.
    const audience = process.env.KAUSHALWATCH_OIDC_AUTH_AUDIENCE;
    if (audience) target.searchParams.set('audience', audience);
    const response = NextResponse.redirect(target, { status: 303 });
    response.cookies.set(oidcCookie(cookie));
    response.headers.set('Cache-Control', 'no-store');
    return response;
  } catch {
    return NextResponse.json({ detail: 'Organization SSO is not configured.' },
      { status: 503, headers: { 'Cache-Control': 'no-store' } });
  }
}
