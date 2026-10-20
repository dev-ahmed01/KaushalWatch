import {test} from 'node:test';
import assert from 'node:assert/strict';
import {challengeSummary,sampleAtOrBefore} from './research-challenge.ts';

const sample=(second,annotation_in_event,usability='PROVISIONALLY_OBSERVABLE',
  interference_review='NOT_ESTABLISHED')=>({
  second,frame0:second*3,annotation_in_event,
  usability,interference_review,reason:'NO_SEVERE_QUALITY_LOSS_OBSERVED',
});
const usable='PROVISIONALLY_OBSERVABLE';
const withheld='NOT_USABLE_FOR_VISUAL_VERIFICATION';
const change='POSSIBLE_SCENE_INTERFERENCE_REVIEW';

test('past-only sample cursor never leaks a future warning before its timestamp',()=>{
 const data=[sample(0,false,usable),sample(1,false,withheld),
             sample(2,true,usable),sample(3,true,withheld)];
 assert.equal(sampleAtOrBefore(data,0.99)?.second,0);
 assert.equal(sampleAtOrBefore(data,1.0)?.second,1);
 assert.equal(sampleAtOrBefore(data,1.99)?.second,1);
 assert.equal(sampleAtOrBefore(data,2.0)?.second,2);
 assert.equal(sampleAtOrBefore(data,2.999)?.second,2);
 assert.equal(sampleAtOrBefore(data,3.4)?.second,3);
 assert.equal(sampleAtOrBefore(data,-1),null);
 assert.equal(sampleAtOrBefore(data,Number.NaN),null);
 assert.equal(sampleAtOrBefore([],8),null);
});

test('normal and pre-event windows count false review burden without fabricated field metrics',()=>{
 const source=[
  {id:'quality-normal',source_sha256:'a'.repeat(64),samples:[
   sample(0,false,withheld,change),
   sample(1,false,usable),
   sample(2,false,withheld),
  ],counts:{evidence_unusable:2,possible_interference:1,annotation_event_samples:0}},
  {id:'quality-covered',source_sha256:'b'.repeat(64),samples:[
   sample(0,false,usable),
   sample(1,false,withheld,change),
   sample(2,true,withheld,change),
   sample(3,true,usable),
  ],counts:{evidence_unusable:2,possible_interference:2,annotation_event_samples:2}},
 ];
 const report=challengeSummary(source);
 assert.equal(report.schema,'KW_PRIVATE_CHALLENGE_DESCRIPTIVE_V1');
 assert.equal(report.normalOrPreEvent.samples,5);
 assert.equal(report.normalOrPreEvent.unusable,3);
 assert.equal(report.normalOrPreEvent.withheld,3);
 assert.equal(report.normalOrPreEvent.possibleInterference,2);
 assert.equal(report.annotated.samples,2);
 assert.equal(report.annotated.withheld,1);
 assert.equal(report.annotated.possibleInterference,1);
 assert.equal(report.clips.find(x=>x.id==='quality-normal').annotated.samples,0);
 assert.equal(report.is_independent_holdout,false);
 assert.equal(report.field_false_alarm_rate_available,false);
 assert.equal(report.physical_tampering_proven,false);
 assert.equal(report.auto_action_allowed,false);
 assert.equal(JSON.stringify(report).includes('false_alerts_per_hour'),false);
});

test('missing events and every sample withheld cannot silently imply high accuracy',()=>{
 const result=challengeSummary([{
  id:'quality-normal',source_sha256:'c'.repeat(64),
  samples:[sample(0,false,withheld),sample(1,false,withheld)],
  counts:{evidence_unusable:2,possible_interference:0,annotation_event_samples:0},
 }]);
 assert.deepEqual(result.annotated,{samples:0,unusable:0,possibleInterference:0,withheld:0});
 assert.equal(result.normalOrPreEvent.withheld,2);
 assert.equal(result.field_false_alarm_rate_available,false);
});
