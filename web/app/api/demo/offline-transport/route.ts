import {NextRequest,NextResponse} from 'next/server';
import {localTransportReportAllowed,loadPrivateOfflineReport} from '../../../lib/server/offline-report';

export const runtime='nodejs';
export const dynamic='force-dynamic';
const headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'};

export async function GET(request:NextRequest){
 if(!localTransportReportAllowed(process.env,request.headers))
   return NextResponse.json({detail:'Unavailable'},{status:404,headers});
 const file=process.env.KAUSHALWATCH_OFFLINE_REPORT_PATH;
 if(!file)return NextResponse.json({detail:'No local measured transport receipt'},{status:404,headers});
 try{
   const report=await loadPrivateOfflineReport(file);
   return NextResponse.json(report,{status:200,headers});
 }catch{
   return NextResponse.json({detail:'Measured local receipt unavailable'},{status:503,headers});
 }
}
