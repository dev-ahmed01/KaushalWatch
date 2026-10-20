/** Private source-bound numeric camera cue trace, never field accuracy. */
import {lstat,readFile,realpath} from 'node:fs/promises';
import path from 'node:path';
import {checkedResearchClips} from './research-replay.ts';

const SHA=/^[a-f0-9]{64}$/;
const IDS=['quality-covered','quality-defocused','quality-moved','quality-normal'];
const USABILITY=new Set([
 'NOT_USABLE_FOR_VISUAL_VERIFICATION','REVIEW_REQUIRED_SCENE_ALIGNMENT',
 'UNKNOWN_NO_REFERENCE','UNKNOWN_SCENE_REGISTRATION','PROVISIONALLY_OBSERVABLE',
]);
const INTERFERENCE=new Set([
 'POSSIBLE_SCENE_INTERFERENCE_REVIEW','UNKNOWN_NO_REFERENCE','NOT_ESTABLISHED',
]);
const REASONS=new Set([
 'VISIBILITY_DEGRADED','FOCUS_DEGRADED','LOCAL_VIEW_OBSCURED',
 'REFERENCE_SCENE_CHANGED','REFERENCE_REQUIRED','NO_RELIABLE_SCENE_MATCH',
 'NO_SEVERE_QUALITY_LOSS_OBSERVED',
]);
const plain=(v:unknown):v is Record<string,unknown>=>
 Boolean(v)&&typeof v==='object'&&!Array.isArray(v);
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
export type TraceSample={
 second:number;frame0:number;annotation_in_event:boolean;usability:string;
 interference_review:string;reason:string;
};
export type TraceClip={id:string;source_sha256:string;samples:TraceSample[];
 counts:{evidence_unusable:number;possible_interference:number;annotation_event_samples:number}};
export type TraceCatalog={
 schema:'KW_PRIVATE_RESEARCH_TRIAGE_TRACE_STATUS_V1';
 status:'ready';source_kind:'previously_inspected_research_not_field_validation';
 numeric_heuristic_trace:true;independent_holdout:false;
 physical_tamper_proven:false;reference_custody_verified:false;
 clips:TraceClip[];
};

export async function researchTrace(root:string):Promise<TraceCatalog>{
 const approved=await checkedResearchClips(root);
 if(!path.isAbsolute(root))throw new Error('No approved private cache');
 const home=await realpath(root);
 const source=path.join(home,'kw-research-analysis.local.json');
 const stat=await lstat(source);
 if(!stat.isFile()||stat.isSymbolicLink()||stat.size<1000||stat.size>400_000)
   throw new Error('No bounded research trace');
 const data:unknown=JSON.parse((await readFile(source)).toString('utf8'));
 if(!plain(data)||data.schema!=='KW_PRIVATE_RESEARCH_TRIAGE_TRACE_V1'
   ||data.source_collection!=='MEVA_UHCTD_DAY3_PREVIOUSLY_INSPECTED_DEVELOPMENT'
   ||data.heuristic_policy!=='CAMERA_QUALITY_SPLIT_V1_UNVERIFIED_FIRST_FRAME'
   ||data.research_only!==true||data.independent_holdout!==false
   ||data.training_centre_validation!==false
   ||data.reference_source!=='UNVERIFIED_FIRST_VIDEO_FRAME'
   ||data.model_accuracy_qualified!==false
   ||data.automatic_enforcement_authorized!==false
   ||data.sampling!=='ONE_FPS_SPARSE_LOCAL_DECODE'
   ||!Array.isArray(data.clips)||data.clips.length!==4)
   throw new Error('Research trace provenance invalid');
 const byId=new Map<string,unknown>();
 for(const item of data.clips){
   if(!plain(item)||typeof item.id!=='string'||byId.has(item.id)
     ||!IDS.includes(item.id))throw new Error('Unsupported trace identity');
   byId.set(item.id,item);
 }
 const clips:TraceClip[]=[];
 for(const c of approved){
   const sourceClip=byId.get(c.visible.id);
   if(!plain(sourceClip))throw new Error('Unverified research clip');
   const frameCount=sourceClip.frame_count;
   const suppliedCounts=sourceClip.counts;
   if(!plain(sourceClip)||sourceClip.source_sha256!==c.visible.source_sha256
     ||!SHA.test(String(sourceClip.source_sha256))
     ||!finite(sourceClip.duration_seconds)
     ||Math.abs(sourceClip.duration_seconds-c.visible.duration_seconds)>.02
     ||typeof frameCount!=='number'||!Number.isSafeInteger(frameCount)
     ||frameCount<60||frameCount>900
     ||!finite(sourceClip.fps)||Math.abs(sourceClip.fps-3)>.02
     ||Math.abs(frameCount/sourceClip.fps-c.visible.duration_seconds)>1.5
     ||!Array.isArray(sourceClip.samples)
     ||sourceClip.samples.length<10||sourceClip.samples.length>300
     ||!plain(suppliedCounts))
     throw new Error('Trace not aligned to source');
   const samples:TraceSample[]=[];
   let previous=-3;
   for(const item of sourceClip.samples){
     if(!plain(item)||!Number.isSafeInteger(item.frame0)
       ||item.frame0!==previous+3
       ||item.frame0<0||item.frame0>=frameCount
       ||!finite(item.second)
       ||Math.abs(item.second-item.frame0/sourceClip.fps)>.03
       ||typeof item.annotation_in_event!=='boolean'
       ||!USABILITY.has(String(item.usability))
       ||!INTERFERENCE.has(String(item.interference_review))
       ||!REASONS.has(String(item.reason)))
        throw new Error('Invalid or non-monotone numeric frame cue');
     const inside=c.visible.event_start_seconds!==null &&
       item.second>=c.visible.event_start_seconds &&
       item.second<(c.visible.event_end_seconds??0);
     if(item.annotation_in_event!==inside)throw new Error('Trace annotation drift');
     previous=item.frame0;
     samples.push({
       second:item.second as number,frame0:item.frame0 as number,
       annotation_in_event:item.annotation_in_event as boolean,
       usability:item.usability as string,
       interference_review:item.interference_review as string,
       reason:item.reason as string,
     });
   }
   if(Math.abs(sourceClip.samples.length-Math.ceil(frameCount/3))>1)
      throw new Error('Incomplete sampled trace');
   const counts={
     evidence_unusable:samples.filter(s=>s.usability==='NOT_USABLE_FOR_VISUAL_VERIFICATION').length,
     possible_interference:samples.filter(s=>s.interference_review==='POSSIBLE_SCENE_INTERFERENCE_REVIEW').length,
     annotation_event_samples:samples.filter(s=>s.annotation_in_event).length,
   };
   if(Object.keys(sourceClip.counts).length!==3
     ||Object.entries(counts).some(([k,v])=>suppliedCounts[k]!==v))
      throw new Error('Inconsistent trace summary');
   clips.push({id:c.visible.id,source_sha256:c.visible.source_sha256,
               samples,counts});
 }
 return {
   schema:'KW_PRIVATE_RESEARCH_TRIAGE_TRACE_STATUS_V1',
   status:'ready',source_kind:'previously_inspected_research_not_field_validation',
   numeric_heuristic_trace:true,independent_holdout:false,
   physical_tamper_proven:false,reference_custody_verified:false,clips,
 };
}
