import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {equipmentReplayAllowed,verifiedEquipmentReplay} from './equipment-replay.ts';

const sha=(b)=>createHash('sha256').update(b).digest('hex');
async function fixture(callback){
 const root=await mkdtemp(path.join(tmpdir(),'kw-private-equipment-'));
 const video=Buffer.concat([Buffer.from('0000ftypisom'),Buffer.alloc(10001,0x12)]);
 const videoHash=sha(video);
 const raw={status:'live_unreviewed_equipment_proposals',qualified:false,
   model_inference_executed:true,source_video_sha256:videoHash,
   frozen_manifest_sha256:'f'.repeat(64),
   model_snapshot_sha256:{'model.safetensors':'a'.repeat(64),'config.json':'b'.repeat(64)},
   proposal_rows:[
     {second:0,source:'groundingdino_local_pinned_unreviewed',detections:[
       {label:'training_panel',prompt:'electrical switchboard',count:1,model_count:1,
         confidence:.8,boxes:[[10,8,80,65]],scores:[.8],proposal_status:'unreviewed_model_proposal'},
       {label:'drill_machine',prompt:'power drill',count:0,model_count:0,
         confidence:0,boxes:[],scores:[],proposal_status:'unreviewed_model_proposal'},
     ]},
     {second:1,source:'groundingdino_local_pinned_unreviewed',detections:[
       {label:'training_panel',prompt:'electrical switchboard',count:1,model_count:1,
         confidence:.9,boxes:[[12,10,82,66]],scores:[.9],proposal_status:'unreviewed_model_proposal'},
       {label:'drill_machine',prompt:'power drill',count:0,model_count:0,
         confidence:0,boxes:[],scores:[],proposal_status:'unreviewed_model_proposal'},
     ]}
   ]};
 const write=async()=>{
   await writeFile(path.join(root,'equipment.mp4'),video);
   const receipt=Buffer.from(JSON.stringify(raw));
   await writeFile(path.join(root,'live-proposals.json'),receipt);
   const manifest={schema:'KW_EQUIPMENT_REPLAY_ADMISSION_V1',
     video_filename:'equipment.mp4',receipt_filename:'live-proposals.json',
     video_sha256:videoHash,receipt_sha256:sha(receipt),
     source_origin:'synthetic CI electrical training room',
     license_basis:'synthetic fixture authored by the CI test runner',
     privacy_basis:'no people are present in generated test pixels',
     width:100,height:80,duration_seconds:2,
     roi:{x:0.05,y:0.05,width:0.9,height:0.9},
     roi_basis:'CI test coordinates for artificial source'};
   await writeFile(path.join(root,'equipment-replay.local.json'),JSON.stringify(manifest));
   return manifest;
 };
 const manifest=await write();
 try{await callback({root,raw,video,manifest,write});}
 finally{await rm(root,{recursive:true,force:true});}
}
test('local source and operator receipt admit exact boxes but never claim independent accuracy',async()=>{
 await fixture(async({root})=>{
   const {catalog,video}=await verifiedEquipmentReplay(root);
   assert.ok(video.length>10000);
   assert.equal(catalog.status,'source_and_receipt_matched_unqualified');
   assert.equal(catalog.training_centre_certified,false);
   assert.equal(catalog.model_execution_independently_verified,false);
   assert.equal(catalog.independent_accuracy_qualified,false);
   assert.equal(catalog.equipment_compliance_qualified,false);
   assert.equal(catalog.timestamps.length,2);
   assert.equal(catalog.timestamps[0].detections.length,1);
   assert.equal(catalog.timestamps[0].counts.find(x=>x.id==='drill_machine').count,0);
   assert.equal(catalog.timestamps[0].detections[0].x,.1);
   assert.equal(catalog.timestamps[0].detections[0].y,.1);
   assert.ok(!JSON.stringify(catalog).includes('equipment.mp4'));
   assert.ok(!JSON.stringify(catalog).includes('synthetic CI electrical training room'+path.sep));
 });
});
test('tampering video/receipt, unreviewed ROI and source outside admitted cache fail closed',async()=>{
 await fixture(async({root,raw,manifest,write})=>{
   await writeFile(path.join(root,'equipment.mp4'),Buffer.alloc(10200,0x19));
   await assert.rejects(()=>verifiedEquipmentReplay(root));
   await write();
   raw.proposal_rows[0].detections[0].boxes=[[98,2,110,20]];
   await writeFile(path.join(root,'live-proposals.json'),Buffer.from(JSON.stringify(raw)));
   manifest.receipt_sha256=sha(Buffer.from(JSON.stringify(raw)));
   await writeFile(path.join(root,'equipment-replay.local.json'),JSON.stringify(manifest));
   await assert.rejects(()=>verifiedEquipmentReplay(root));
   raw.proposal_rows[0].detections[0].boxes=[[10,8,80,65]];
   await write();
   const mutated={...manifest,roi:{x:.4,y:.4,width:.9,height:.9}};
   await writeFile(path.join(root,'equipment-replay.local.json'),JSON.stringify(mutated));
   await assert.rejects(()=>verifiedEquipmentReplay(root));
 });
});
test('missing class, duplicate time, and fake model status never become negative detections',async()=>{
 await fixture(async({root,raw,write})=>{
   raw.proposal_rows[1].detections.pop();
   await write();
   await assert.rejects(()=>verifiedEquipmentReplay(root));
   raw.proposal_rows[1].detections.push(structuredClone(raw.proposal_rows[0].detections[1]));
   raw.proposal_rows[1].second=0;
   await write();
   await assert.rejects(()=>verifiedEquipmentReplay(root));
   raw.proposal_rows[1].second=1;
   raw.model_inference_executed=false;
   await write();
   await assert.rejects(()=>verifiedEquipmentReplay(root));
 });
});
test('private replay is gated to explicit local development and same-origin requests',()=>{
 const enabled={KAUSHALWATCH_ENV:'development',KAUSHALWATCH_LOCAL_EQUIPMENT_REPLAY:'true'};
 const headers=new Headers({host:'localhost:3000','sec-fetch-site':'same-origin'});
 assert.equal(equipmentReplayAllowed(enabled,headers),true);
 assert.equal(equipmentReplayAllowed({},headers),false);
 for(const mode of ['pilot','staging','prod','production']){
   assert.equal(equipmentReplayAllowed({...enabled,KAUSHALWATCH_ENV:mode},headers),false);
 }
 assert.equal(equipmentReplayAllowed({...enabled,KAUSHALWATCH_WEB_AUTH_MODE:'protected'},headers),false);
 assert.equal(equipmentReplayAllowed({...enabled,NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY:'true'},headers),false);
 assert.equal(equipmentReplayAllowed({...enabled,KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT:'true'},headers),false);
 for(const bad of [
   {host:'external.example.org'},
   {host:'localhost:3000','x-forwarded-host':'external.example.org'},
   {host:'localhost:3000','sec-fetch-site':'cross-site'},
   {host:'localhost:3000',origin:'https://evil.example'},
 ])assert.equal(equipmentReplayAllowed(enabled,new Headers(bad)),false);
});
