import {test} from 'node:test';
import assert from 'node:assert/strict';
import {
 missionPositionFromSearch,returnToMissionFromCase,
 missionHref,caseHrefWithReturn,
} from './missionContinuity.ts';

test('default, exact stage restore and source-centre binding',()=>{
 assert.deepEqual(missionPositionFromSearch(''),{scene:'attendance',step:0});
 assert.deepEqual(missionPositionFromSearch('?scene=equipment&step=3'),{scene:'equipment',step:3});
 assert.equal(returnToMissionFromCase('?from=mission&scene=attendance&step=3','DEMO-KA-104'),
  '/demo/mission?scene=attendance&step=3');
 assert.equal(returnToMissionFromCase('?from=mission&scene=equipment&step=2','DEMO-KA-303'),
  '/demo/mission?scene=equipment&step=2');
 assert.equal(returnToMissionFromCase('?from=mission&scene=equipment&step=2','DEMO-KA-104'),null);
});
test('no untrusted external redirect, bad stage or unknown scenario',()=>{
 for(const search of [
  '?from=mission&scene=https://evil.example&step=3',
  '?from=mission&scene=attendance&step=4',
  '?from=mission&scene=attendance&step=-1',
  '?from=mission&scene=attendance&step=03',
  '?from=mission&scene=attendance&step=3&url=https://evil.example',
  '?from=external&scene=attendance&step=3',
 ]) {
  assert.notEqual(returnToMissionFromCase(search,'DEMO-KA-104'),
     'https://evil.example');
 }
 assert.equal(returnToMissionFromCase('?from=mission&scene=attendance&step=4','DEMO-KA-104'),null);
 assert.equal(returnToMissionFromCase('?from=mission&scene=attendance&step=03','DEMO-KA-104'),null);
 assert.equal(returnToMissionFromCase('?from=external&scene=attendance&step=3','DEMO-KA-104'),null);
 assert.deepEqual(missionPositionFromSearch('?scene=unknown&step=2'),
  {scene:'attendance',step:0});
});
test('case links encode only a centre-contextual scenario, not arbitrary href',()=>{
 const link=caseHrefWithReturn('SIM-KA-104-ATT',{scene:'attendance',step:3});
 assert.equal(link,'/cases/SIM-KA-104-ATT?from=mission&scene=attendance&step=3');
 assert.throws(()=>caseHrefWithReturn('../external',{scene:'attendance',step:0}));
 assert.throws(()=>missionHref({scene:'attendance',step:11}));
});
