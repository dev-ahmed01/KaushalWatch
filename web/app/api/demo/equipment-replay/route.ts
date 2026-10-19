import {NextRequest,NextResponse} from 'next/server';
import {equipmentReplayAllowed,verifiedEquipmentReplay} from '../../../lib/server/equipment-replay';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const h={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'};
export async function GET(req:NextRequest){
 if(!equipmentReplayAllowed(process.env,req.headers))
   return NextResponse.json({detail:'Unavailable'},{status:404,headers:h});
 try{
   const result=await verifiedEquipmentReplay(process.env.KAUSHALWATCH_EQUIPMENT_REPLAY_DIR||'');
   return NextResponse.json(result.catalog,{headers:h});
 }catch{return NextResponse.json({detail:'Source/receipt unavailable or invalid'},{status:503,headers:h});}
}
