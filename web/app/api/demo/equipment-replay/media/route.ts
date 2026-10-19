import {NextRequest} from 'next/server';
import {equipmentReplayAllowed,verifiedEquipmentReplay} from '../../../../lib/server/equipment-replay';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const h={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff',
 'Content-Security-Policy':"default-src 'none'",'Accept-Ranges':'bytes'};
export async function GET(req:NextRequest){
 if(!equipmentReplayAllowed(process.env,req.headers))
   return new Response(null,{status:404,headers:h});
 try{
   const {video}=await verifiedEquipmentReplay(process.env.KAUSHALWATCH_EQUIPMENT_REPLAY_DIR||'');
   const range=req.headers.get('range');
   let start=0,end=video.length-1;
   if(range!==null){
     const match=/^bytes=(\d+)-(\d*)$/.exec(range);
     if(!match)return new Response(null,{status:416,headers:{...h,'Content-Range':'bytes */'+video.length}});
     start=Number(match[1]);end=match[2]?Number(match[2]):end;
     if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start>end||start<0||start>=video.length)
       return new Response(null,{status:416,headers:{...h,'Content-Range':'bytes */'+video.length}});
     end=Math.min(end,video.length-1);
   }
   const bytes=new Uint8Array(video.subarray(start,end+1));
   return new Response(bytes,{status:range===null?200:206,headers:{
     ...h,'Content-Type':'video/mp4','Content-Length':String(bytes.byteLength),
     ...(range!==null?{'Content-Range':'bytes '+start+'-'+end+'/'+video.length}:{})
   }});
 }catch{return new Response(null,{status:503,headers:h});}
}
