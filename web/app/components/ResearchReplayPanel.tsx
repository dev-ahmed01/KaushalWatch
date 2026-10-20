'use client';
import {useEffect,useRef,useState} from 'react';
import {ArrowRight,ShieldCheck,AlertCircle} from 'lucide-react';
import type {ResearchCatalog,ResearchClip} from '../lib/server/research-replay';
import type {TraceCatalog} from '../lib/server/research-analysis';
import {challengeSummary,sampleAtOrBefore} from '../lib/server/research-challenge';

const clock=(n:number)=>'00:'+Math.floor(Math.max(0,n)).toString().padStart(2,'0');
export default function ResearchReplayPanel(){
 const player=useRef<HTMLVideoElement>(null);
 const [clips,setClips]=useState<ResearchClip[]>([]);
 const [selected,setSelected]=useState('');
 const [state,setState]=useState<'off'|'ready'|'error'>('off');
 const [second,setSecond]=useState(0);
 const [ready,setReady]=useState(false);
 const [decodeError,setDecodeError]=useState(false);
 const [trace,setTrace]=useState<TraceCatalog|null>(null);
 useEffect(()=>{
   let mounted=true;
   fetch('/api/demo/research-replay',{cache:'no-store'})
    .then(async response=>{
       if(response.status===404)return null;
       if(!response.ok)throw new Error('Private cache not admitted');
       return await response.json() as ResearchCatalog;
    })
    .then(data=>{
      if(!mounted||data===null)return;
      if(data.schema!=='KW_PRIVATE_RESEARCH_REPLAY_STATUS_V1'||data.status!=='ready'
         ||!data.research_only||data.model_inference_qualified!==false||data.clips.length!==4)
        throw new Error('Invalid research admission');
      setClips(data.clips);setSelected(data.clips[0].id);setState('ready');
      // The optional local numeric trace is a separately verified source
      // receipt. Unavailable traces must never be replaced with fake scores.
      void fetch('/api/demo/research-replay/analysis',{cache:'no-store'})
       .then(async response=>response.ok?await response.json() as TraceCatalog:null)
       .then(report=>{
          if(mounted&&report?.schema==='KW_PRIVATE_RESEARCH_TRIAGE_TRACE_STATUS_V1'
             &&report.numeric_heuristic_trace===true
             &&report.independent_holdout===false
             &&report.reference_custody_verified===false
             &&report.physical_tamper_proven===false){
             setTrace(report);
          }
       }).catch(()=>{if(mounted)setTrace(null);});
    }).catch(()=>{if(mounted)setState('error');});
   return()=>{mounted=false;};
 },[]);
 const clip=clips.find(c=>c.id===selected);
 const computed=trace?.clips.find(c=>c.id===clip?.id&&c.source_sha256===clip?.source_sha256);
 const numeric=computed?sampleAtOrBefore(computed.samples,second):null;
 const challenge=trace?challengeSummary(trace.clips):null;
 const selectedChallenge=challenge?.clips.find(c=>c.id===clip?.id);
 const allControls=challenge?.normalOrPreEvent;
 const allAnnotated=challenge?.annotated;
 if(state==='off')return null;
 return <section aria-label="Private research replay" className="mt-5 rounded-[20px] border border-[#CBDDED] bg-white p-4 sm:p-5">
   <div className="flex flex-wrap items-start justify-between gap-2">
    <div><p className="text-[11px] font-bold uppercase tracking-[.12em] text-[#6784A5]">Local research replay</p>
     <h3 className="mt-1 text-[16px] font-bold text-[#274968]">Annotated camera-quality study</h3>
     <p className="mt-2 max-w-[620px] text-[11px] leading-5 text-[#677F99]">
       MEVA/UHCTD research footage, not a skill-training centre. Event windows are externally supplied research annotations, not our AI detections or physical-camera certification.
     </p>
    </div>
    <span className="inline-flex items-center gap-1 rounded-full bg-[#EDF5FD] px-2 py-1 text-[11px] font-semibold text-[#315D89]">
      <ShieldCheck size={13}/> Private source SHA verified
    </span>
   </div>
   {state==='error'&&<p role="alert" className="mt-3 text-[12px] text-[#93611D]">
     Approved local research clips unavailable; no private video can be played.
   </p>}
   {clip&&<>
     <div className="mt-4 flex flex-wrap gap-2" aria-label="Choose research annotation">
       {clips.map(item=><button type="button" key={item.id} aria-pressed={selected===item.id}
         onClick={()=>{setSelected(item.id);setSecond(0);setReady(false);setDecodeError(false);}}
         className={'kw-focus rounded-lg border px-3 py-2 text-[11px] font-semibold '+
          (selected===item.id?'border-[#9ABBDD] bg-[#EEF6FF] text-[#225E96]':'border-[#DFE8F2] bg-white text-[#718399]')}>
         {item.name}</button>)}
     </div>
     {challenge&&allControls&&allAnnotated&&<>
       <div className="mt-4 rounded-xl border border-[#DFE8F2] bg-[#F9FBFD] p-3 sm:p-4" aria-label="Private challenge-set audit">
         <div className="flex flex-wrap items-center justify-between gap-2">
           <h4 className="text-[12px] font-bold text-[#355875]">Challenge check · difficult normal scenes</h4>
           <span className="text-[10px] text-[#788BA0]">Previously inspected research · 1 FPS</span>
         </div>
         <div className="mt-3 grid gap-2 sm:grid-cols-3">
           <div className="rounded-lg bg-white px-3 py-2">
             <p className="text-[10px] text-[#72839B]">Normal/pre-event · possible scene change</p>
             <strong className="mt-1 block text-[18px] tabular-nums text-[#344F70]">{allControls.possibleInterference} / {allControls.samples}</strong>
           </div>
           <div className="rounded-lg bg-white px-3 py-2">
             <p className="text-[10px] text-[#72839B]">Normal/pre-event · evidence withheld</p>
             <strong className="mt-1 block text-[18px] tabular-nums text-[#344F70]">{allControls.withheld} / {allControls.samples}</strong>
           </div>
           <div className="rounded-lg bg-white px-3 py-2">
             <p className="text-[10px] text-[#72839B]">Annotated event · evidence withheld</p>
             <strong className="mt-1 block text-[18px] tabular-nums text-[#344F70]">{allAnnotated.withheld} / {allAnnotated.samples}</strong>
           </div>
         </div>
         <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
           <p className="max-w-[580px] text-[10px] leading-4 text-[#71839B]">Selected clips only. These counts are not camera-hour false-alert rates, independent accuracy, or proof of tampering.</p>
           <button type="button" className="kw-focus rounded-lg border border-[#C9DDED] bg-white px-3 py-2 text-[11px] font-semibold text-[#315B81]"
             onClick={()=>{setSelected('quality-normal');setSecond(0);setReady(false);setDecodeError(false);}}>
             Examine normal control <ArrowRight size={13} className="inline"/>
           </button>
         </div>
       </div>
     </>}
     <div className="mt-4 grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(175px,.65fr)]">
       <div className="min-w-0">
        <div className="relative aspect-video overflow-hidden rounded-xl bg-[#142C46]">
         <video ref={player} key={selected} src={clip.source_url} preload="metadata" muted playsInline
          aria-label="Private verified research recording" className="h-full w-full object-contain"
          onLoadedMetadata={e=>{
            const actual=e.currentTarget.duration;
            const valid=Number.isFinite(actual)&&Math.abs(actual-clip.duration_seconds)<=1.5;
            setReady(valid);setDecodeError(!valid);
          }}
          onError={()=>{setReady(false);setDecodeError(true);}}
          onTimeUpdate={e=>setSecond(e.currentTarget.currentTime)}
          onSeeked={e=>setSecond(e.currentTarget.currentTime)}/>
         <span className="pointer-events-none absolute left-3 top-3 rounded bg-[#0F2A43]/90 px-2 py-1 text-[10px] font-bold text-white">Recorded research · not live</span>
        </div>
        {decodeError&&<p role="alert" className="mt-2 inline-flex items-center gap-1 text-[11px] text-[#925F22]">
           <AlertCircle size={13}/> The browser cannot decode or time-align this recording.
         </p>}
        {computed&&<div className="mt-3" aria-label="Quality challenge timeline">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[11px] font-semibold text-[#52728F]">Source-matched quality timeline</span>
            <span className="text-[10px] text-[#7D8EA5]">
              {selectedChallenge?.normalOrPreEvent.withheld ?? 0} normal/pre-event samples withheld
            </span>
          </div>
          <div className="mt-2 flex w-full gap-[2px] overflow-x-auto rounded-md border border-[#DCE6F0] bg-[#EEF3F8] p-1">
            {computed.samples.map(item=><button key={item.frame0} type="button"
              title={item.second.toFixed(1)+'s · '+(item.annotation_in_event?'Annotated event':'Normal/pre-event')+' · '+item.usability}
              aria-label={'Inspect research sample '+Math.floor(item.second)+'s'}
              aria-current={numeric?.frame0===item.frame0?'step':undefined}
              disabled={!ready}
              onClick={()=>{
                if(!player.current)return;
                player.current.currentTime=Math.min(clip.duration_seconds-0.1,item.second);
                setSecond(player.current.currentTime);
              }}
              className={'kw-focus h-7 min-w-[7px] flex-1 rounded-[2px] disabled:cursor-not-allowed disabled:opacity-50 '+
                (item.usability!=='PROVISIONALLY_OBSERVABLE'
                  ?'bg-[#D9A267]':'bg-[#93B9C3]')+
                (numeric?.frame0===item.frame0?' outline outline-2 outline-offset-1 outline-[#315A7D]':'')+
                (item.annotation_in_event?' border-b-[3px] border-b-[#4A648E]':'')}
             />)}
          </div>
          <p className="mt-1 text-[10px] text-[#8190A3]">Amber: evidence review · blue-green: provisional observation · bottom line: supplied event annotation. Use a bar to inspect its actual source time.</p>
        </div>}
        <label className="mt-3 block text-[11px] font-semibold text-[#68809A]" htmlFor="kw-research-seek">
          Recorded position {clock(second)} / {clock(clip.duration_seconds)}
        </label>
        <input type="range" id="kw-research-seek" aria-label="Research playback position"
          min="0" max={clip.duration_seconds} step="0.1" value={Math.min(second,clip.duration_seconds)}
          disabled={!ready} onChange={e=>{
            if(!player.current)return;
            player.current.currentTime=Number(e.target.value);
            setSecond(player.current.currentTime);
          }} className="mt-2 w-full accent-[#28629A]"/>
       </div>
       <aside className="space-y-3">
        <div className="rounded-xl border border-[#E0EAF4] p-3">
          <p className="text-[11px] font-bold text-[#375E80]">Existing annotation</p>
          <p className="mt-2 text-[12px] font-semibold text-[#2D516E]">{clip.annotation_class==='normal'?'Normal control':clip.annotation_class+' interval'}</p>
          <p className="mt-1 text-[11px] text-[#68819D]">
           {clip.event_start_seconds===null?'No incident annotated':
             clock(clip.event_start_seconds)+'–'+clock(clip.event_end_seconds||0)+' · within recording'}
          </p>
          {clip.event_start_seconds!==null&&<button type="button" disabled={!ready}
            onClick={()=>{
             if(!player.current)return;
             player.current.currentTime=Math.min(clip.duration_seconds-0.2,clip.event_start_seconds!+0.25);
             setSecond(player.current.currentTime);
            }} className="kw-focus mt-3 inline-flex items-center gap-1 text-[11px] font-bold text-[#25659A] disabled:opacity-40">
            Jump to annotation <ArrowRight size={13}/>
          </button>}
        </div>
        <div className="rounded-xl border border-[#DCE7F1] bg-[#F9FBFD] p-3" aria-label="Computed research-quality observations">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[11px] font-bold text-[#375E80]">Computed frame sample</p>
            <span className="text-[10px] font-medium text-[#6C8198]">{numeric?clock(numeric.second):'Not prepared'}</span>
          </div>
          {numeric?<>
            <div className="mt-3 flex items-center justify-between gap-2 rounded-lg bg-white px-3 py-2">
              <span className="text-[11px] text-[#576B85]">Evidence usability</span>
              <strong className="text-right text-[11px] text-[#344F70]">{numeric.usability.replaceAll('_',' ')}</strong>
            </div>
            <div className="mt-2 flex items-center justify-between gap-2 rounded-lg bg-white px-3 py-2">
              <span className="text-[11px] text-[#576B85]">Possible interference</span>
              <strong className="text-right text-[11px] text-[#344F70]">{numeric.interference_review.replaceAll('_',' ')}</strong>
            </div>
            <p className="mt-2 text-[10px] leading-4 text-[#7B8A9E]">
              Source-matched numeric heuristic · 1 FPS · first-frame reference not independently approved.
            </p>
          </>:<p className="mt-2 text-[11px] leading-5 text-[#72849A]">
            Numeric trace unavailable. Only the recorded annotation is shown.
          </p>}
        </div>
        <div className="rounded-xl border border-[#E0EAF4] p-3">
          <p className="text-[11px] font-bold text-[#375E80]">Original file integrity</p>
          <code className="mt-2 block break-all font-mono text-[9px] text-[#607B98]">{clip.source_sha256}</code>
          <p className="mt-2 text-[11px] leading-5 text-[#71849A]">
            No inferred attendance, invented object boxes, people identification or training-centre compliance conclusions.
          </p>
        </div>
       </aside>
     </div>
   </>}
 </section>;
}
