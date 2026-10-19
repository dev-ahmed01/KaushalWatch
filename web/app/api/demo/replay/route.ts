import {NextResponse} from 'next/server';
import {loadReplayCatalog,localReplayPermitted} from '../../../lib/server/replay-catalog';

export const runtime='nodejs';
export const dynamic='force-dynamic';

// Only the pre-generated, public synthetic clips are allowlisted here.
// This API never accepts filenames, reads Drive, exposes private CCTV,
// streams a secret video, or permits model receipts in a protected release.
export async function GET(){
 if(!localReplayPermitted())return NextResponse.json(
   {detail:'Controlled replay is disabled in protected environments'},
   {status:404,headers:{'Cache-Control':'private, no-store'}});
 const result=await loadReplayCatalog();
 return NextResponse.json(result,{
   status:result.status==='ready'?200:503,
   headers:{'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'},
 });
}
