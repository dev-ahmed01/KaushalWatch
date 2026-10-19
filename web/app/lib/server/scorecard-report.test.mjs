import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,symlink,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {localScorecardAllowed,parseTrustScorecard,readTrustScorecard} from './scorecard-report.ts';

const kinds=['attendance','camera_trust','equipment_count','equipment_localization','practical_activity','offline_transport'];
const blocked=(id)=>({id,state:'not_qualified',metric:null,support:null,reason:'Unverified'});
const fixture=()=>({
 schema:'KW_PROOF_OF_TRAINING_SCORECARD_V1',
 status:'evidence_gates_reported_not_field_qualified',
 qualified:false,scope:'controlled_source_receipts_not_field_certification',
 receipt_sha256:{},limitations:'No independent signed measurements.',
 pillars:Object.fromEntries(kinds.map(id=>[id,blocked(id)])),
});
const headers=(host='localhost:3000')=>new Headers({host,origin:'http://'+host});

test('protected/public routes never expose private judge-day scorecards',()=>{
 const env={KAUSHALWATCH_ENV:'development',KAUSHALWATCH_LOCAL_SCORECARD:'true'};
 assert.equal(localScorecardAllowed(env,headers()),true);
 assert.equal(localScorecardAllowed({...env,KAUSHALWATCH_ENV:'production'},headers()),false);
 assert.equal(localScorecardAllowed({...env,NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY:'true'},headers()),false);
 assert.equal(localScorecardAllowed({...env,KAUSHALWATCH_WEB_AUTH_MODE:'protected'},headers()),false);
 assert.equal(localScorecardAllowed(env,headers('evil.site')),false);
 assert.equal(localScorecardAllowed({...env,KAUSHALWATCH_LOCAL_SCORECARD:'false'},headers()),false);
});

test('refuse made-up qualified accuracy in apparently valid private report',()=>{
 assert.equal(parseTrustScorecard(fixture()).qualified,false);
 for(const edit of [
  (s)=>s.qualified=true,(s)=>s.pillars.attendance.metric={mae:0.2},
  (s)=>s.pillars.equipment_count.state='certified',
  (s)=>s.status='externally_approved',
 ]){const doc=fixture();edit(doc);assert.throws(()=>parseTrustScorecard(doc));}
});

test('admit only measured local bytes and provisional IoU, never independent approval',()=>{
 const doc=fixture();
 doc.pillars.offline_transport={
  id:'offline_transport',state:'measured_loopback_fixture_only',
  metric:{request_body_bytes:567,response_body_bytes:155,delivered:2,queued:2},
  support:{network_cut_verified:true},reason:'Observed local HTTP only',
 };
 doc.pillars.equipment_localization={
  id:'equipment_localization',state:'candidate_measured_not_independently_qualified',
  metric:{tp:2,fp:1,fn:1,
   per_class:{training_panel:{tp:2,fp:1,fn:1,precision:2/3,recall:2/3}}},
  support:{recordings:4},reason:'No external audit',
 };
 assert.equal(parseTrustScorecard(doc).pillars.offline_transport.metric.delivered,2);
 doc.pillars.equipment_localization.metric.tp=200;
 assert.throws(()=>parseTrustScorecard(doc),/total mismatch/);
});

test('a private scorecard cannot be symlinked or tampered with',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'kw-phase5-'));
 const file=path.join(dir,'scorecard.json'),link=path.join(dir,'alias.json');
 try{
  await writeFile(file,JSON.stringify(fixture()));
  assert.equal((await readTrustScorecard(file)).qualified,false);
  await symlink(file,link);
  await assert.rejects(()=>readTrustScorecard(link));
  await writeFile(file,JSON.stringify({...fixture(),qualified:true}));
  await assert.rejects(()=>readTrustScorecard(file));
 }finally{await rm(dir,{recursive:true,force:true});}
});
