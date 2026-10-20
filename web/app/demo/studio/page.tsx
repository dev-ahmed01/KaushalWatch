'use client';

import Link from 'next/link';
import {
  AlertTriangle, ArrowRight, BarChart3, Check, CheckCircle2, ChevronRight,
  Clock3, FileCheck2, MessageCircle, Pause, Play, RotateCcw, Send,
  ShieldAlert, ShieldCheck, Sparkles, Users, Video, Wrench,
} from 'lucide-react';
import {useEffect, useMemo, useRef, useState, type FormEvent} from 'react';
import {SECURE_PROXY} from '../../lib/api';
import {
  STUDIO_SCENES, STUDIO_VIEWS, scriptedAnswer, studioStage,
  type StudioSceneId, type StudioView,
} from '../../lib/demoStudio';

type ReplayCatalog = {
  schema: string; status: string;
  clips: Array<{id:string;status:string;source_url:string|null;sha256:string|null}>;
};
type ChatEntry = {scene:StudioSceneId;author:'Officer'|'Centre Head';text:string;at:number};
type AssistantEntry = {question:string;answer:string};

const surface='rounded-[20px] border border-[#DFE9F5] bg-white shadow-[0_3px_20px_rgba(31,65,109,.045)]';
const accent='text-[#1C5BBC]';
const clock=(seconds:number)=>'00:'+Math.floor(Math.max(0,seconds)).toString().padStart(2,'0');

export default function RecordedDemoStudio(){
  const [sceneId,setSceneId]=useState<StudioSceneId>('attendance');
  const [view,setView]=useState<StudioView>('Overview');
  const [seconds,setSeconds]=useState(0);
  const [playing,setPlaying]=useState(false);
  const [catalog,setCatalog]=useState<ReplayCatalog|null>(null);
  const [sourceError,setSourceError]=useState('');
  const [reviewed,setReviewed]=useState<Record<string,boolean>>({});
  const [chat,setChat]=useState<ChatEntry[]>([]);
  const [chatDraft,setChatDraft]=useState('');
  const [question,setQuestion]=useState('');
  const [answers,setAnswers]=useState<Record<string,AssistantEntry[]>>({});
  const player=useRef<HTMLVideoElement|null>(null);
  const scene=STUDIO_SCENES.find(item=>item.id===sceneId)||STUDIO_SCENES[0];
  const stage=studioStage(scene,seconds);
  const sceneReviewed=Boolean(reviewed[sceneId]);
  const messages=chat.filter(message=>message.scene===sceneId);
  const aiConversation=answers[sceneId]||[];
  const source=useMemo(()=>catalog?.clips.find(item=>item.id===scene.clipId),[catalog,scene.clipId]);
  const admitted=catalog?.schema==='KW_SOURCE_LOCKED_REPLAY_V1'&&catalog.status==='ready'
    &&source?.status==='verified'&&source.source_url==='/camera-trust/'+scene.clipId+'.mp4'
    &&Boolean(source.sha256?.match(/^[a-f0-9]{64}$/));

  useEffect(()=>{
    if(SECURE_PROXY)return;
    let active=true;
    fetch('/api/demo/replay',{cache:'no-store'})
      .then(async response=>{
        if(!response.ok)throw new Error('Source verification unavailable');
        return await response.json() as ReplayCatalog;
      })
      .then(data=>{if(active){setCatalog(data);setSourceError('');}})
      .catch(()=>{if(active){setCatalog(null);setSourceError('The recorded sample could not be verified. Playback is blocked.');}});
    return()=>{active=false;};
  },[]);

  function selectScene(id:StudioSceneId){
    player.current?.pause();
    setSceneId(id);setSeconds(0);setPlaying(false);setView('Overview');setQuestion('');
  }
  async function play(){
    if(!admitted||!player.current)return;
    try{await player.current.play();setSourceError('');}
    catch{setSourceError('Playback could not start on this device. Try the native video controls.');}
  }
  function jump(time:number){
    if(!admitted||!player.current)return;
    player.current.currentTime=time;
    setSeconds(time);
  }
  function reset(){
    player.current?.pause();
    if(player.current)player.current.currentTime=0;
    setSeconds(0);setPlaying(false);
    setReviewed(previous=>({...previous,[sceneId]:false}));
    setAnswers(previous=>({...previous,[sceneId]:[]}));
    setChat(previous=>previous.filter(message=>message.scene!==sceneId));
  }
  function ask(text:string){
    const clean=text.trim().slice(0,400);
    if(!clean)return;
    const answer=scriptedAnswer(scene,seconds,clean,sceneReviewed);
    setAnswers(previous=>({...previous,[sceneId]:[...(previous[sceneId]||[]),{question:clean,answer}].slice(-4)}));
    setQuestion('');
  }
  function sendChat(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    const text=chatDraft.trim().slice(0,500);
    if(!text||!stage.prepared)return;
    setChat(previous=>[...previous,
      {scene:sceneId,author:'Officer',text,at:seconds},
      {scene:sceneId,author:'Centre Head',text:'Acknowledged in the simulated conversation. We will provide the requested records for officer review.',at:seconds}]);
    setChatDraft('');
  }
  if(SECURE_PROXY)return <div role="alert" className={surface+' p-8'}>
    <h1 className="text-2xl font-bold">Recorded demo unavailable</h1>
    <p className="mt-3 text-sm text-[#61758d]">The synthetic showcase is available only in controlled local demo mode, not protected officer deployments.</p>
    <Link href="/" className="mt-3 inline-block font-semibold text-[#205db7]">Return to Overview</Link>
  </div>;

  const iconFor=(id:StudioSceneId)=>id==='attendance'?<Users size={18}/>:id==='infrastructure'?<Wrench size={18}/>:<ShieldAlert size={18}/>;
  return <div className="space-y-4 pb-7" aria-label="Recorded synthetic analysis studio">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <Link href="/demo/mission" className="kw-focus inline-flex items-center gap-1.5 text-[12px] font-semibold text-[#54718f]">
        <ChevronRight className="rotate-180" size={15}/> Guided mission
      </Link>
      <span className="inline-flex items-center gap-2 rounded-full border border-[#BDD6F3] bg-[#EDF5FF] px-3 py-1.5 text-[11px] font-semibold text-[#245BA3]">
        <span className="h-2 w-2 rounded-full bg-[#2563EB]"/> Simulated demo · scripted analysis
      </span>
    </div>

    <section className="relative overflow-hidden rounded-[22px] bg-[#102B50] px-5 py-6 text-white sm:px-7">
      <div aria-hidden="true" className="absolute -right-12 -top-24 h-72 w-72 rounded-full border border-[#90B9EE]/15 bg-[#427FC9]/15"/>
      <div className="relative flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[.22em] text-[#A5C8F0]">KaushalWatch OS / demonstration control room</p>
          <h1 className="mt-2 text-[27px] font-bold tracking-[-.045em] sm:text-[35px]">From recording to officer action.</h1>
          <p className="mt-2 max-w-[680px] text-[12px] leading-6 text-[#D1E0F1]">A source-verified procedural recording drives a time-synchronised synthetic workflow. No real-time model inference or external messaging is claimed.</p>
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-white/20 bg-white/10 px-4 py-2.5 text-[11px]">
          <ShieldCheck size={18} className="text-[#A9D5FF]"/>
          <div><strong className="block">Controlled replay</strong><span className="text-[#D1E0F1]">Reproducible, no internet AI dependency</span></div>
        </div>
      </div>
    </section>

    <div className="grid gap-2 sm:grid-cols-3" aria-label="Select recorded scenario">
      {STUDIO_SCENES.map((item,index)=><button type="button" key={item.id} aria-pressed={sceneId===item.id}
        onClick={()=>selectScene(item.id)}
        className={'kw-focus flex min-w-0 items-center gap-3 rounded-2xl border px-4 py-3.5 text-left transition-colors '+
          (sceneId===item.id?'border-[#8CB5F1] bg-[#ECF5FF] shadow-[0_3px_12px_rgba(37,99,235,.09)]':'border-[#DEE7F2] bg-white hover:bg-[#F6F9FE]')}>
        <span className={'flex h-11 w-11 shrink-0 items-center justify-center rounded-xl '+(sceneId===item.id?'bg-[#D6E9FF] text-[#155FDB]':'bg-[#F1F5FA] text-[#6B809B]')}>{iconFor(item.id)}</span>
        <span className="min-w-0 flex-1"><span className="block text-[10px] text-[#7F91A9]">0{index+1} / recorded scenario</span>
          <strong className="block truncate text-[13px] text-[#233B5E]">{item.title}</strong><small className="mt-0.5 block truncate text-[10px] text-[#7C8DA3]">{item.centre}</small></span>
        {sceneId===item.id&&<Check size={16} className="text-[#2463C2]"/>}
      </button>)}
    </div>

    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.52fr)_minmax(320px,.83fr)]">
      <div className="min-w-0 space-y-4">
        <section className={surface+' overflow-hidden'} aria-label="Recorded scene playback">
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3.5 sm:px-5">
            <div className="flex items-center gap-2"><Video size={17} className={accent}/><h2 className="text-[15px] font-bold text-[#233B5B]">Recorded source</h2><span className="text-[10px] text-[#778EA9]">{scene.subtitle}</span></div>
            <span className={'text-[11px] font-semibold '+(admitted?'text-[#09845D]':'text-[#AA7130]')}>
              {admitted?'SHA-256 source verified':sourceError?'Source blocked':'Verifying source…'}
            </span>
          </div>
          <div className="relative aspect-video overflow-hidden bg-[#0D2036]">
            {admitted?<video key={scene.clipId} ref={player} controls muted playsInline preload="metadata"
              src={source!.source_url!} aria-label="Procedural sample recording"
              className="h-full w-full object-contain"
              onTimeUpdate={event=>setSeconds(event.currentTarget.currentTime)}
              onSeeked={event=>setSeconds(event.currentTarget.currentTime)}
              onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onEnded={()=>setPlaying(false)}
              onError={()=>setSourceError('The verified recording could not be decoded by this browser.')}/>:
              <div role="status" className="flex h-full items-center justify-center px-6 text-center text-[13px] text-[#D4E0EF]">
                {sourceError||'Checking the recorded source…'}
              </div>}
            <span className="pointer-events-none absolute left-3 top-3 rounded-md bg-[#0D2036]/80 px-2 py-1 text-[10px] font-semibold text-white">PROCEDURAL VIDEO · SIMULATED FINDINGS</span>
            <span className="pointer-events-none absolute right-3 top-3 rounded-md bg-[#0D2036]/80 px-2 py-1 font-mono text-[12px] text-white">{clock(seconds)} / 00:20</span>
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-[#DFE8F4] px-4 py-3">
            <button type="button" disabled={!admitted} onClick={()=>playing?player.current?.pause():void play()}
              className="kw-focus inline-flex h-9 items-center gap-2 rounded-lg bg-[#2563EB] px-4 text-[11px] font-semibold text-white disabled:opacity-45">
              {playing?<Pause size={14}/>:<Play size={14}/>} {playing?'Pause':'Play recording'}
            </button>
            <button type="button" disabled={!admitted} onClick={()=>jump(8)} aria-label="Jump to finding"
              className="kw-focus rounded-lg border border-[#D8E5F3] px-3 py-2 text-[11px] font-semibold text-[#305B92] disabled:opacity-45">Finding · 00:08</button>
            <button type="button" disabled={!admitted} onClick={()=>jump(16)} aria-label="Jump to review"
              className="kw-focus rounded-lg border border-[#D8E5F3] px-3 py-2 text-[11px] font-semibold text-[#305B92] disabled:opacity-45">Review · 00:16</button>
            <button type="button" aria-label="Reset recorded demo" onClick={reset}
              className="kw-focus ml-auto rounded-lg p-2 text-[#58718F]" title="Reset this scenario"><RotateCcw size={17}/></button>
          </div>
          {sourceError&&<p role="alert" className="px-4 pb-3 text-[11px] text-[#B42318]">{sourceError}</p>}
        </section>

        <section className={surface+' p-4 sm:p-5'} aria-label="Synthetic analysis timeline">
          <div className="flex items-center justify-between gap-3"><h2 className="text-[15px] font-bold">Playback-linked analysis</h2>
            <span className="text-[10px] font-semibold text-[#6C829E]">{stage.timeline.length} / {scene.events.length} checkpoints</span></div>
          <div className="mt-3 grid grid-cols-5 gap-1.5" role="group" aria-label="Simulation checkpoints">
            {scene.events.map(event=><button type="button" key={event.at} disabled={!admitted}
              onClick={()=>jump(event.at)} title={event.title}
              className={'kw-focus h-2.5 rounded-full transition-colors '+(event.at<=seconds?'bg-[#2563EB]':'bg-[#E3EBF4]')}/>
            )}
          </div>
          <div className="mt-4 space-y-2">
            {scene.events.map(event=><div key={event.at} className={'flex items-start gap-3 rounded-xl border p-3 '+
              (event.at<=seconds?'border-[#E0EBFA] bg-[#F7FAFF]':'border-transparent bg-[#FBFCFE] opacity-55')}>
              <span className={'flex h-8 w-12 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold '+(event.at<=seconds?'bg-[#DFEBFF] text-[#195DB6]':'bg-[#F1F4F9] text-[#8B99A8]')}>{clock(event.at)}</span>
              <div className="min-w-0"><strong className="text-[12px] text-[#314761]">{event.title}</strong>
                <p className="mt-0.5 text-[11px] leading-5 text-[#71849C]">{event.detail}</p></div>
              {event.at<=seconds&&<CheckCircle2 size={16} className="ml-auto shrink-0 text-[#0FA776]"/>}
            </div>)}
          </div>
        </section>
      </div>

      <aside className="min-w-0 space-y-4">
        <section className={surface+' overflow-hidden'} aria-label="KaushalAI scripted copilot">
          <div className="border-b border-[#E1EAF6] bg-gradient-to-r from-[#EFF5FF] to-white px-4 py-4 sm:px-5">
            <div className="flex items-center gap-2"><Sparkles size={19} className="text-[#1E63CF]"/><h2 className="text-[17px] font-bold text-[#1F3B6B]">KaushalAI copilot</h2></div>
            <p className="mt-1 text-[11px] text-[#6882A4]">Deterministic, scene-aware demo answers · no external AI call</p>
          </div>
          <div className="p-4 sm:p-5">
            <p className="text-[10px] font-bold uppercase tracking-[.13em] text-[#8699B2]">Current signal</p>
            <p className="mt-2 min-h-[66px] text-[13px] leading-6 text-[#355271]" aria-live="polite">
              {stage.sampled?scene.finding:'Play the recorded scene. The simulation will surface its result at the 00:08 checkpoint.'}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {['Summarise this scene','Why is this flagged?','What should we do next?'].map(label=><button type="button" key={label} onClick={()=>ask(label)}
                className="kw-focus rounded-full border border-[#D9E6F8] bg-[#F8FBFF] px-3 py-2 text-[10px] font-medium text-[#285DA6] hover:bg-[#EFF6FF]">{label}</button>)}
            </div>
            <div className="mt-4 max-h-[220px] space-y-3 overflow-y-auto" aria-label="Scripted AI conversation" aria-live="polite">
              {aiConversation.map((entry,i)=><div key={i} className="space-y-1.5">
                <p className="text-right text-[11px] font-semibold text-[#3E618F]">{entry.question}</p>
                <p className="rounded-xl bg-[#EEF5FF] p-3 text-[11px] leading-5 text-[#355371]">{entry.answer}</p>
              </div>)}
            </div>
            <form onSubmit={event=>{event.preventDefault();ask(question)}} className="mt-4 flex min-w-0 gap-2 border-t border-[#E9EDF5] pt-4">
              <label className="sr-only" htmlFor="studio-ai-question">Ask scripted KaushalAI</label>
              <input id="studio-ai-question" value={question} onChange={event=>setQuestion(event.target.value)} maxLength={400}
                placeholder="Ask about this scene…" className="kw-focus min-w-0 flex-1 rounded-xl border border-[#D8E5F5] bg-white px-3 py-2.5 text-[11px]"/>
              <button type="submit" disabled={!question.trim()} aria-label="Ask scene question"
                className="kw-focus rounded-xl bg-[#2563EB] px-3 text-white disabled:opacity-45"><Send size={16}/></button>
            </form>
          </div>
        </section>

        <section className={surface+' p-4 sm:p-5'} aria-label="Current simulated case status">
          <div className="flex items-center gap-2"><FileCheck2 size={17} className="text-[#2465CE]"/><h2 className="text-[14px] font-bold">Officer decision</h2></div>
          <div className="mt-3 rounded-xl bg-[#F7FAFE] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <strong className="text-[13px] text-[#273F60]">{scene.title}</strong>
              <span className={'rounded-full px-2 py-1 text-[10px] font-semibold '+(sceneReviewed?'bg-[#E8F8F0] text-[#0B8456]':stage.flagged?'bg-[#FFF3E5] text-[#A36513]':'bg-[#EAF1FA] text-[#58718D]')}>
                {sceneReviewed?'Reviewed':stage.flagged?'Officer review':'Awaiting checkpoint'}
              </span>
            </div>
            <p className="mt-2 text-[11px] leading-5 text-[#72849A]">{stage.flagged?scene.recommendation:'Complete the recording checkpoints to prepare a simulated case.'}</p>
          </div>
          <button type="button" onClick={()=>setReviewed(previous=>({...previous,[sceneId]:true}))} disabled={!stage.prepared||sceneReviewed}
            className="kw-focus mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#173E75] px-4 py-3 text-[11px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45">
            <CheckCircle2 size={16}/>{sceneReviewed?'Review recorded locally':'Mark simulation reviewed'}
          </button>
          <p className="mt-2 text-[10px] leading-5 text-[#8193AA]">No real compliance case, official decision or external notification is created.</p>
        </section>
      </aside>
    </div>

    <section className={surface+' overflow-hidden'} aria-label="Five-module synthetic workbench">
      <div className="flex gap-1 overflow-x-auto border-b border-[#E7EDF6] p-2 sm:p-3" role="tablist" aria-label="Demo modules">
        {STUDIO_VIEWS.map(item=><button key={item} type="button" role="tab" aria-selected={view===item} onClick={()=>setView(item)}
          className={'kw-focus shrink-0 rounded-xl px-3 py-2.5 text-[11px] font-semibold sm:px-4 '+(view===item?'bg-[#EAF3FF] text-[#1D5DB7]':'text-[#71839A] hover:bg-[#F7FAFD]')}>{item}</button>)}
      </div>
      <div role="tabpanel" className="min-h-[170px] p-4 sm:p-5">
        {view==='Overview'&&<div className="grid gap-3 sm:grid-cols-3">
          <Metric title="Reported (scripted)" value={scene.reported??'—'} icon={<Users size={17}/>} tone="blue"/>
          <Metric title="Observed (scripted)" value={stage.sampled?(scene.observed??'Unknown'):'—'} icon={<BarChart3 size={17}/>} tone="green"/>
          <Metric title="Officer action" value={sceneReviewed?'Reviewed':stage.flagged?'Review needed':'Pending'} icon={<FileCheck2 size={17}/>} tone="amber"/>
        </div>}
        {view==='Issues'&&<div className="grid gap-3 lg:grid-cols-[minmax(0,.9fr)_minmax(0,1.1fr)]">
          <div className="rounded-xl border border-[#E6EBF3] bg-[#F8FAFE] p-4"><h3 className="text-[14px] font-bold">{scene.title}</h3>
            <p className="mt-2 text-[12px] text-[#657B99]">{stage.flagged?scene.issue:'No finding has entered the scripted queue yet.'}</p>
            <span className="mt-3 inline-block rounded-lg bg-[#E8F1FE] px-2.5 py-1.5 text-[10px] font-semibold text-[#1F60BE]">{stage.flagged?'Synthetic issue opened':'Awaiting 00:12'}</span></div>
          <div className="rounded-xl border border-[#E6EBF3] p-4"><h3 className="text-[13px] font-bold">Evidence trail</h3>
            <p className="mt-2 text-[11px] leading-6 text-[#617A95]">{stage.sampled?scene.finding:'No synthetic detection has been generated yet.'}</p>
            <p className="mt-2 text-[10px] text-[#8A9BAE]">Reference: {scene.clipId} · procedural footage · timestamp {clock(seconds)}</p></div>
        </div>}
        {view==='Insights'&&<div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <div><h3 className="text-[13px] font-bold">Scenario comparison</h3>
            <p className="mt-1 text-[10px] text-[#8797A8]">Illustrative values, not estimated from the recording</p>
            {scene.reported!=null&&<div className="mt-4 space-y-3"><Meter label="Reported" value={scene.reported} max={Math.max(1,scene.reported)} color="bg-[#2E6EEB]"/>
              {stage.sampled&&scene.observed!==null?<Meter label="Observed" value={scene.observed} max={Math.max(1,scene.reported)} color="bg-[#0FA96C]"/>:
                <p className="text-[11px] text-[#7D8EA4]">{stage.sampled?'Observed: unknown (camera gate)':'Observed: pending playback'}</p>}</div>}</div>
          <div className="rounded-xl bg-[#F7FAFE] p-4"><h3 className="text-[13px] font-bold">Scenario audit</h3>
            <p className="mt-2 text-[11px] text-[#657B96]">{stage.timeline.length} of 5 simulated checkpoints completed.</p>
            <p className="mt-2 text-[11px] leading-5 text-[#657B96]">{stage.flagged?scene.recommendation:'Continue to 00:12 for the scripted review signal.'}</p></div>
        </div>}
        {view==='Centre Desk'&&<div className="flex flex-wrap items-center justify-between gap-4 rounded-xl bg-[#F8FAFE] p-4">
          <div><h3 className="text-[13px] font-bold">Today's synthetic follow-up</h3>
            <p className="mt-1 max-w-xl text-[12px] leading-6 text-[#6C8098]">{stage.prepared?scene.recommendation:'Follow-up becomes available once the recording reaches 00:16.'}</p>
            <p className="mt-1 text-[10px] text-[#8293AA]">{scene.centre} · {scene.role}</p></div>
          <span className="rounded-full bg-[#EAF2FF] px-3 py-1.5 text-[11px] font-semibold text-[#2363BB]">{sceneReviewed?'Reviewed':stage.prepared?'Action queued':'Pending'}</span></div>}
        {view==='Chatbox'&&<div className="grid gap-4 md:grid-cols-[minmax(0,.8fr)_minmax(0,1.2fr)]">
          <div><h3 className="text-[13px] font-bold">{scene.centre} · {scene.role}</h3>
            <p className="mt-1 text-[11px] leading-5 text-[#6D8198]">Scripted, in-browser exchange. No message is delivered to an actual recipient.</p>
            <p className="mt-3 rounded-xl bg-[#F1F6FD] p-3 text-[11px] text-[#4E6886]">{stage.prepared?'Officer: '+scene.recommendation:'Conversation opens at 00:16.'}</p></div>
          <div>
            <div className="max-h-40 space-y-2 overflow-y-auto" aria-label="Demo conversation history">{messages.map((item,i)=><div key={i}
              className={'rounded-lg p-2.5 text-[11px] leading-5 '+(item.author==='Officer'?'bg-[#E9F2FF] text-[#295A91]':'bg-[#EAF8F1] text-[#287251]')}>
              <strong>{item.author} · {clock(item.at)}</strong><p>{item.text}</p></div>)}</div>
            <form onSubmit={sendChat} className="mt-3 flex gap-2">
              <label htmlFor="studio-chat-message" className="sr-only">Compose simulated message</label>
              <input id="studio-chat-message" maxLength={500} disabled={!stage.prepared} value={chatDraft} onChange={event=>setChatDraft(event.target.value)}
                placeholder="Write a simulated follow-up…" className="kw-focus min-w-0 flex-1 rounded-xl border border-[#D9E5F2] px-3 py-2.5 text-[11px] disabled:bg-[#F3F5F8]"/>
              <button type="submit" aria-label="Send simulated message" disabled={!chatDraft.trim()||!stage.prepared}
                className="kw-focus rounded-xl bg-[#2563EB] px-3 text-white disabled:opacity-40"><Send size={15}/></button>
            </form>
          </div>
        </div>}
      </div>
    </section>
    <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-[10px] text-[#8999AB]">
      <span className="inline-flex items-center gap-1.5"><Clock3 size={13}/> Session-local simulation · recording time {clock(seconds)} · no real people evaluated</span>
      <Link href="/demo/mission" className="kw-focus inline-flex items-center gap-1 font-semibold text-[#2F67B5]">View evidence mission <ArrowRight size={14}/></Link>
    </div>
  </div>;
}

function Metric({title,value,icon,tone}:{
  title:string;value:string|number;icon:React.ReactNode;tone:'blue'|'green'|'amber';
}){
  const color=tone==='blue'?'text-[#2769CE] bg-[#EDF4FF]':tone==='green'?'text-[#159965] bg-[#EBF9F1]':'text-[#BE7A20] bg-[#FFF7EA]';
  return <div className="rounded-xl border border-[#E5ECF5] p-4"><div className={'inline-flex h-9 w-9 items-center justify-center rounded-lg '+color}>{icon}</div>
    <p className="mt-2 text-[11px] text-[#71859B]">{title}</p><strong className="mt-1 block text-[25px] font-bold tracking-tight text-[#253E60]">{value}</strong></div>;
}

function Meter({label,value,max,color}:{label:string;value:number;max:number;color:string}){
  return <div><div className="flex justify-between text-[11px] text-[#55708C]"><span>{label}</span><strong>{value}</strong></div>
    <div className="mt-1.5 h-2 rounded-full bg-[#E5EDF8]"><div className={'h-full rounded-full '+color} style={{width:Math.min(100,value/max*100)+'%'}}/></div></div>;
}
