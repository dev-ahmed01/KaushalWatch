import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {loadReplayCatalog,localReplayPermitted,validateReplayReceipt} from './replay-catalog.ts';

const ids=['training-bay','workshop-floor','east-corridor'];
const hash=data=>createHash('sha256').update(data).digest('hex');
async function withMedia(run){
  const root=await mkdtemp(path.join(tmpdir(),'kw-replay-test-'));
  const dir=path.join(root,'public','camera-trust');
  await mkdir(dir,{recursive:true});
  const data=Buffer.alloc(11000,0x41);
  const clips={};
  for(const id of ids){
    await writeFile(path.join(dir,id+'.mp4'),data);
    clips[id]={sha256:hash(data)};
  }
  const manifest={schema:'KW_SUBMISSION_SAMPLE_MEDIA_V1',
    provenance:'PROCEDURALLY_GENERATED_RECORDING_NOT_REAL_CCTV',clips};
  await writeFile(path.join(dir,'manifest.json'),JSON.stringify(manifest));
  try{await run({root,dir,clips,manifest});}finally{await rm(root,{recursive:true,force:true});}
}
function receipt(source){
  return {schema:'KW_REPLAY_MODEL_RECEIPT_V1',
    source_kind:'PROCEDURALLY_GENERATED_RECORDING_NOT_REAL_CCTV',
    source_sha256:source,provider:'operator-supplied',
    model_sha256:'a'.repeat(64),profile_sha256:'b'.repeat(64),
    samples:[{second:0,frame:0,boxes:[{label:'person',score:0.73,x:0.2,y:0.1,width:0.3,height:0.5}]}]};
}

test('three exact synthetic hashes are required for playback',async()=>{
  await withMedia(async({root,dir})=>{
    const good=await loadReplayCatalog(root);
    assert.equal(good.status,'ready');
    assert.equal(good.clips.length,3);
    assert.ok(good.clips.every(x=>x.status==='verified'&&x.receipt===null));
    assert.equal(good.physical_camera_accuracy_qualified,false);
    await writeFile(path.join(dir,'training-bay.mp4'),Buffer.alloc(11000,0x42));
    const blocked=await loadReplayCatalog(root);
    assert.equal(blocked.status,'blocked');
    const bad=blocked.clips.find(x=>x.id==='training-bay');
    assert.equal(bad.source_url,null);
    assert.equal(bad.sha256,null);
  });
});

test('unknown source manifest entries and missing manifest block admission',async()=>{
  await withMedia(async({root,dir,manifest})=>{
    manifest.clips['unexpected-source']={sha256:'f'.repeat(64)};
    await writeFile(path.join(dir,'manifest.json'),JSON.stringify(manifest));
    assert.equal((await loadReplayCatalog(root)).status,'blocked');
    await rm(path.join(dir,'manifest.json'));
    assert.equal((await loadReplayCatalog(root)).status,'blocked');
  });
});

test('production and protected environments cannot enable controlled replay',()=>{
  assert.equal(localReplayPermitted({}),true);
  for(const env of ['staging','pilot','production','prod'])
    assert.equal(localReplayPermitted({KAUSHALWATCH_ENV:env}),false);
  assert.equal(localReplayPermitted({NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY:'true'}),false);
  assert.equal(localReplayPermitted({KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT:'true'}),false);
});

test('receipt requires matching SHA, model, profile, frame and bounds',()=>{
  const src='c'.repeat(64);
  const good=receipt(src);
  assert.equal(validateReplayReceipt(good,src).samples[0].boxes[0].score,0.73);
  assert.equal(validateReplayReceipt(good,'d'.repeat(64)),null);
  const mutations=[
    {...good,model_sha256:'bad'},
    {...good,profile_sha256:'bad'},
    {...good,source_kind:'unknown'},
    {...good,samples:[{...good.samples[0],frame:1}]},
    {...good,samples:[{...good.samples[0],second:20}]},
    {...good,samples:[{...good.samples[0],boxes:[{...good.samples[0].boxes[0],x:0.9}]}]},
    {...good,samples:[{...good.samples[0],boxes:[{...good.samples[0].boxes[0],score:2}]}]},
    {...good,samples:[{...good.samples[0],boxes:[{...good.samples[0].boxes[0],label:'identity'}]}]},
    {...good,samples:[good.samples[0],good.samples[0]]},
  ];
  for(const bad of mutations)assert.equal(validateReplayReceipt(bad,src),null);
});

test('only validated receipt fields are returned and invalid operator receipts excluded',async()=>{
  await withMedia(async({root,clips})=>{
    const folder=path.join(root,'.controlled-replay','receipts');
    await mkdir(folder,{recursive:true});
    const original=receipt(clips['training-bay'].sha256);
    original.extra='TEST_ONLY_UNRECOGNIZED_FIELD';
    await writeFile(path.join(folder,'training-bay.json'),JSON.stringify(original));
    const matched=await loadReplayCatalog(root);
    assert.equal(matched.clips[0].receipt_status,'matched_unqualified');
    assert.equal(JSON.stringify(matched).includes('TEST_ONLY_UNRECOGNIZED_FIELD'),false);
    await writeFile(path.join(folder,'training-bay.json'),JSON.stringify({...original,source_sha256:'e'.repeat(64)}));
    const rejected=await loadReplayCatalog(root);
    assert.equal(rejected.status,'ready');
    assert.equal(rejected.clips[0].receipt_status,'rejected');
    assert.equal(rejected.clips[0].receipt,null);
  });
});
