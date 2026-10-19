import {NextRequest} from 'next/server';
import {checkedResearchClips,localResearchPermitted} from '../../../../../lib/server/research-replay';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const COMMON={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff',
 'Content-Security-Policy':"default-src 'none'",'Accept-Ranges':'bytes'};
const ALIAS=/^quality-(covered|defocused|moved|normal)$/;
type Ctx={params:Promise<{id:string}>};
export async function GET(request:NextRequest,context:Ctx):Promise<Response>{
 if(!localResearchPermitted(process.env,request.headers))
   return new Response(null,{status:404,headers:COMMON});
 const {id}=await context.params;
 if(!ALIAS.test(id))return new Response(null,{status:404,headers:COMMON});
 try{
   const clips=await checkedResearchClips(process.env.KAUSHALWATCH_RESEARCH_REPLAY_DIR||'');
   const item=clips.find(c=>c.visible.id===id);
   if(!item)return new Response(null,{status:404,headers:COMMON});
   const data=item.bytes;
   const range=request.headers.get('range');
   let start=0,end=data.length-1;
   if(range!==null){
     const match=/^bytes=(\d+)-(\d*)$/.exec(range);
     if(!match)return new Response(null,{status:416,headers:{
       ...COMMON,'Content-Range':'bytes */'+data.length}});
     start=Number(match[1]);end=match[2]?Number(match[2]):end;
     if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)
       ||start<0||start>=data.length||start>end)
       return new Response(null,{status:416,headers:{
         ...COMMON,'Content-Range':'bytes */'+data.length}});
     end=Math.min(end,data.length-1);
   }
   const response=new Uint8Array(data.subarray(start,end+1));
   return new Response(response,{status:range===null?200:206,
     headers:{...COMMON,'Content-Type':'video/mp4',
       'Content-Length':String(response.byteLength),
       ...(range!==null?{'Content-Range':'bytes '+start+'-'+end+'/'+data.length}:{})}});
 }catch{
   return new Response(null,{status:503,headers:COMMON});
 }
}
