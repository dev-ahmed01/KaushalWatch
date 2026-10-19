import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {buildTradeProof,loadTradeProof,localTradePermitted} from './trade-proof.ts';

const root=path.resolve(process.cwd(),'..');
const manifestPath=path.join(root,'configs/job_roles/construction_electrician.demo.json');
const cachePath=path.join(root,'demo/cached_detections/construction_electrician.example.json');
const originals=async()=>[
  JSON.parse(await readFile(manifestPath,'utf8')),
  JSON.parse(await readFile(cachePath,'utf8')),
];
const check=(m,c)=>buildTradeProof(m,c,'a'.repeat(64),'b'.repeat(64));

test('manifest-derived example has correct simulated quantities and class-specific gates',async()=>{
 const result=await loadTradeProof(root);
 assert.equal(result.job_role_code,'CON/Q0603');
 assert.equal(result.status,'illustrative_only');
 assert.equal(result.counts_are_simulated,true);
 assert.equal(result.model_run_verified,false);
 assert.equal(result.camera_quality_verified,false);
 assert.equal(result.video_source_sha256,null);
 assert.equal(result.independent_per_class_tp_fp_fn,null);
 assert.equal(result.external_work_authorization,'unknown');
 assert.deepEqual(result.sampling_seconds,[0,10,20]);
 assert.equal(result.items.length,5);
 const byId=Object.fromEntries(result.items.map(x=>[x.id,x]));
 assert.equal(byId.training_panel.required,4);
 assert.equal(byId.training_panel.example_observed,3);
 assert.equal(byId.training_panel.example_state,'illustrative_gap');
 assert.deepEqual(byId.training_panel.sample_counts.map(x=>x.count),[3,3,3]);
 assert.equal(byId.workbench.required,4);
 assert.equal(byId.workbench.example_state,'illustrative_alignment');
 assert.equal(byId.chair.required,12);
 assert.equal(byId.drill_machine.required,1);
 assert.equal(byId.drill_machine.verification_tier,'camera_partially_verifiable');
 assert.equal(byId.multimeter.required,6);
 assert.equal(byId.multimeter.example_observed,null);
 assert.equal(byId.multimeter.sample_counts.length,0);
 assert.equal(byId.multimeter.example_state,'manual_officer_check');
});

test('rejects unqualified source-manifest changes, missing samples and invented labels',async()=>{
 const [m,c]=await originals();
 const changed=structuredClone(m);
 changed.quantities_status='sanctioned';
 assert.throws(()=>check(changed,c));
 const wrongRole=structuredClone(m);wrongRole.job_role_code='CON/OTHER';
 assert.throws(()=>check(wrongRole,c));
 const duplicate=structuredClone(m);duplicate.items[4].id='chair';
 assert.throws(()=>check(duplicate,c));
 const missing=structuredClone(c);missing[1].detections.pop();
 assert.throws(()=>check(m,missing));
 const custom=structuredClone(c);custom[0].detections[0].label='face_identity';
 assert.throws(()=>check(m,custom));
 const repeated=structuredClone(c);repeated[1].second=0;
 assert.throws(()=>check(m,repeated));
 const invalid=structuredClone(c);invalid[2].detections[0].confidence=NaN;
 assert.throws(()=>check(m,invalid));
});

test('negative and zero counts remain illustrative observations not definitive violations',async()=>{
 const [m,c]=await originals();
 const withZero=structuredClone(c);
 for(const row of withZero)row.detections.find(x=>x.label==='training_panel').count=0;
 const report=check(m,withZero);
 const item=report.items.find(x=>x.id==='training_panel');
 assert.equal(item.example_observed,0);
 assert.equal(item.example_state,'illustrative_gap');
 assert.equal(report.video_source_sha256,null);
 assert.equal(report.independent_per_class_tp_fp_fn,null);
});

test('protected and pilot environments cannot request controlled trade fixtures',()=>{
 assert.equal(localTradePermitted({}),true);
 assert.equal(localTradePermitted({KAUSHALWATCH_ENV:'development'}),true);
 for(const stage of ['staging','pilot','prod','production'])
   assert.equal(localTradePermitted({KAUSHALWATCH_ENV:stage}),false);
 assert.equal(localTradePermitted({KAUSHALWATCH_WEB_AUTH_MODE:'protected'}),false);
 assert.equal(localTradePermitted({NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY:'true'}),false);
 assert.equal(localTradePermitted({KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT:'true'}),false);
});
