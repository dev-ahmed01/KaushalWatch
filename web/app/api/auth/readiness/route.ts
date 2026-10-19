import { NextResponse } from 'next/server';
import { sessionStoreReady } from '../../../lib/server/officer-session';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** External orchestration check; not an authenticated officer action.
 * Returns no backend address, Redis key, credential, or private source state.
 * This is a software dependency check, not independent deployment approval.
 */
export async function GET() {
  const ready = await sessionStoreReady();
  return NextResponse.json(
    { ready, mode: 'protected' },
    { status: ready ? 200 : 503, headers: { 'Cache-Control': 'no-store' } },
  );
}
