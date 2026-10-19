/** Local-only, source-hashed SIH replay catalogue. Never handles private CCTV. */
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import path from 'node:path';

const SHA=/^[0-9a-f]{64}$/;
const CLIPS=[
  {id:'training-bay',name:'Training bay',cue:'Focus variation',start:8,end:13},
  {id:'workshop-floor',name:'Workshop floor',cue:'Visibility change',start:9,end:15},
  {id:'east-corridor',name:'East corridor',cue:'Scene alignment',start:7,end:13},
] as const;
const EXPECTED_PROVENANCE='PROCEDURALLY_GENERATED_RECORDING_NOT_REAL_CCTV';
const MAX_VIDEO=12_000_000;
const MAX_RECEIPT=300_000;
const MAX_SAMPLES=240;
const MAX_BOXES=40;

export type ReplayBox={label:string;score:number;x:number;y:number;width:number;height:number};
export type ReplaySample={second:number;frame:number;boxes:ReplayBox[]};
export type ReplayModelReceipt={provider:'operator-supplied';model_sha256:string;profile_sha256:string;samples:ReplaySample[]};
export type ReplayClip={
 id:string;name:string;cue:string;start:number;end:number;duration:number;fps:number;
 sha256:string|null;source_url:string|null;status:'verified'|'blocked';
 receipt_status:'absent'|'matched_unqualified'|'rejected';
 receipt:ReplayModelReceipt|null;
};
export type ReplayCatalog={
 schema:'KW_SOURCE_LOCKED_REPLAY_V1';kind:'synthetic_quality_demonstration';
 status:'ready'|'blocked';physical_camera_accuracy_qualified:false;
 private_video_available:false;source_match_is_model_validation:false;clips:ReplayClip[];
};

export function localReplayPermitted(env:NodeJS.ProcessEnv=process.env):boolean{
 const mode=(env.KAUSHALWATCH_ENV||'development').toLowerCase();
 return env.NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY!=='true'
   && !['pilot','prod','production','staging'].includes(mode)
   && env.KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT!=='true';
}
const plain=(value:unknown):value is Record<string,unknown>=>Boolean(value)&&typeof value==='object'&&!Array.isArray(value);
const safeNumber=(value:unknown):value is number=>typeof value==='number'&&Number.isFinite(value);
const safeBox=(raw:unknown):raw is ReplayBox=>{
 if(!plain(raw))return false;
 const labels=['person','workbench','training_panel','multimeter','tool'];
 if(!labels.includes(String(raw.label)))return false;
 const {x,y,width,height,score}=raw;
 return [x,y,width,height,score].every(safeNumber)
   && (x as number)>=0&&(y as number)>=0&&(width as number)>0&&(height as number)>0
   && (x as number)+(width as number)<=1.000001
   && (y as number)+(height as number)<=1.000001
   && (score as number)>=0&&(score as number)<=1;
};

export function validateReplayReceipt(raw:unknown,sourceSha:string):ReplayModelReceipt|null{
 if(!plain(raw)||raw.schema!=='KW_REPLAY_MODEL_RECEIPT_V1'||raw.source_sha256!==sourceSha
   ||raw.source_kind!=='PROCEDURALLY_GENERATED_RECORDING_NOT_REAL_CCTV'
   ||raw.provider!=='operator-supplied'||!SHA.test(String(raw.model_sha256||''))
   ||!SHA.test(String(raw.profile_sha256||''))
   ||!Array.isArray(raw.samples)||raw.samples.length===0||raw.samples.length>MAX_SAMPLES)return null;
 let last=-1;
 const samples:ReplaySample[]=[];
 for(const entry of raw.samples){
   if(!plain(entry)||!safeNumber(entry.second)||entry.second<0||entry.second>=20
     ||entry.second<=last||!safeNumber(entry.frame)||!Number.isSafeInteger(entry.frame)||entry.frame<0
     ||!Array.isArray(entry.boxes)||entry.boxes.length>MAX_BOXES||!entry.boxes.every(safeBox))return null;
   const second=entry.second;
   const frame=entry.frame as number;
   // Frame time is from the 12-FPS procedural clip; arbitrary timestamps
   // cannot be used to paint detections over unrelated video frames.
   if(Math.abs(second-frame/12)>0.05||frame>=240)return null;
   last=second;
   samples.push({second,frame,boxes:(entry.boxes as ReplayBox[]).map(b=>({
     label:b.label,score:b.score,x:b.x,y:b.y,width:b.width,height:b.height,
   }))});
 }
 return {
   provider:'operator-supplied',model_sha256:String(raw.model_sha256),
   profile_sha256:String(raw.profile_sha256),samples,
 };
}

export async function loadReplayCatalog(root=process.cwd()):Promise<ReplayCatalog>{
 const blocked=():ReplayCatalog=>({
   schema:'KW_SOURCE_LOCKED_REPLAY_V1',kind:'synthetic_quality_demonstration',
   status:'blocked',physical_camera_accuracy_qualified:false,
   private_video_available:false,source_match_is_model_validation:false,
   clips:CLIPS.map(c=>({...c,duration:20,fps:12,sha256:null,source_url:null,
     status:'blocked' as const,receipt_status:'absent' as const,receipt:null})),
 });
 let manifest:unknown;
 try{
   const bytes=await readFile(path.join(root,'public','camera-trust','manifest.json'));
   if(bytes.length>20_000)return blocked();
   manifest=JSON.parse(bytes.toString('utf8'));
 }catch{return blocked();}
 if(!plain(manifest)||manifest.schema!=='KW_SUBMISSION_SAMPLE_MEDIA_V1'
   ||manifest.provenance!==EXPECTED_PROVENANCE||!plain(manifest.clips)
   ||Object.keys(manifest.clips).length!==CLIPS.length)return blocked();
 const clips:ReplayClip[]=[];
 for(const clip of CLIPS){
   const item=manifest.clips[clip.id];
   const expected=plain(item)?item.sha256:null;
   let valid=typeof expected==='string'&&SHA.test(expected);
   if(valid){
     try{
       const bytes=await readFile(path.join(root,'public','camera-trust',clip.id+'.mp4'));
       if(bytes.length<10_000||bytes.length>MAX_VIDEO)valid=false;
       else valid=createHash('sha256').update(bytes).digest('hex')===expected;
     }catch{valid=false;}
   }
   let receipt:ReplayModelReceipt|null=null;
   let receipt_status:ReplayClip['receipt_status']='absent';
   if(valid){
     try{
       // Operator-imported receipts must remain outside the publicly served
       // directory and are never blindly returned to the browser.
       const file=await readFile(path.join(root,'.controlled-replay','receipts',clip.id+'.json'));
       if(file.length<=MAX_RECEIPT){
         receipt=validateReplayReceipt(JSON.parse(file.toString('utf8')),expected as string);
       }
       receipt_status=receipt?'matched_unqualified':'rejected';
     }catch(e){
       const err=e as NodeJS.ErrnoException;
       receipt_status=err?.code==='ENOENT'?'absent':'rejected';
     }
   }
   clips.push({
     ...clip,duration:20,fps:12,
     sha256:valid?expected as string:null,
     source_url:valid?'/camera-trust/'+clip.id+'.mp4':null,
     status:valid?'verified':'blocked',receipt_status,receipt,
   });
 }
 return {
   schema:'KW_SOURCE_LOCKED_REPLAY_V1',kind:'synthetic_quality_demonstration',
   status:clips.every(c=>c.status==='verified')?'ready':'blocked',
   physical_camera_accuracy_qualified:false,private_video_available:false,
   source_match_is_model_validation:false,clips,
 };
}
