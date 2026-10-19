import {NextRequest,NextResponse} from 'next/server';
import {localResearchPermitted,researchCatalog} from '../../../lib/server/research-replay';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const HEADERS={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'};
export async function GET(request:NextRequest){
 if(!localResearchPermitted(process.env,request.headers))
   return NextResponse.json({detail:'Unavailable'},{status:404,headers:HEADERS});
 try{
   return NextResponse.json(await researchCatalog(process.env),{headers:HEADERS});
 }catch{
   return NextResponse.json({detail:'Approved local research replay unavailable'},
     {status:503,headers:HEADERS});
 }
}
