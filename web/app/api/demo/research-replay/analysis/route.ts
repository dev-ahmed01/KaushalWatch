import {NextRequest,NextResponse} from 'next/server';
import {localResearchPermitted} from '../../../../lib/server/research-replay';
import {researchTrace} from '../../../../lib/server/research-analysis';

export const runtime='nodejs';
export const dynamic='force-dynamic';
const HEADERS={'Cache-Control':'private, no-store',
 'X-Content-Type-Options':'nosniff',
 'Content-Security-Policy':"default-src 'none'"};
export async function GET(request:NextRequest){
 if(!localResearchPermitted(process.env,request.headers))
   return NextResponse.json({detail:'Unavailable'},{status:404,headers:HEADERS});
 try{
   const trace=await researchTrace(process.env.KAUSHALWATCH_RESEARCH_REPLAY_DIR||'');
   return NextResponse.json(trace,{headers:HEADERS});
 }catch{
   return NextResponse.json({detail:'Private numeric research trace unavailable'},
     {status:503,headers:HEADERS});
 }
}
