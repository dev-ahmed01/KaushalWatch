import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {researchTrace} from './research-analysis.ts';

const sourceNames=[
 ['quality-covered','covered_gentle_frame721_onset.mp4','covered'],
 ['quality-defocused','defocused_strong_frame166275_onset.mp4','defocused'],
 ['quality-moved','moved_gentle_frame7919_onset.mp4','moved'],
 ['quality-normal','normal_control_1.mp4','normal'],
];
const digest=b=>createHash('sha256').update(b).digest('hex');
async function fixture(run){
 const root=await mkdtemp(path.join(tmpdir(),'kw-source-trace-'));
 const sources=[];
 for(let i=0;i<4;i++){
  const [id,filename,category]=sourceNames[i];
  const bytes=Buffer.concat([Buffer.from('0000ftypisom'),Buffer.alloc(12500,i+1)]);
  await writeFile(path.join(root,filename),bytes);
  sources.push({id,filename,name:category,annotation_class:category,
    source_sha256:digest(bytes),bytes:bytes.length,fps:3,
    duration_seconds:47,event_start_seconds:i===3?null:12.333,
    event_end_seconds:i===3?null:47});
 }
 const sourceCatalog={
  schema:'KW_RESEARCH_REPLAY_V1',
  provenance:'MEVA_UHCTD_RESEARCH_ANNOTATIONS_NOT_SKILL_CENTRE',
  annotation_origin:'existing_Meva_UHCTD_Day3_selected_clips_csv',
  model_inference_qualified:false,training_centre_provenance:false,
  independent_field_validation:false,clips:sources,
 };
 await writeFile(path.join(root,'kw-research-replay.local.json'),JSON.stringify(sourceCatalog));
 const clips=sources.map(c=>{
  const samples=Array.from({length:47},(_,i)=>({
    frame0:i*3,second:i,
    annotation_in_event:c.event_start_seconds!==null&&i>=c.event_start_seconds,
    usability:i>=13&&c.id!=='quality-normal'?
      'NOT_USABLE_FOR_VISUAL_VERIFICATION':'PROVISIONALLY_OBSERVABLE',
    interference_review:'NOT_ESTABLISHED',
    reason:i>=13&&c.id!=='quality-normal'?'FOCUS_DEGRADED':
      'NO_SEVERE_QUALITY_LOSS_OBSERVED',
  }));
  return {id:c.id,source_sha256:c.source_sha256,duration_seconds:47,
   frame_count:141,fps:3,samples,
   counts:{
    evidence_unusable:samples.filter(s=>s.usability==='NOT_USABLE_FOR_VISUAL_VERIFICATION').length,
    possible_interference:0,
    annotation_event_samples:samples.filter(s=>s.annotation_in_event).length,
   }};
 });
 const trace={
  schema:'KW_PRIVATE_RESEARCH_TRIAGE_TRACE_V1',
  source_collection:'MEVA_UHCTD_DAY3_PREVIOUSLY_INSPECTED_DEVELOPMENT',
  heuristic_policy:'CAMERA_QUALITY_SPLIT_V1_UNVERIFIED_FIRST_FRAME',
  research_only:true,independent_holdout:false,
  training_centre_validation:false,
  reference_source:'UNVERIFIED_FIRST_VIDEO_FRAME',
  model_accuracy_qualified:false,automatic_enforcement_authorized:false,
  sampling:'ONE_FPS_SPARSE_LOCAL_DECODE',clips,
 };
 async function save(){await writeFile(path.join(root,'kw-research-analysis.local.json'),JSON.stringify(trace));}
 await save();
 try{await run({root,trace,sources,save});}
 finally{await rm(root,{recursive:true,force:true});}
}

test('accepts source-matched previously inspected traces while retaining uncertainty',async()=>{
 await fixture(async({root})=>{
  const result=await researchTrace(root);
  assert.equal(result.clips.length,4);
  assert.equal(result.independent_holdout,false);
  assert.equal(result.physical_tamper_proven,false);
  assert.equal(result.reference_custody_verified,false);
  assert.equal(result.clips[0].samples.length,47);
  assert.equal(result.clips[0].counts.annotation_event_samples,34);
  assert.equal(JSON.stringify(result).includes('.mp4'),false);
  assert.equal(JSON.stringify(result).includes('ftyp'),false);
 });
});

test('refuses altered private video digest, forged provenance and mismatched annotation',async()=>{
 await fixture(async({root,trace,sources,save})=>{
  trace.clips[0].source_sha256='a'.repeat(64);
  await save();
  await assert.rejects(()=>researchTrace(root),/source/);
  trace.clips[0].source_sha256=sources[0].source_sha256;
  trace.clips[0].samples[15].annotation_in_event=false;
  await save();
  await assert.rejects(()=>researchTrace(root),/annotation/);
  trace.clips[0].samples[15].annotation_in_event=true;
  trace.model_accuracy_qualified=true;
  await save();
  await assert.rejects(()=>researchTrace(root),/provenance/);
  trace.model_accuracy_qualified=false;
  await save();
  await writeFile(path.join(root,sources[0].filename),Buffer.alloc(12512,0));
  await assert.rejects(()=>researchTrace(root));
 });
});

test('refuses skipped or duplicated frames and forged aggregate counts',async()=>{
 await fixture(async({root,trace,save})=>{
  trace.clips[0].samples[3].frame0=100;
  await save();
  await assert.rejects(()=>researchTrace(root),/frame cue/);
  trace.clips[0].samples[3].frame0=9;
  trace.clips[0].counts.evidence_unusable=0;
  await save();
  await assert.rejects(()=>researchTrace(root),/summary/);
 });
});
