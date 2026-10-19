import {NextResponse} from 'next/server';
import {loadTradeProof,localTradePermitted} from '../../../lib/server/trade-proof';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const HEADERS={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'};
export async function GET(){
 if(!localTradePermitted())return NextResponse.json({detail:'Unavailable'},
   {status:404,headers:HEADERS});
 try{
   const report=await loadTradeProof();
   return NextResponse.json(report,{status:200,headers:HEADERS});
 }catch{
   return NextResponse.json({detail:'Controlled trade manifest unavailable'},
     {status:503,headers:HEADERS});
 }
}
