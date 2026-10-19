/** Private operator-supplied equipment video + model-output receipt admission.
 * Source matching is NOT independent model execution or accuracy certification.
 */
import {createHash} from 'node:crypto';
import {lstat,readFile,realpath} from 'node:fs/promises';
import path from 'node:path';

const SHA=/^[a-f0-9]{64}$/;
const CLASSES=['workbench','chair','training_panel','drill_machine'] as const;
const digest=(bytes:Buffer)=>createHash('sha256').update(bytes).digest('hex');
const obj=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const num=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const str=(v:unknown,n=200):v is string=>typeof v==='string'&&v.trim().length>=8&&v.length<=n;
const hash=(v:unknown):v is string=>typeof v==='string'&&SHA.test(v);
export type EquipmentBox={label:string;score:number;x:number;y:number;width:number;height:number};
export type EquipmentSample={second:number;detections:EquipmentBox[];counts:{id:string;count:number}[]};
export type EquipmentCatalog={
 schema:'KW_PRIVATE_EQUIPMENT_REPLAY_V1';status:'source_and_receipt_matched_unqualified';
 source_type:'operator_supplied_research_or_approved_video';
 training_centre_certified:false;model_execution_independently_verified:false;
 independent_accuracy_qualified:false;equipment_compliance_qualified:false;
 camera_quality_independently_verified:false;
 video_url:string;source_sha256:string;receipt_sha256:string;
 source_origin:string;permission_basis:string;privacy_basis:string;
 width:number;height:number;duration:number;roi:{x:number;y:number;width:number;height:number};
 model_artifact_count:number;timestamps:EquipmentSample[];
};
export function equipmentReplayAllowed(env:NodeJS.ProcessEnv,headers:Headers):boolean{
 const mode=(env.KAUSHALWATCH_ENV||'').toLowerCase(),host=headers.get('host')||'';
 const forwarded=headers.get('x-forwarded-host'),origin=headers.get('origin');
 let allowedOrigin=true;
 if(origin){
   try{const parsed=new URL(origin);allowedOrigin=parsed.host===host&&['http:','https:'].includes(parsed.protocol);}
   catch{allowedOrigin=false;}
 }
 return env.KAUSHALWATCH_LOCAL_EQUIPMENT_REPLAY==='true'
   && ['development','local','test'].includes(mode)
   && env.NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY!=='true'
   && env.KAUSHALWATCH_WEB_AUTH_MODE!=='protected'
   && env.KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT!=='true'
   && /^(localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?$/.test(host.toLowerCase())
   && (!forwarded||forwarded===host)
   && headers.get('sec-fetch-site')!=='cross-site'&&allowedOrigin;
}
async function localFile(dir:string,name:string,limit:number):Promise<Buffer>{
 const p=path.join(dir,name),stat=await lstat(p);
 if(!stat.isFile()||stat.isSymbolicLink()||stat.size<20||stat.size>limit)
   throw Error('Missing or untrusted replay file');
 return readFile(p);
}
function parseReceipt(raw:unknown,sha:string,width:number,height:number,duration:number){
 if(!obj(raw)||raw.status!=='live_unreviewed_equipment_proposals'
   ||raw.qualified!==false||raw.model_inference_executed!==true
   ||raw.source_video_sha256!==sha||!hash(raw.frozen_manifest_sha256)
   ||!obj(raw.model_snapshot_sha256)
   ||Object.keys(raw.model_snapshot_sha256).length<2
   ||Object.keys(raw.model_snapshot_sha256).length>80
   ||!Object.values(raw.model_snapshot_sha256).every(hash)
   ||!Array.isArray(raw.proposal_rows)||raw.proposal_rows.length<1||raw.proposal_rows.length>48)
   throw Error('Invalid operator-supplied detector receipt');
 const samples:EquipmentSample[]=[];
 let last=-1,reference:string|null=null;
 for(const row of raw.proposal_rows){
   if(!obj(row)||!num(row.second)||row.second<0||row.second>=duration
     ||row.second<=last||row.source!=='groundingdino_local_pinned_unreviewed'
     ||!Array.isArray(row.detections)||row.detections.length<1
     ||row.detections.length>CLASSES.length)throw Error('Invalid source-bound sample');
   last=row.second;
   const boxes:EquipmentBox[]=[],counts:EquipmentSample['counts']=[];
   const seen=new Set<string>();
   for(const d of row.detections){
     if(!obj(d)||typeof d.label!=='string'||!CLASSES.includes(d.label as typeof CLASSES[number])
       ||seen.has(d.label)||d.proposal_status!=='unreviewed_model_proposal'
       ||typeof d.prompt!=='string'||d.prompt.length<2||d.prompt.length>200
       ||typeof d.count!=='number'||!Number.isSafeInteger(d.count)||d.count<0||d.count>250
       ||d.model_count!==d.count||!num(d.confidence)||d.confidence<0||d.confidence>1
       ||!Array.isArray(d.boxes)||!Array.isArray(d.scores)
       ||d.boxes.length!==d.count||d.scores.length!==d.count)
       throw Error('Invalid proposal class/count');
     seen.add(d.label);counts.push({id:d.label,count:d.count});
     for(let i=0;i<d.count;i++){
       const b=d.boxes[i],confidence=d.scores[i];
       if(!Array.isArray(b)||b.length!==4||!b.every(num)
         ||!num(confidence)||confidence<0||confidence>1)
         throw Error('Invalid model box');
       const [x1,y1,x2,y2]=b as number[];
       if(x1<0||y1<0||x2>width||y2>height||x2<=x1||y2<=y1)
         throw Error('Model box outside pinned frame');
       boxes.push({label:d.label,score:confidence,
         x:x1/width,y:y1/height,width:(x2-x1)/width,height:(y2-y1)/height});
     }
   }
   const names=[...seen].sort().join(',');
   if(reference===null)reference=names;
   else if(reference!==names)throw Error('Missing class is unknown, not zero');
   samples.push({second:row.second,detections:boxes,counts});
 }
 return {samples,modelCount:Object.keys(raw.model_snapshot_sha256).length};
}
export async function verifiedEquipmentReplay(root:string):Promise<{catalog:EquipmentCatalog;video:Buffer}>{
 if(!path.isAbsolute(root))throw Error('Approved absolute private replay root required');
 const dir=await realpath(root),app=await realpath(process.cwd());
 if(dir===app||dir.startsWith(app+path.sep)||dir.includes(path.sep+'public'+path.sep))
   throw Error('Private replay must be outside application and public directory');
 const entry=JSON.parse((await localFile(dir,'equipment-replay.local.json',12000)).toString('utf8')) as unknown;
 if(!obj(entry)||entry.schema!=='KW_EQUIPMENT_REPLAY_ADMISSION_V1'
   ||entry.video_filename!=='equipment.mp4'||entry.receipt_filename!=='live-proposals.json'
   ||!hash(entry.video_sha256)||!hash(entry.receipt_sha256)
   ||!str(entry.source_origin)||!str(entry.license_basis)||!str(entry.privacy_basis)
   ||typeof entry.width!=='number'||typeof entry.height!=='number'
   ||!Number.isSafeInteger(entry.width)||!Number.isSafeInteger(entry.height)
   ||entry.width<32||entry.height<32||entry.width>4096||entry.height>4096
   ||!num(entry.duration_seconds)||entry.duration_seconds<0.3||entry.duration_seconds>360
   ||!obj(entry.roi)||!str(entry.roi_basis))
   throw Error('Invalid media custody metadata');
 const roi=entry.roi;
 if(!num(roi.x)||!num(roi.y)||!num(roi.width)||!num(roi.height)
   ||roi.x<0||roi.y<0||roi.width<=0||roi.height<=0
   ||roi.x+roi.width>1||roi.y+roi.height>1)
   throw Error('Unreviewed ROI geometry');
 const video=await localFile(dir,'equipment.mp4',130_000_000);
 if(video.subarray(4,8).toString('utf8')!=='ftyp'||digest(video)!==entry.video_sha256)
   throw Error('Equipment source hash mismatch');
 const receipt=await localFile(dir,'live-proposals.json',700_000);
 if(digest(receipt)!==entry.receipt_sha256)throw Error('Inference receipt hash mismatch');
 const proposals=parseReceipt(JSON.parse(receipt.toString('utf8')),entry.video_sha256,
   entry.width,entry.height,entry.duration_seconds);
 return {video,catalog:{
   schema:'KW_PRIVATE_EQUIPMENT_REPLAY_V1',status:'source_and_receipt_matched_unqualified',
   source_type:'operator_supplied_research_or_approved_video',
   training_centre_certified:false,model_execution_independently_verified:false,
   independent_accuracy_qualified:false,equipment_compliance_qualified:false,
   camera_quality_independently_verified:false,
   video_url:'/api/demo/equipment-replay/media',source_sha256:entry.video_sha256,
   receipt_sha256:entry.receipt_sha256,
   source_origin:entry.source_origin,permission_basis:entry.license_basis,
   privacy_basis:entry.privacy_basis,width:entry.width,height:entry.height,
   duration:entry.duration_seconds,
   roi:{x:roi.x,y:roi.y,width:roi.width,height:roi.height},
   model_artifact_count:proposals.modelCount,timestamps:proposals.samples
 }};
}
