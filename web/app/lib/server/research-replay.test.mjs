import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {checkedResearchClips,localResearchPermitted,researchCatalog} from './research-replay.ts';

const names=[
 ['quality-covered','covered_gentle_frame721_onset.mp4','covered'],
 ['quality-defocused','defocused_strong_frame166275_onset.mp4','defocused'],
 ['quality-moved','moved_gentle_frame7919_onset.mp4','moved'],
 ['quality-normal','normal_control_1.mp4','normal'],
];
const digest=data=>createHash('sha256').update(data).digest('hex');
async function fixture(run){
 const root=await mkdtemp(path.join(tmpdir(),'kw-private-source-'));
 const clips=[];
 for(let i=0;i<names.length;i++){
   const [id,filename,category]=names[i];
   const bytes=Buffer.concat([Buffer.from('0000ftypisom'),Buffer.alloc(12000,i+1)]);
   await writeFile(path.join(root,filename),bytes);
   clips.push({id,filename,name:category,annotation_class:category,
     source_sha256:digest(bytes),bytes:bytes.length,fps:3,
     duration_seconds:50.333,event_start_seconds:i===3?null:7,
     event_end_seconds:i===3?null:33});
 }
 const info={schema:'KW_RESEARCH_REPLAY_V1',
  provenance:'MEVA_UHCTD_RESEARCH_ANNOTATIONS_NOT_SKILL_CENTRE',
  annotation_origin:'existing_Meva_UHCTD_Day3_selected_clips_csv',
  model_inference_qualified:false,training_centre_provenance:false,
  independent_field_validation:false,clips};
 await writeFile(path.join(root,'kw-research-replay.local.json'),JSON.stringify(info));
 try{await run({root,clips,info});}finally{await rm(root,{recursive:true,force:true});}
}

test('reads four private sources and returns no filenames/Drive ids',async()=>{
 await fixture(async({root})=>{
   const result=await researchCatalog({KAUSHALWATCH_RESEARCH_REPLAY_DIR:root});
   assert.equal(result.status,'ready');
   assert.equal(result.training_centre_validation,false);
   assert.equal(result.model_inference_qualified,false);
   assert.equal(result.clips.length,4);
   for(const clip of result.clips){
      assert.match(clip.source_url,/^\/api\/demo\/research-replay\/quality-[a-z]+\/media$/);
      assert.match(clip.source_sha256,/^[a-f0-9]{64}$/);
      assert.equal(clip.source_type,'research_annotation_not_model_inference');
   }
   assert.equal(JSON.stringify(result).includes('.mp4'),false);
 });
});

test('tampered cache or annotation blocks every source',async()=>{
 await fixture(async({root,clips,info})=>{
   await writeFile(path.join(root,clips[0].filename),
     Buffer.concat([Buffer.from('0000ftypisom'),Buffer.alloc(12000,99)]));
   await assert.rejects(()=>checkedResearchClips(root));
   info.clips[0].source_sha256=digest(
      Buffer.concat([Buffer.from('0000ftypisom'),Buffer.alloc(12000,99)]));
   info.clips[0].event_start_seconds=45;
   info.clips[0].event_end_seconds=30;
   await writeFile(path.join(root,'kw-research-replay.local.json'),JSON.stringify(info));
   await assert.rejects(()=>checkedResearchClips(root));
 });
});

test('research endpoint denied unless explicitly local and unprotected',()=>{
 const env={KAUSHALWATCH_LOCAL_RESEARCH_REPLAY:'true',KAUSHALWATCH_ENV:'development'};
 const h=new Headers({host:'localhost:3000','sec-fetch-site':'same-origin'});
 assert.equal(localResearchPermitted(env,h),true);
 assert.equal(localResearchPermitted({...env,KAUSHALWATCH_ENV:'staging'},h),false);
 assert.equal(localResearchPermitted({...env,KAUSHALWATCH_WEB_AUTH_MODE:'protected'},h),false);
 assert.equal(localResearchPermitted({...env,NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY:'true'},h),false);
 assert.equal(localResearchPermitted({...env,KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT:'true'},h),false);
 assert.equal(localResearchPermitted({...env,KAUSHALWATCH_LOCAL_RESEARCH_REPLAY:'false'},h),false);
 assert.equal(localResearchPermitted(env,new Headers({host:'public.example.com'})),false);
 assert.equal(localResearchPermitted(env,new Headers({host:'localhost:3000','x-forwarded-host':'public.example.com'})),false);
 assert.equal(localResearchPermitted(env,new Headers({host:'localhost:3000','sec-fetch-site':'cross-site'})),false);
});
