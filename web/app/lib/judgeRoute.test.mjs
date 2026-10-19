import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chapters,chapterClock,validJudgePath} from './judgeRoute.ts';
import {DEMO_SCENES} from './demoMission.ts';

test('both presenter tracks cover exactly 60s and 200s without holes',()=>{
 assert.equal(validJudgePath('quick'),true);
 assert.equal(validJudgePath('full'),true);
 assert.equal(chapters('quick').at(-1).to,60);
 assert.equal(chapters('full').at(-1).to,200);
 assert.equal(chapterClock(0),'00:00');
 assert.equal(chapterClock(200),'03:20');
});

test('every speaker cue has a grounded existing scenario with no fifth module',()=>{
 const known=new Set(DEMO_SCENES.map(x=>x.id));
 assert.deepEqual([...known].sort(),['attendance','camera','equipment','normal']);
 for(const mode of ['quick','full']){
  const list=chapters(mode);
  for(const chapter of list){
   assert.ok(known.has(chapter.scene));
   assert.ok(chapter.cue.length>=20);
   assert.ok(chapter.label.length>=5);
   assert.ok(chapter.target.length>=5);
  }
 }
});
