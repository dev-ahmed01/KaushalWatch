'use client';
import Link from 'next/link';
import {useEffect,useState} from 'react';
import {ArrowLeft,ArrowRight,Camera,FileSearch,ShieldCheck,WifiOff} from 'lucide-react';
import {DEMO_SCENES,STAGES,stageDescription,type SceneId} from '../../lib/demoMission';
import {SECURE_PROXY,getCases,getCentreIntelligence} from '../../lib/api';
import type {CaseRecord,CentreIntelligence} from '../../lib/types';

const surface='rounded-[22px] border border-[#E0E9F4] bg-white shadow-[0_3px_20px_rgba(20,44,77,0.04)]';
export default function MissionPage(){
  const [sceneId,setSceneId]=useState<SceneId>('attendance');
  const [step,setStep]=useState(0);
  const [info,setInfo]=useState<CentreIntelligence|null>(null);
  const [cases,setCases]=useState<CaseRecord[]>([]);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState(false);
  const [retry,setRetry]=useState(0);
  const scene=DEMO_SCENES.find(s=>s.id===sceneId)||DEMO_SCENES[0];

  useEffect(()=>{
    if(SECURE_PROXY)return;
    let active=true;
    setLoading(true);setError(false);setInfo(null);setCases([]);
    Promise.allSettled([getCentreIntelligence(scene.centreId,'last_7_days'),getCases()])
      .then(([centreResult,casesResult])=>{
        if(!active)return;
        if(centreResult.status==='fulfilled')setInfo(centreResult.value);
        if(casesResult.status==='fulfilled')setCases(casesResult.value.filter(c=>c.centre_id===scene.centreId));
        if(centreResult.status==='rejected'||casesResult.status==='rejected')setError(true);
      }).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false};
  },[scene.centreId,retry]);

  // Scenario data are explicitly authored; a real saved API source overrides a
  // fixture only if it supplies a non-null, source-grounded comparison.
  const metric=info?.verification[scene.id==='equipment'?'infrastructure':'attendance'];
  const apiFacts=Boolean(metric&&metric.source!=='unavailable'&&metric.reported!=null&&metric.observed!=null);
  const reported=apiFacts?metric!.reported:scene.reported;
  const observed=scene.id==='camera'?null:apiFacts?metric!.observed:scene.observed;
  const caseRecord=cases.find(c=>scene.id==='attendance'?c.case_type==='attendance_discrepancy':
    scene.id==='equipment'?c.case_type==='infrastructure_compliance':false);
  const decision=scene.id==='camera'?'Evidence insufficient':scene.id==='normal'?'No exception in this scenario':'Officer review needed';

  if(SECURE_PROXY)return <div className={surface+' p-8'} role="alert">
    <h1 className="text-[26px] font-bold">Controlled mission unavailable</h1>
    <p className="mt-3 text-[13px]">Synthetic centre scenarios are disabled in protected officer deployments.</p>
    <Link href="/centres" className="kw-focus mt-4 inline-flex text-[#275C9A]">Open authorised centres</Link>
  </div>;

  function select(id:SceneId){setSceneId(id);setStep(0);}
  return <div className="space-y-5 pb-8">
    <header className="flex flex-wrap items-center justify-between gap-2">
      <Link className="kw-focus inline-flex items-center gap-1 text-[12px] text-[#667C94]" href="/"><ArrowLeft size={15}/> KaushalAI</Link>
      <span className="rounded-full border border-[#D8E6F6] bg-[#F2F7FE] px-3 py-1 text-[11px] font-semibold text-[#285F96]">Controlled SIH scenarios · simulated</span>
    </header>
    <section className="relative overflow-hidden rounded-[24px] bg-[#173456] px-6 py-8 text-white sm:px-9 sm:py-10">
      <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full border border-white/10 bg-[#2E5889]/20"/>
      <div className="relative">
        <div className="text-[11px] font-bold uppercase tracking-[.18em] text-[#AAC8EB]">KaushalWatch · Proof of Training</div>
        <h1 className="mt-3 max-w-[750px] text-[clamp(28px,4vw,44px)] font-bold leading-tight tracking-[-.045em]">A centre reports. Evidence responds. An officer decides.</h1>
        <p className="mt-4 max-w-[620px] text-[13px] leading-6 text-[#D4E1F0]">Not just another people counter. Follow four controlled inspection scenarios to see how trust changes the outcome.</p>
        <div className="mt-5 flex flex-wrap gap-4 text-[11px] text-[#D4E1F0]">
          <span className="inline-flex items-center gap-2"><Camera size={15}/> Anonymous observation</span>
          <span className="inline-flex items-center gap-2"><ShieldCheck size={15}/> Evidence quality gate</span>
          <span className="inline-flex items-center gap-2"><FileSearch size={15}/> Human review</span>
        </div>
      </div>
    </section>
    <div className="grid gap-5 xl:grid-cols-[270px_minmax(0,1fr)]">
      <nav className={surface+' h-fit p-3'} aria-label="Controlled scenarios">
        <div className="px-3 pb-3 pt-2 text-[14px] font-bold text-[#283E5A]">Four proof scenarios</div>
        {DEMO_SCENES.map((item,i)=><button type="button" key={item.id}
          onClick={()=>select(item.id)} aria-pressed={scene.id===item.id}
          className={'kw-focus mb-1 flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left '+
            (scene.id===item.id?'border-[#BDD2EC] bg-[#EDF5FE]':'border-transparent hover:bg-[#F6F9FD]')}>
            <span className={'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[12px] font-bold '+
              (scene.id===item.id?'bg-[#255990] text-white':'bg-[#EBF1F8] text-[#617C9B]')}>{i+1}</span>
            <span><strong className="block text-[12px] text-[#2E4663]">{item.title}</strong>
              <small className="mt-0.5 block text-[11px] text-[#7B8DA3]">{item.subtitle}</small></span>
          </button>)}
        <Link href="/centres" className="kw-focus mx-3 mt-3 inline-flex items-center gap-1 text-[12px] font-semibold text-[#275D9D]">Explore centres <ArrowRight size={13}/></Link>
      </nav>
      <article className={surface+' min-w-0 p-5 sm:p-7'} aria-label="Controlled scenario inspection">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><p className="text-[11px] font-semibold uppercase tracking-[.14em] text-[#6B85A3]">{scene.subtitle}</p>
            <h2 className="mt-1 text-[26px] font-bold tracking-[-.035em] text-[#263D57]">{scene.title}</h2>
            <p className="mt-2 max-w-[610px] text-[13px] text-[#5B728C]">{scene.question}</p></div>
          <span className={'rounded-full px-3 py-1.5 text-[11px] font-semibold '+
            (scene.id==='camera'?'bg-[#ECF2FA] text-[#405C80]':scene.id==='normal'?'bg-[#EAF7F0] text-[#216D4C]':'bg-[#FFF3E4] text-[#956018]')}>{decision}</span>
        </div>
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div className="rounded-xl bg-[#F4F8FC] p-4"><div className="text-[11px] text-[#7389A1]">Reported</div>
            <strong className="mt-1 block text-[30px] font-bold tabular-nums text-[#234367]">{reported??'—'}</strong><div className="text-[11px] text-[#8192A8]">{scene.unit}</div></div>
          <div className="rounded-xl bg-[#F4F8FC] p-4"><div className="text-[11px] text-[#7389A1]">Observed</div>
            <strong className="mt-1 block text-[30px] font-bold tabular-nums text-[#234367]">{observed??'—'}</strong>
            <div className="text-[11px] text-[#8192A8]">{observed===null?'Withheld · not zero':scene.unit}</div></div>
          <div className="col-span-2 rounded-xl border border-[#E1EAF4] bg-[#FAFCFF] p-4 sm:col-span-1">
            <div className="text-[11px] text-[#7389A1]">Outcome</div>
            <div className="mt-2 text-[14px] font-bold text-[#2A4A6B]">{decision}</div>
            <div className="mt-2 text-[10px] leading-4 text-[#7389A1]">{loading?'Loading records…':apiFacts?'Saved API comparison':'Scenario fixture, not AI inference'}</div></div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-[#6D819A]">
          <ShieldCheck size={13}/>{apiFacts?(info?.simulated||metric?.simulated?'Simulated API record':'Saved analysis/case record'):'Authored controlled example'}
          {error&&<button type="button" className="kw-focus font-semibold text-[#255C9D] underline" onClick={()=>setRetry(v=>v+1)}>Retry source</button>}
        </div>
        <div className="mt-7">
          <div className="flex items-center justify-between"><h3 className="text-[14px] font-bold text-[#2B415C]">The evidence trail</h3><span className="text-[11px] text-[#7E90A7]">{step+1}/4</span></div>
          <div className="mt-3 grid grid-cols-4 gap-2">{STAGES.map((label,i)=><button key={label} type="button" aria-pressed={step===i}
            onClick={()=>setStep(i)} className={'kw-focus rounded-lg border px-1.5 py-2 text-[10px] font-semibold sm:text-[12px] '+
              (step===i?'border-[#8EB4E0] bg-[#EBF4FF] text-[#215C9B]':'border-[#E5ECF5] text-[#6B8098]')}>{label}</button>)}</div>
          <div className="mt-3 min-h-28 rounded-xl bg-[#F5F8FC] p-4" role="region" aria-label="Selected evidence step">
            <p className="text-[11px] font-bold uppercase tracking-[.12em] text-[#768AA2]">{STAGES[step]}</p>
            <p className="mt-2 text-[13px] leading-6 text-[#385471]">{stageDescription(scene,step)}</p>
          </div>
          <div className="mt-3 flex items-center justify-between">
            <button type="button" disabled={step===0} onClick={()=>setStep(x=>Math.max(0,x-1))}
              className="kw-focus rounded-lg px-3 py-2 text-[12px] font-semibold text-[#526B88] disabled:opacity-35">Back</button>
            <button type="button" onClick={()=>step<3?setStep(x=>x+1):
              select(DEMO_SCENES[(DEMO_SCENES.findIndex(x=>x.id===scene.id)+1)%DEMO_SCENES.length].id)}
              className="kw-focus inline-flex items-center gap-2 rounded-xl bg-[#23568C] px-4 py-2.5 text-[12px] font-semibold text-white hover:bg-[#1A4577]">
              {step===3?'Next scenario':'Next evidence step'} <ArrowRight size={14}/></button>
          </div>
        </div>
        <div className="mt-7 grid gap-3 md:grid-cols-2">
          <div className="rounded-xl border border-[#F1E5D9] bg-[#FFFBF6] p-4"><p className="text-[11px] font-semibold text-[#A36B31]">Simplistic approach</p>
            <p className="mt-2 text-[12px] leading-5 text-[#775635]">{scene.compare}</p></div>
          <div className="rounded-xl border border-[#D8EAE0] bg-[#F4FBF7] p-4"><p className="text-[11px] font-semibold text-[#2B7151]">KaushalWatch</p>
            <p className="mt-2 text-[12px] leading-5 text-[#37624E]">{scene.conclusion}</p></div>
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-[#ECF0F5] pt-5">
          <Link href={scene.href} className="kw-focus inline-flex items-center gap-2 rounded-xl bg-[#EAF3FC] px-4 py-2.5 text-[12px] font-semibold text-[#245B96]">
            Open centre evidence <ArrowRight size={14}/></Link>
          {caseRecord&&<Link href={'/cases/'+encodeURIComponent(caseRecord.case_id)}
            className="kw-focus text-[12px] font-semibold text-[#355F8A]">Open saved case</Link>}
        </div>
      </article>
    </div>
    <section className="grid gap-3 md:grid-cols-2" aria-label="Further proof">
      <div className={surface+' p-4'}><WifiOff size={17} className="text-[#5C7DA4]"/>
        <h3 className="mt-2 text-[13px] font-bold text-[#2A4666]">Offline by design</h3>
        <p className="mt-1 text-[11px] text-[#70849C]">The edge agent already queues privacy-safe data. A measured disconnect/reconnect presentation is planned for Phase 4.</p></div>
      <div className={surface+' p-4'}><ShieldCheck size={17} className="text-[#5C7DA4]"/>
        <h3 className="mt-2 text-[13px] font-bold text-[#2A4666]">Officers remain accountable</h3>
        <p className="mt-1 text-[11px] text-[#70849C]">This walkthrough never modifies a case, issues a legal notice or touches a real grant.</p></div>
    </section>
  </div>;
}
