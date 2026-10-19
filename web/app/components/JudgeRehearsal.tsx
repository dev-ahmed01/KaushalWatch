'use client';
import {useState} from 'react';
import {ArrowRight,RotateCcw} from 'lucide-react';
import type {SceneId} from '../lib/demoMission';
import {chapters,chapterClock,type DemoMode} from '../lib/judgeRoute';

/** Manual rehearsal cues, never a pretend running timer or accuracy measure. */
export default function JudgeRehearsal({sceneId,onScene}:
 {sceneId:SceneId;onScene:(id:SceneId)=>void}){
 const [mode,setMode]=useState<DemoMode>('full');
 const [chapter,setChapter]=useState(0);
 const itinerary=chapters(mode);
 const active=itinerary[Math.min(chapter,itinerary.length-1)];
 const directScene=sceneId===active.scene;

 function switchMode(next:DemoMode){
  setMode(next);setChapter(0);onScene(chapters(next)[0].scene);
 }
 function go(next:number){
  const to=Math.max(0,Math.min(itinerary.length-1,next));
  setChapter(to);onScene(itinerary[to].scene);
 }
 return <section aria-label="Judge rehearsal" className="rounded-[18px] border border-[#CFDEEF] bg-white px-4 py-4 sm:px-5">
  <div className="flex flex-wrap items-center justify-between gap-3">
   <div>
    <h2 className="text-[14px] font-bold text-[#254361]">Judge route</h2>
    <p className="mt-0.5 text-[10px] text-[#7F91A7]">Planned speaking windows · manual navigation, not a timer</p>
   </div>
   <div role="group" aria-label="Presentation length" className="inline-flex gap-1 rounded-lg border border-[#DCE6F1] bg-[#F6F9FC] p-1">
    {(['quick','full'] as const).map(key=><button key={key} type="button"
     aria-pressed={mode===key} onClick={()=>switchMode(key)}
     className={'kw-focus rounded-md px-3 py-1.5 text-[11px] font-semibold '+
      (mode===key?'bg-[#24588A] text-white':'text-[#607991] hover:bg-white')}>
     {key==='quick'?'60 sec':'3m 20s'}
    </button>)}
   </div>
  </div>
  <div role="list" className="mt-3 grid gap-1.5" style={{gridTemplateColumns:'repeat('+itinerary.length+',minmax(0,1fr))'}}>
   {itinerary.map((item,i)=><button key={item.id} role="listitem" type="button"
    aria-current={chapter===i?'step':undefined}
    aria-label={'Chapter '+(i+1)+' '+item.label+' at '+chapterClock(item.from)}
    onClick={()=>go(i)}
    className={'kw-focus min-h-10 min-w-0 rounded-lg border px-1 py-2 text-center text-[9px] font-semibold sm:text-[11px] '+
      (chapter===i?'border-[#8EB9E4] bg-[#EAF3FE] text-[#1B558D]':
        'border-[#E4ECF4] bg-[#FAFCFE] text-[#7790A7] hover:border-[#C2D8EA]')}>
    <span className="block truncate">{item.label}</span>
    <span className="block font-mono text-[9px] opacity-75">{chapterClock(item.from)}</span>
   </button>)}
  </div>
  <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
   <p role="status" className="max-w-[620px] text-[11px] leading-5 text-[#5D728B]">
    <strong className="text-[#315879]">{chapterClock(active.from)}–{chapterClock(active.to)}</strong> · {directScene?active.cue:'You manually changed scenarios. Use a chapter to resume the presenter route.'}
   </p>
   <div className="flex shrink-0 gap-2">
    <button type="button" onClick={()=>go(0)} aria-label="Restart judge route"
     className="kw-focus rounded-lg border border-[#D6E2EF] p-2 text-[#42688C]"><RotateCcw size={14}/></button>
    <button type="button" onClick={()=>go(chapter+1)} disabled={chapter===itinerary.length-1}
     className="kw-focus inline-flex items-center gap-1.5 rounded-lg bg-[#285C8D] px-3 py-2 text-[11px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40">
     Next cue <ArrowRight size={13}/>
    </button>
   </div>
  </div>
 </section>;
}
