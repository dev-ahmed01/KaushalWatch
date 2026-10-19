import type {SceneId} from './demoMission';

export type DemoMode='quick'|'full';
export type JudgeChapter={
 id:string;scene:SceneId;label:string;
 from:number;to:number;cue:string; target:string;
};
/** Cue windows are presentation PLAN, not measured runtime or model inference. */
export const JUDGE_PATHS:Record<DemoMode,readonly JudgeChapter[]>={
 quick:[
  {id:'q1',scene:'attendance',label:'Attendance',from:0,to:15,cue:'Show the reported/observed difference and mark it illustrative.',target:'Mission evidence'},
  {id:'q2',scene:'camera',label:'Camera',from:15,to:29,cue:'Withheld is not zero; point to the source-quality abstention.',target:'Camera evidence'},
  {id:'q3',scene:'equipment',label:'Equipment',from:29,to:43,cue:'Compare item classes; do not call missing proposals sanctioned shortages.',target:'Equipment matrix'},
  {id:'q4',scene:'normal',label:'Normal + sync',from:43,to:60,cue:'Show a clean negative control and the measured local offline test.',target:'No invented case'},
 ],
 full:[
  {id:'f1',scene:'attendance',label:'Claim → evidence',from:0,to:40,cue:'Demonstrate discrepancy persistence, explain anonymous counts and show the source boundary.',target:'Review candidate'},
  {id:'f2',scene:'camera',label:'Trust → abstain',from:40,to:75,cue:'Change to obstructed-camera scenario. Unknown physical count remains unknown.',target:'Withheld conclusion'},
  {id:'f3',scene:'equipment',label:'Item verification',from:75,to:115,cue:'Show job-role item matrix, camera ROI and nonqualified saved model proposals.',target:'Class-level evidence'},
  {id:'f4',scene:'attendance',label:'Officer → audit',from:115,to:160,cue:'Open saved case, review evidence. Show role-gated atomic decision and audit trail.',target:'Saved case and PDF'},
  {id:'f5',scene:'normal',label:'Negative control',from:160,to:178,cue:'Show aligned reported/observed counts; do not invent a case.',target:'Quiet outcome'},
  {id:'f6',scene:'normal',label:'Offline → limits',from:178,to:200,cue:'Show real loopback byte receipt, qualification gaps and close without field-certification claims.',target:'Measured transport'},
 ],
} as const;
export function chapters(mode:DemoMode):readonly JudgeChapter[]{return JUDGE_PATHS[mode];}
export function validJudgePath(mode:DemoMode):boolean{
 const list=chapters(mode),end=mode==='quick'?60:200;
 return list.length>=4&&list[0].from===0&&list.at(-1)?.to===end
   &&list.every((x,i)=>x.to>x.from&&(i===0||list[i-1].to===x.from));
}
export function chapterClock(second:number):string{
 const m=Math.floor(second/60),s=second%60;
 return String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
}
