'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import CentreTabs from '../../../components/CentreTabs';
import { API, SECURE_PROXY, getReviewAccess, officerFetch } from '../../../lib/api';

type Camera = {
  camera_id:string; centre_id:string; label:string; source_alias:string;
  physical_health:string; production_qualified:boolean; created_at:string;
};
type Job = {job_id:string;status:string;attempts:number;last_error:string|null;created_at:string};
type Observation = {
  observation_id:string;created_at:string;review_status:string;
  payload:{sampled_frames:number;possible_review_samples:number;failed_positions:number[];
    authorized_reference_file_present:boolean; sampling:string; physical_camera_health:string;
    samples?:Array<{requested_frame0:number;candidate_for_human_review:boolean;
      illumination:string;geometry:{state:string};focus:{state:string};
      localized_coverage:{state:string}}>;
  };
};
type Reference = {reference_id:string; status:string; proposed_by:string;
  sha256:string; captured_at:string; approved_by:string|null};
const classes='w-full rounded-xl border border-[#D0D9E4] bg-white px-3 py-2 text-[13px] text-[#344054]';
const btn='kw-focus rounded-xl border border-[#CED7E2] bg-white px-4 py-2 text-[13px] font-medium text-[#344054] hover:bg-[#F4F7FB] disabled:opacity-50';
const card='rounded-[18px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]';
const stateLabel=(s:string)=>s.replaceAll('_',' ');
function short(value:string){return value.slice(0,10);}
function message(e:unknown){return e instanceof Error?e.message:'Request unavailable';}

export default function CameraTrustPage(){
  const {centreId}=useParams<{centreId:string}>();
  const centre=String(centreId);
  const path=`${API}/api/centres/${encodeURIComponent(centre)}/camera-trust`;
  const [cameras,setCameras]=useState<Camera[]>([]);
  const [selected,setSelected]=useState('');
  const [jobs,setJobs]=useState<Job[]>([]);
  const [observations,setObservations]=useState<Observation[]>([]);
  const [references,setReferences]=useState<Reference[]>([]);
  const [canWrite,setCanWrite]=useState(!SECURE_PROXY);
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [label,setLabel]=useState('');
  const [alias,setAlias]=useState('');
  const [key,setKey]=useState('');
  const [sampleLimit,setSampleLimit]=useState(48);
  const [refsha,setRefsha]=useState('');
  const [captured,setCaptured]=useState('');
  const [custody,setCustody]=useState('');
  const [reviewNotes,setReviewNotes]=useState<Record<string,string>>({});

  const request=useCallback(async <T,>(url:string,method='GET',body?:object):Promise<T>=>{
    const r=await officerFetch(url,{
      method,headers:body?{'Content-Type':'application/json'}:undefined,
      body:body?JSON.stringify(body):undefined,cache:'no-store',
    });
    const payload=await r.json().catch(()=>({detail:'Invalid server response'}));
    if(!r.ok)throw new Error(payload.detail || 'Request failed');
    return payload as T;
  },[]);
  const load=useCallback(async()=>{
    setError('');
    try{
      const o=await request<{cameras:Camera[]}>(path);
      setCameras(o.cameras);
      setSelected(previous=>o.cameras.some(c=>c.camera_id===previous)?previous:(o.cameras[0]?.camera_id||''));
    }catch(e){setError(message(e));}
    finally{setLoading(false);}
  },[path,request]);
  useEffect(()=>{void load();},[load]);
  useEffect(()=>{
    if(!SECURE_PROXY)return;
    getReviewAccess().then(x=>setCanWrite(x.can_write===true)).catch(()=>setCanWrite(false));
  },[]);
  const refreshCamera=useCallback(async()=>{
    if(!selected){setJobs([]);setObservations([]);setReferences([]);return;}
    try{
      const url=path+'/'+encodeURIComponent(selected);
      const [j,o,r]=await Promise.all([
        request<{jobs:Job[]}>(url+'/jobs'),
        request<{observations:Observation[]}>(url+'/observations'),
        request<{references:Reference[]}>(url+'/references'),
      ]);
      setJobs(j.jobs);setObservations(o.observations);setReferences(r.references);
    }catch(e){setError(message(e));}
  },[selected,path,request]);
  useEffect(()=>{void refreshCamera();},[refreshCamera]);
  const camera=cameras.find(c=>c.camera_id===selected);
  async function mutate<T>(url:string,body?:object){
    setBusy(true);setError('');setNotice('');
    try{
      const result=await request<T>(url,'POST',body);
      setNotice('Saved to the Camera Trust audit workflow.');
      await load();await refreshCamera();
      return result;
    }catch(e){setError(message(e));return null;}
    finally{setBusy(false);}
  }
  return <div className="space-y-6">
    <header>
      <Link href={'/centres/'+encodeURIComponent(centre)} className="text-[12px] font-medium text-[#64748B]">← Centre overview</Link>
      <h1 className="mt-2 text-[30px] font-semibold tracking-[-0.035em] text-[var(--kw-text)]">Camera Trust</h1>
      <p className="mt-1 max-w-3xl text-[13px] leading-6 text-[var(--kw-muted)]">
        Review source-pinned camera-quality observations, approvals and analysis jobs. A numerical warning is not a verified physical tamper event.
      </p>
    </header>
    <CentreTabs centreId={centre}/>
    <div className="grid gap-3 md:grid-cols-3">
      {[
        ['Release','Not production-qualified'],
        ['Physical camera health','UNKNOWN'],
        ['Enforcement effects','None — shadow only'],
      ].map(([name,value])=><div className={card} key={name}>
        <p className="text-[11px] text-[#667085]">{name}</p>
        <p className="mt-2 text-[14px] font-semibold text-[#344054]">{value}</p>
      </div>)}
    </div>
    {error&&<div role="alert" className="rounded-xl border border-[#FED7AA] bg-[#FFF7ED] p-4 text-[13px] text-[#9A3412]">{error}</div>}
    {notice&&<div role="status" className="rounded-xl border border-[#BBF7D0] bg-[#F0FDF4] p-4 text-[13px] text-[#166534]">{notice}</div>}
    <div className="grid gap-5 lg:grid-cols-[.8fr_1.2fr]">
      <section className={card}>
        <h2 className="text-[16px] font-semibold">Registered cameras</h2>
        <p className="mt-1 text-[12px] text-[#667085]">Private source alias, never a public Drive link.</p>
        <div className="mt-4 space-y-2">
          {cameras.map(c=><button key={c.camera_id} onClick={()=>setSelected(c.camera_id)}
            aria-pressed={c.camera_id===selected}
            className={'kw-focus w-full rounded-xl border p-3 text-left text-[13px] '+
              (c.camera_id===selected?'border-[#93B4F6] bg-[#EFF6FF]':'border-[#E6EAF0] bg-[#FAFBFD]')}>
            <strong>{c.label}</strong><span className="ml-2 text-[11px] text-[#64748B]">UNKNOWN</span>
            <div className="mt-1 break-all text-[11px] text-[#667085]">{c.source_alias}</div>
          </button>)}
          {!loading&&!cameras.length&&<p className="text-[12px] text-[#667085]">No cameras registered. This is not a healthy-camera finding.</p>}
        </div>
        {canWrite&&<form className="mt-6 space-y-3" onSubmit={async e=>{
          e.preventDefault();
          const result=await mutate<Camera>(path+'/cameras',{label,source_alias:alias});
          if(result){setLabel('');setAlias('');setSelected(result.camera_id);}
        }}>
          <h3 className="text-[14px] font-semibold">Register source</h3>
          <label className="block text-[12px]">Camera label
            <input className={'mt-1 '+classes} value={label} onChange={e=>setLabel(e.target.value)} minLength={3} maxLength={80} required/>
          </label>
          <label className="block text-[12px]">Approved private source filename
            <input className={'mt-1 '+classes} value={alias} onChange={e=>setAlias(e.target.value)} required placeholder="camera-day3.avi"/>
          </label>
          <p className="text-[11px] text-[#667085]">Source must already have an approved SHA-256 pin in the server-side private manifest.</p>
          <button className={btn} type="submit" disabled={busy}>Register camera</button>
        </form>}
      </section>
      <div className="space-y-5">
        {!camera?<section className={card}><p className="text-[13px] text-[#667085]">Select a camera to inspect its reference, jobs and observations.</p></section>:
        <>
          <section className={card}>
            <h2 className="text-[16px] font-semibold">Analysis jobs</h2>
            <p className="mt-1 text-[12px] text-[#667085]">A private worker downloads the approved source once and resumes interrupted transfers.</p>
            {canWrite&&<form onSubmit={async e=>{
              e.preventDefault();
              const result=await mutate<{job_id:string}>(path+'/'+camera.camera_id+'/jobs',
                {idempotency_key:key,sample_limit:sampleLimit});
              if(result)setKey('');
            }} className="mt-4 grid gap-3 sm:grid-cols-[1fr_120px_auto] sm:items-end">
              <label className="text-[12px]">Analysis request ID
                <input className={'mt-1 '+classes} minLength={8} maxLength={100}
                  value={key} onChange={e=>setKey(e.target.value)} placeholder="review-2026-10-18" required/>
              </label>
              <label className="text-[12px]">Max samples
                <input className={'mt-1 '+classes} type="number" min={12} max={180}
                  value={sampleLimit} onChange={e=>setSampleLimit(Number(e.target.value))} required/>
              </label>
              <button disabled={busy} className={btn} type="submit">Queue analysis</button>
            </form>}
            <div className="mt-4 divide-y divide-[#EEF2F6]">
              {jobs.map(j=><div key={j.job_id} className="flex items-center justify-between gap-3 py-3 text-[12px]">
                <div><strong className="capitalize">{stateLabel(j.status)}</strong>
                  <span className="ml-2 font-mono text-[10px] text-[#667085]">{short(j.job_id)}</span>
                  <p className="mt-1 text-[11px] text-[#98A2B3]">Attempt {j.attempts} · {j.last_error||'No worker errors recorded'}</p></div>
                {canWrite&&j.status==='queued'&&<button className={btn} disabled={busy}
                  onClick={()=>void mutate(path+'/'+camera.camera_id+'/jobs/'+j.job_id+'/cancel')}>Cancel</button>}
              </div>)}
              {!jobs.length&&<p className="py-4 text-[12px] text-[#667085]">No queued source analysis yet.</p>}
            </div>
            <button className={'mt-3 '+btn} onClick={()=>void refreshCamera()}>Refresh jobs</button>
          </section>
          <section className={card}>
            <h2 className="text-[16px] font-semibold">Custodial reference proposals</h2>
            <p className="mt-1 text-[12px] text-[#667085]">One officer proposes; a different officer approves. No automatic reference replacement or re-enrollment.</p>
            {canWrite&&<form onSubmit={async e=>{
              e.preventDefault();
              const r=await mutate(path+'/'+camera.camera_id+'/references',
                {sha256:refsha,captured_at:new Date(captured).toISOString(),custody_note:custody});
              if(r){setRefsha('');setCaptured('');setCustody('');}
            }} className="mt-4 space-y-3">
              <label className="block text-[12px]">Reference PNG SHA-256
                <input className={'mt-1 '+classes} pattern="[a-f0-9]{64}" value={refsha}
                  onChange={e=>setRefsha(e.target.value)} required/>
              </label>
              <label className="block text-[12px]">Capture timestamp (local)
                <input type="datetime-local" className={'mt-1 '+classes} value={captured}
                  onChange={e=>setCaptured(e.target.value)} required/>
              </label>
              <label className="block text-[12px]">Custody evidence and authorization note
                <textarea className={'mt-1 '+classes} minLength={15} maxLength={1000}
                  value={custody} onChange={e=>setCustody(e.target.value)} required/>
              </label>
              <button className={btn} type="submit" disabled={busy}>Propose reference</button>
            </form>}
            {references.map(r=><div key={r.reference_id} className="mt-4 rounded-xl border border-[#EEF2F6] p-3 text-[12px]">
              <div className="flex flex-wrap items-center justify-between gap-2"><strong className="capitalize">{r.status}</strong><span className="font-mono text-[11px]">{short(r.reference_id)}</span></div>
              <div className="mt-1 break-all text-[11px] text-[#667085]">{r.sha256}</div>
              <p className="mt-1 text-[11px] text-[#667085]">Proposed by {r.proposed_by}; approved by {r.approved_by||'nobody yet'}</p>
              {canWrite&&r.status==='proposed'&&<div className="mt-3 flex gap-2">
                <button className={btn} disabled={busy} onClick={()=>void mutate(path+'/'+camera.camera_id+'/references/'+r.reference_id+'/decision',{approve:true})}>Approve</button>
                <button className={btn} disabled={busy} onClick={()=>void mutate(path+'/'+camera.camera_id+'/references/'+r.reference_id+'/decision',{approve:false})}>Reject</button>
              </div>}
            </div>)}
          </section>
          <section className={card}>
            <h2 className="text-[16px] font-semibold">Evidence observations and decisions</h2>
            <p className="mt-1 text-[12px] text-[#667085]">Sparse video samples are diagnostic proxies; no raw frames are exposed to the browser.</p>
            {observations.map(o=><div key={o.observation_id} className="mt-4 rounded-xl border border-[#E6EAF0] p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-[12px]">
                <strong>{o.payload.possible_review_samples} potential review samples / {o.payload.sampled_frames} inspected</strong>
                <span className="capitalize">{stateLabel(o.review_status)}</span>
              </div>
              <p className="mt-1 text-[11px] text-[#667085]">Physical camera state UNKNOWN · {o.payload.authorized_reference_file_present?'Reference present':'No approved reference image available'}</p>
              <p className="mt-1 text-[11px] text-[#667085]">Failed positions: {o.payload.failed_positions.length} · {o.payload.sampling}</p>
              <details className="mt-3 text-[12px]"><summary className="cursor-pointer font-medium">Numeric cue examples</summary>
                <div className="mt-2 space-y-2">
                  {(o.payload.samples||[]).filter(s=>s.candidate_for_human_review).slice(0,6).map(s=>
                    <p key={s.requested_frame0} className="rounded-lg bg-[#F8FAFC] p-2 text-[11px]">
                      Frame {s.requested_frame0}: {s.illumination} · {s.focus.state} · {s.geometry.state} · {s.localized_coverage.state}
                    </p>)}
                </div>
              </details>
              {canWrite&&o.review_status==='unreviewed'&&<div className="mt-3 space-y-2">
                <label className="block text-[12px]">Officer review note
                  <textarea className={'mt-1 '+classes} value={reviewNotes[o.observation_id]||''}
                    onChange={e=>setReviewNotes(v=>({...v,[o.observation_id]:e.target.value}))}/>
                </label>
                <div className="flex flex-wrap gap-2">{[
                  ['needs_followup','Needs follow-up'],
                  ['not_actionable','Not actionable'],
                  ['reviewed','Reviewed'],
                ].map(([decision,text])=><button key={decision} className={btn} disabled={busy||!(reviewNotes[o.observation_id]||'').trim()|| (reviewNotes[o.observation_id]||'').trim().length<12}
                  onClick={()=>void mutate(path+'/'+camera.camera_id+'/observations/'+o.observation_id+'/review',
                    {decision,note:reviewNotes[o.observation_id]})}>{text}</button>)}</div>
              </div>}
            </div>)}
            {!observations.length&&<p className="mt-4 text-[12px] text-[#667085]">No completed evaluations; camera health remains unknown.</p>}
          </section>
          <p className="text-[11px] text-[#667085]">Audit records are maintained in the protected PostgreSQL ledger. No observation can confirm, close or penalize a compliance case.</p>
        </>}
      </div>
    </div>
  </div>;
}
