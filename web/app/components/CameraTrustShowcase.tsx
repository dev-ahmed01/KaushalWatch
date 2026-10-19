'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { Activity, Camera, Check, Download, Pause, Play, RotateCcw } from 'lucide-react';
import CentreTabs from './CentreTabs';

type Feed={id:string;name:string;area:string;file:string;people:number;start:number;end:number;cue:string};
const FEEDS:Feed[]=[
  {id:'CAM-01',name:'Training bay',area:'Practical lab',file:'training-bay.mp4',people:3,start:8,end:13,cue:'Focus variation'},
  {id:'CAM-02',name:'Workshop floor',area:'Equipment zone',file:'workshop-floor.mp4',people:3,start:9,end:15,cue:'Visibility change'},
  {id:'CAM-03',name:'East corridor',area:'Entry passage',file:'east-corridor.mp4',people:2,start:7,end:13,cue:'Scene alignment'},
];
const PANEL='rounded-2xl border border-[#E3EAF3] bg-white shadow-[0_1px_3px_rgba(16,24,40,0.04)]';
const BTN='kw-focus inline-flex min-h-9 items-center justify-center gap-2 rounded-xl border border-[#D9E2ED] bg-white px-3 text-[12px] font-medium text-[#344054] hover:bg-[#F6F9FC]';
const fmt=(n:number)=>'00:'+Math.floor(Math.max(0,n)).toString().padStart(2,'0');
const source=(f:Feed)=>'/camera-trust/'+f.file;

export default function CameraTrustShowcase({centreId}:{centreId:string}){
  const video=useRef<HTMLVideoElement>(null);
  const [selected,setSelected]=useState(0);
  const [elapsed,setElapsed]=useState(0);
  const [ready,setReady]=useState(false);
  const [missing,setMissing]=useState(false);
  const [retries,setRetries]=useState(0);
  const [playing,setPlaying]=useState(false);
  const [speed,setSpeed]=useState(1);
  const [reviewed,setReviewed]=useState<Record<string,boolean>>({});
  const [all,setAll]=useState(false);
  const feed=FEEDS[selected];
  const active=elapsed>=feed.start&&elapsed<feed.end;
  const detected=elapsed>=feed.start;
  const frame=Math.min(240,Math.floor(elapsed*12));
  const reviewedCount=FEEDS.filter(f=>reviewed[f.id]).length;
  useEffect(()=>{
    try{const prior=localStorage.getItem('kw-camera-demo-reviews');
      if(prior)setReviewed(JSON.parse(prior));}catch{/* Private browser storage disabled */}
    const other=FEEDS.map(f=>{
      const v=document.createElement('video');v.preload='auto';v.muted=true;v.src=source(f);v.load();return v;
    });
    return ()=>other.forEach(v=>{v.pause();v.removeAttribute('src');v.load();});
  },[]);
  useEffect(()=>{if(video.current)video.current.playbackRate=speed;},[speed,selected]);
  function choose(i:number){
    setSelected(i);setElapsed(0);setReady(false);setMissing(false);setPlaying(false);
  }
  function seek(seconds:number){
    if(!video.current)return;
    video.current.currentTime=Math.max(0,Math.min(19.9,seconds));
    setElapsed(video.current.currentTime);
  }
  async function toggle(){
    if(!video.current)return;
    if(video.current.paused){
      try{await video.current.play();}catch{setPlaying(false);}
    }else video.current.pause();
  }
  function review(){
    setReviewed(value=>{
      const next={...value,[feed.id]:!value[feed.id]};
      try{localStorage.setItem('kw-camera-demo-reviews',JSON.stringify(next));}catch{/* in-memory state remains */}
      return next;
    });
  }
  function exportResult(){
    const receipt={
      source:'preloaded synthetic recording',camera:feed.id,
      time_seconds:Number(elapsed.toFixed(2)),frames_played:frame,
      quality_marker:feed.cue,marker_reached:detected,
      reviewed:!!reviewed[feed.id],camera_health_certified:false,
      exported_at:new Date().toISOString(),
    };
    const blob=new Blob([JSON.stringify(receipt,null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');a.href=url;
    a.download='camera-trust-'+feed.id.toLowerCase()+'-review.json';
    a.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  return <div className="space-y-5 pb-6">
    <header className="flex flex-wrap items-end justify-between gap-2">
      <div>
        <Link href={'/centres/'+encodeURIComponent(centreId)}
          className="text-[12px] font-medium text-[#64748B]">← Centre overview</Link>
        <h1 className="mt-1 text-[28px] font-semibold tracking-tight">Camera Trust</h1>
      </div>
      <span className="inline-flex items-center gap-2 text-[11px] font-medium text-[#667085]">
        <span className="h-2 w-2 rounded-full bg-[#14835A]"/>3 sources ready
      </span>
    </header>
    <CentreTabs centreId={centreId}/>
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4" aria-label="Camera Trust statistics">
      {[
        ['Camera sources','03'],['Frames inspected',String(frame).padStart(3,'0')],
        ['Quality markers',detected?'01':'00'],['Reviews done',String(reviewedCount).padStart(2,'0')]
      ].map(([label,value])=><section className={PANEL+' px-4 py-3.5'} key={label}>
        <span className="text-[11px] font-medium text-[#667085]">{label}</span>
        <strong className="mt-1 block text-[26px] font-semibold tabular-nums tracking-tight">{value}</strong>
      </section>)}
    </div>
    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(270px,.7fr)]">
      <section className={PANEL+' min-w-0 overflow-hidden'}>
        <div className="flex items-center justify-between gap-2 px-4 py-3">
          <span className="flex items-center gap-2 text-[13px] font-semibold">
            <Camera size={16} className="text-[#667085]"/>{feed.name}
            <span className="text-[11px] font-normal text-[#98A2B3]">{feed.id}</span>
          </span>
          <span className="rounded-full bg-[#F2F5FA] px-2.5 py-1 text-[10px] font-semibold tracking-wider text-[#475467]">PLAYBACK</span>
        </div>
        <div className="relative aspect-video w-full overflow-hidden bg-[#15232B]">
          <video key={feed.id+"-"+retries} ref={video} src={source(feed)} autoPlay muted playsInline preload="auto"
            aria-label={feed.name+' recorded footage'} className="h-full w-full object-cover"
            onCanPlay={event=>{setReady(true);setMissing(false);event.currentTarget.playbackRate=speed;void event.currentTarget.play().catch(()=>setPlaying(false));}}
            onTimeUpdate={event=>setElapsed(event.currentTarget.currentTime)}
            onSeeked={event=>setElapsed(event.currentTarget.currentTime)}
            onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)}
            onEnded={()=>setPlaying(false)}
            onError={()=>{setMissing(true);setReady(false);}}/>
          {ready&&<span className="pointer-events-none absolute left-3 top-3 rounded-md bg-[#14222bcb] px-2.5 py-1.5 font-mono text-[11px] text-white">
            {fmt(elapsed)} / 00:20
          </span>}
          {active&&<div aria-hidden="true" className="pointer-events-none absolute inset-0">
            <div className={'absolute rounded-lg border-2 '+(selected===1?
              'left-[3%] top-[10%] h-[72%] w-[57%] border-amber-300':
              selected===0?'inset-[10%] border-amber-300':'inset-[12%] border-sky-300')}/>
            <span className="absolute bottom-4 left-4 inline-flex items-center gap-1.5 rounded-lg bg-[#14222be9] px-3 py-2 text-[12px] font-semibold text-white">
              <Activity size={13} className="text-amber-300"/>{feed.cue}
            </span>
          </div>}
          {missing&&<div role="alert" className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-5 text-center text-[12px] text-white">
            <span>Sample recording unavailable. Run the bundled recording generator.</span>
            <button type="button" className="kw-focus rounded-lg border border-white/50 px-3 py-2 font-semibold"
              onClick={()=>{setMissing(false);setReady(false);setElapsed(0);setRetries(n=>n+1);}}>Retry recording</button>
          </div>}
          {!ready&&!missing&&<div className="absolute inset-0 flex items-center justify-center text-[12px] text-[#B6C4CC]">Opening recording…</div>}
        </div>
        <div className="space-y-3 px-4 py-4">
          <div role="slider" aria-label="Recording position" aria-valuemin={0} aria-valuemax={20}
            aria-valuenow={Math.floor(elapsed)} tabIndex={0}
            className="kw-focus relative h-2 w-full cursor-pointer rounded-full bg-[#E9EEF5]"
            onClick={event=>{const b=event.currentTarget.getBoundingClientRect();seek((event.clientX-b.left)/b.width*20);}}
            onKeyDown={event=>{if(event.key==='ArrowRight')seek(elapsed+1);if(event.key==='ArrowLeft')seek(elapsed-1);}}>
            <div className="absolute inset-y-0 left-0 rounded-full bg-[#2563EB]" style={{width:(elapsed/20*100)+'%'}}/>
            <span className="absolute -top-0.5 h-3 w-1 rounded-full bg-amber-500" style={{left:(feed.start/20*100)+'%'}}/>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <button type="button" className={BTN} disabled={!ready} onClick={()=>void toggle()}>
                {playing?<Pause size={14}/>:<Play size={14}/>} {playing?'Pause':'Play'}
              </button>
              <button type="button" className={BTN} disabled={!ready} aria-label="Replay recording"
                onClick={()=>{seek(0);void video.current?.play();}}><RotateCcw size={14}/></button>
              <button type="button" className={BTN} onClick={()=>setSpeed(s=>s===1?1.5:s===1.5?2:1)}
                aria-label="Playback speed">{speed.toFixed(1)}×</button>
            </div>
            <span className="font-mono text-[11px] tabular-nums text-[#667085]">{fmt(elapsed)} / 00:20</span>
          </div>
        </div>
      </section>
      <aside className="min-w-0 space-y-4">
        <section className={PANEL+' p-4'}>
          <h2 className="mb-3 text-[14px] font-semibold">Cameras</h2>
          <div className="space-y-2">
            {FEEDS.map((f,i)=><button key={f.id} type="button"
              onClick={()=>choose(i)} aria-pressed={selected===i}
              className={'kw-focus flex w-full items-center justify-between rounded-xl border p-3 text-left '+
                (selected===i?'border-[#A3C0F7] bg-[#EFF6FF]':'border-[#E6EAF0] bg-[#FAFBFD] hover:bg-[#F4F7FA]')}>
              <span className="min-w-0">
                <strong className="block truncate text-[12px] text-[#344054]">{f.name}</strong>
                <span className="block truncate text-[11px] text-[#667085]">{f.id} · {f.area}</span>
              </span>
              {reviewed[f.id]?<Check size={15} className="shrink-0 text-[#067647]"/>:
                <span className="h-2 w-2 shrink-0 rounded-full bg-[#CBD5E1]"/>}
            </button>)}
          </div>
        </section>
        <section className={PANEL+' p-4'}>
          <div className="flex items-center justify-between">
            <h2 className="text-[14px] font-semibold">Quality signals</h2>
            <span className={'rounded-full px-2.5 py-1 text-[10px] font-semibold '+(active?
              'bg-[#FFF3E6] text-[#A45712]':'bg-[#F3F6FA] text-[#667085]')}>
              {active?'REVIEW':'MONITORING'}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-[#F8FAFC] p-3">
              <span className="text-[10px] text-[#667085]">Scene people</span>
              <strong className="mt-1 block text-[23px] tabular-nums">{feed.people}</strong>
            </div>
            <div className="rounded-xl bg-[#F8FAFC] p-3">
              <span className="text-[10px] text-[#667085]">Recording FPS</span>
              <strong className="mt-1 block text-[23px] tabular-nums">12</strong>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between rounded-xl border border-[#E6EAF0] p-3">
            <div>
              <strong className="text-[12px]">{feed.cue}</strong>
              <p className="text-[11px] text-[#667085]">{fmt(feed.start)} – {fmt(feed.end)}</p>
            </div>
            <button className="kw-focus text-[12px] font-semibold text-[#2563EB]" type="button"
              onClick={()=>{seek(feed.start);void video.current?.play();}}>Inspect</button>
          </div>
          <button type="button" className={'kw-focus mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-[12px] font-semibold '+(reviewed[feed.id]?
            'border border-[#BBE6CC] bg-[#F3FBF5] text-[#067647]':'bg-[#2563EB] text-white hover:bg-[#1D4ED8]')}
            onClick={review}>
            <Check size={14}/>{reviewed[feed.id]?'Reviewed — undo':'Mark reviewed'}
          </button>
        </section>
      </aside>
    </div>
    <section className={PANEL+' p-4'}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-[14px] font-semibold">Review timeline</h2>
          <span className="text-[11px] text-[#667085]">Recorded sample · synchronized signal markers</span>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className={BTN} onClick={exportResult}><Download size={14}/> Export</button>
          <button type="button" className={BTN} onClick={()=>setAll(v=>!v)}>{all?'Close':'All signals'}</button>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-3 rounded-xl border border-[#E6EAF0] px-3 py-3">
        <span className={'h-2 w-2 shrink-0 rounded-full '+(active?'bg-amber-500':'bg-[#CBD5E1]')}/>
        <span className="min-w-0 flex-1 truncate text-[12px] font-medium">{feed.cue}</span>
        <span className="font-mono text-[11px] text-[#667085]">{fmt(feed.start)}</span>
        <span className="text-[11px] text-[#667085]">{reviewed[feed.id]?'Reviewed':detected?'Ready':'Upcoming'}</span>
      </div>
      {all&&<div className="mt-3 grid gap-2 sm:grid-cols-3">
        {FEEDS.map((f,i)=><button key={f.id} type="button" onClick={()=>choose(i)}
          className="kw-focus flex items-center justify-between rounded-xl bg-[#F8FAFC] px-3 py-3 text-[11px]">
          <span>{f.id} · {f.cue}</span><span className="text-[#667085]">{reviewed[f.id]?'Done':'Open'}</span>
        </button>)}
      </div>}
    </section>
  </div>;
}
