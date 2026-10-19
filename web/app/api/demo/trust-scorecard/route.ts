import {NextRequest,NextResponse} from 'next/server';
import {localScorecardAllowed,readTrustScorecard} from '../../../lib/server/scorecard-report';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'};
export async function GET(request:NextRequest){
 if(!localScorecardAllowed(process.env,request.headers))
  return NextResponse.json({detail:'Unavailable'},{status:404,headers});
 const file=process.env.KAUSHALWATCH_SCORECARD_PATH;
 if(!file)return NextResponse.json({detail:'No private independently reviewed evaluation receipt'},{status:404,headers});
 try{
  return NextResponse.json(await readTrustScorecard(file),{status:200,headers});
 }catch{
  return NextResponse.json({detail:'Scorecard source verification failed'},{status:503,headers});
 }
}
