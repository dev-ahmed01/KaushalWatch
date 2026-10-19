'use client';

import {useEffect,useRef,useState} from 'react';
import {AlertCircle,ArrowRight,CheckCircle2,Pause,Play,RotateCcw,ShieldCheck,Video} from 'lucide-react';
import type {SceneId} from '../lib/demoMission';
import type {ReplayCatalog,ReplayClip,ReplaySample} from '../lib/server/replay-catalog';

const CLIP_BY_SCENE:Record<SceneId,string>={
  attendance:'training-bay',camera:'training-bay',
  equipment:'workshop-floor',normal:'east-corridor',
};
const time=(t:number)=>'00:'+String(Math.min(59,Math.floor(Math.max(t,0)))).padStart(2,'0');

export default function SourceLockedReplay({sceneId}:{sceneId:SceneId}){
  const player=useRef<HTMLVideoElement>(null);
  const [catalog,setCatalog]=useState<ReplayCatalog|null>(null);
  const [selected,setSelected]=useState(CLIP_BY_SCENE[sceneId]);
  const [loading,setLoading]=useState(true);
  const [failed,setFailed]=useState(false);
  const [mediaReady,setMediaReady]=useState(false);
  const [playing,setPlaying]=useState(false);
  const [elapsed,setElapsed]=useState(0);
  const [refresh,setRefresh]=useState(0);

  useEffect(()=>{
    setSelected(CLIP_BY_SCENE[sceneId]);setMediaReady(false);setPlaying(false);setElapsed(0);setFailed(false);
  },[sceneId]);

  useEffect(()=>{
    let active=true;
    setLoading(true);setFailed(false);setCatalog(null);
    fetch('/api/demo/replay',{cache:'no-store'})
      .then(async response=>{
        const payload=await response.json().catch(()=>null) as ReplayCatalog|null;
        if(!response.ok||payload?.schema!=='KW_SOURCE_LOCKED_REPLAY_V1'
          ||payload.status!=='ready')throw new Error('Source verification failed');
        return payload;
      })
      .then(payload=>{if(active)setCatalog(payload);})
      .catch(()=>{if(active)setFailed(true);})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false};
  },[refresh]);

  const clip=catalog?.clips.find(item=>item.id===selected);
  const verified=clip?.status==='verified'&&clip.source_url&&clip.sha256;
  const model=verified&&clip.receipt_status==='matched_unqualified'?clip.receipt:null;
  const sample:ReplaySample|undefined=model?.samples.find(p=>Math.abs(p.second-elapsed)<=0.06);
  const withinMarker=Boolean(clip&&elapsed>=clip.start&&elapsed<clip.end);
  const blocked=failed||!loading&&!verified;

  function selectClip(id:string){
    setSelected(id);setElapsed(0);setMediaReady(false);setPlaying(false);
  }
  function seek(second:number){
    if(!player.current||!mediaReady||!clip)return;
    player.current.currentTime=Math.min(clip.duration-0.1,Math.max(0,second));
    setElapsed(player.current.currentTime);
  }
  async function toggle(){
    if(!player.current||!mediaReady)return;
    if(!player.current.paused){player.current.pause();return;}
    try{await player.current.play();}catch{setPlaying(false);}
  }
  function verifyMetadata(){
    const element=player.current;
    if(!element||!clip)return;
    // Refuse unexpected codecs/files with a very different duration or
    // aspect ratio; manifest hash is checked on the server separately.
    const okay=Number.isFinite(element.duration)
      && Math.abs(element.duration-clip.duration)<=0.6
      && element.videoWidth===576&&element.videoHeight===324;
    setMediaReady(okay);setFailed(!okay);
  }

  return <section aria-label="Source-locked replay" className="mt-6 min-w-0 rounded-[20px] border border-[#DCE7F3] bg-[#F7FAFD] p-4 sm:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-[11px] font-bold uppercase tracking-[.13em] text-[#6D88A7]">Recorded source check</p>
        <h3 className="mt-1 text-[16px] font-bold text-[#29445F]">Source-locked replay</h3>
        <p className="mt-1 max-w-xl text-[11px] leading-5 text-[#617993]">
          A procedural camera-quality recording, not CCTV from the selected centre.
          The illustrated attendance and equipment counts above are <strong>not derived from this video</strong>.
        </p>
      </div>
      <span className={'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-semibold '+
        (verified&&!blocked?'bg-[#E5F4EB] text-[#276A48]':'bg-[#FFF2E2] text-[#905B1C]')}>
        {verified&&!blocked?<CheckCircle2 size={13}/>:<AlertCircle size={13}/>}
        {loading?'Checking source…':verified&&!blocked?'Manifest hash matched':'Source unavailable'}
      </span>
    </div>
    {blocked?<div role="alert" className="mt-4 rounded-xl border border-[#ECD6B8] bg-white p-5 text-[12px] text-[#92631E]">
      The original recording or manifest could not be verified. No replay, detection or camera conclusion is shown.
      <button type="button" onClick={()=>setRefresh(n=>n+1)} className="kw-focus ml-2 font-bold underline">Retry verification</button>
    </div>:null}
    {!blocked&&!loading&&catalog&&clip&&verified&&<>
      <div className="mt-4 flex flex-wrap gap-2" aria-label="Choose synthetic camera recording">
        {catalog.clips.map(item=><button type="button" key={item.id} onClick={()=>selectClip(item.id)}
          aria-pressed={selected===item.id}
          className={'kw-focus rounded-lg border px-3 py-1.5 text-[11px] font-semibold '+
            (item.id===selected?'border-[#AAC7E8] bg-[#E5F0FC] text-[#2D5F98]':'border-[#DFE8F3] bg-white text-[#627994]')}>
          {item.name}</button>)}
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(210px,.65fr)]">
        <div className="min-w-0">
          <div className="relative aspect-video overflow-hidden rounded-xl bg-[#13233B]">
            <video key={selected+'-'+sceneId} ref={player}
              className="h-full w-full object-contain"
              src={clip.source_url||undefined} preload="metadata" muted playsInline
              aria-label="Source-verified procedural recorded footage"
              onLoadedMetadata={verifyMetadata} onError={()=>{setFailed(true);setMediaReady(false);}}
              onTimeUpdate={event=>setElapsed(event.currentTarget.currentTime)}
              onSeeked={event=>setElapsed(event.currentTarget.currentTime)}
              onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onEnded={()=>setPlaying(false)}/>
            <div className="pointer-events-none absolute left-3 top-3 rounded-md bg-[#0E2339]/85 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white">
              Recorded · synthetic
            </div>
            {model&&sample?.boxes.map((box,i)=><div key={sample.frame+'-'+i}
              className="pointer-events-none absolute border-2 border-[#64E3AE] text-white"
              style={{left:(box.x*100)+'%',top:(box.y*100)+'%',
                width:(box.width*100)+'%',height:(box.height*100)+'%'}}>
              <span className="absolute -top-5 left-0 whitespace-nowrap rounded bg-[#155B4C] px-1 text-[9px]">
                {box.label} {(box.score*100).toFixed(0)}%
              </span>
            </div>)}
            {!mediaReady&&<div role="status" className="pointer-events-none absolute inset-0 flex items-center justify-center bg-[#13233B]/40 text-[12px] text-white">
              Preparing verified recording…
            </div>}
          </div>
          <div className="mt-3">
            <label className="block text-[11px] font-semibold text-[#526A86]" htmlFor="kw-replay-seek">
              Playback position · {time(elapsed)} / {time(clip.duration)}
            </label>
            <input id="kw-replay-seek" aria-label="Recorded video position" type="range"
              min="0" max={clip.duration} step="0.1" value={elapsed}
              disabled={!mediaReady} onChange={e=>seek(Number(e.target.value))}
              className="mt-2 w-full accent-[#2862A0]"/>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button type="button" disabled={!mediaReady} onClick={()=>void toggle()}
                className="kw-focus inline-flex items-center gap-2 rounded-lg bg-[#214D80] px-3 py-2 text-[11px] font-bold text-white disabled:opacity-40">
                {playing?<Pause size={13}/>:<Play size={13}/>} {playing?'Pause':'Play recording'}
              </button>
              <button type="button" disabled={!mediaReady} aria-label="Restart recorded replay" onClick={()=>seek(0)}
                className="kw-focus rounded-lg border border-[#D8E2EE] bg-white p-2 text-[#426587] disabled:opacity-40"><RotateCcw size={14}/></button>
              <span className="ml-auto font-mono text-[10px] text-[#7089A1]">12 FPS · 20 sec</span>
            </div>
          </div>
        </div>
        <aside className="min-w-0 space-y-3">
          <div className="rounded-xl border border-[#E1EAF3] bg-white p-3">
            <div className="flex items-center gap-2 text-[11px] font-semibold text-[#31536F]"><ShieldCheck size={14}/> Source provenance</div>
            <p className="mt-2 text-[11px] leading-5 text-[#627991]">Procedurally generated video; SHA-256 checked against the committed manifest.</p>
            <code className="mt-2 block break-all font-mono text-[9px] text-[#587B9D]">{clip.sha256}</code>
          </div>
          <div className="rounded-xl border border-[#E1EAF3] bg-white p-3">
            <div className="flex items-center gap-2 text-[11px] font-semibold text-[#31536F]"><Video size={14}/> Camera-quality cue</div>
            <p className="mt-2 text-[12px] font-semibold text-[#2F4D69]">{clip.cue}</p>
            <p className="mt-1 text-[11px] text-[#6A8198]">{time(clip.start)}–{time(clip.end)} · authored generator event</p>
            <p className="mt-1 text-[11px] text-[#768AA0]">{withinMarker?'Inside the quality-change interval':'Outside the marked interval'}</p>
            <button type="button" disabled={!mediaReady} onClick={()=>seek(clip.start+0.5)}
              className="kw-focus mt-3 inline-flex items-center gap-1.5 text-[11px] font-bold text-[#275F9B] disabled:opacity-40">
              Inspect quality event <ArrowRight size={13}/>
            </button>
          </div>
          <div className="rounded-xl border border-[#E1EAF3] bg-white p-3">
            <p className="text-[11px] font-semibold text-[#31536F]">Saved model observations</p>
            <p className="mt-2 text-[11px] leading-5 text-[#657C95]">
              {clip.receipt_status==='matched_unqualified'
                ? 'Matching operator-supplied inference receipt; independently unqualified. Boxes are shown only at exact source frame times.'
                : clip.receipt_status==='rejected'
                  ? 'A supplied receipt failed validation. No detections can be shown.'
                  : 'No matching model receipt. No detected headcount, confidence or bounding boxes are invented.'}
            </p>
            {model&&<p className="mt-2 break-all text-[9px] text-[#7187A0]">
              Model {model.model_sha256.slice(0,12)}… · Profile {model.profile_sha256.slice(0,12)}…
            </p>}
          </div>
        </aside>
      </div>
    </>}
  </section>;
}
