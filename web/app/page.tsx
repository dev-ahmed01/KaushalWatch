'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';

type CaseStatus = 'open'|'under_review'|'confirmed'|'false_positive'|'virtual_verification'|'resolved';
type Case = {
  case_id:string; centre_id:string; batch_id:string; case_type:string; severity:string; summary:string; status:CaseStatus;
  discrepancy_pct?:number; reported_attendance?:number; visual_occupancy?:number; persistence_ratio?:number;
  evidence?:{evidence_id:string; duplicate_of?:string|null; sha256:string}[];
  details?:{apparent_operability?:{state?:string;activity_score?:number};[key:string]:any};
  review_history?:{timestamp:string;from_status:string;to_status:string;note?:string|null}[];
};
type Dashboard = {banner:string;centres_monitored:number;open_cases:number;camera_issues:number;synced_edge_events:number;cases:Case[]};
type InfraItem = {id:string;label:string;required:number;observed:number|null;state:string;confidence:number|null};

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Page() {
  const [data,setData]=useState<Dashboard|null>(null);
  const [infra,setInfra]=useState<InfraItem[]>([]);
  const [result,setResult]=useState<any>(null);
  const [infraResult,setInfraResult]=useState<any>(null);
  const [busy,setBusy]=useState(false);
  const [infraBusy,setInfraBusy]=useState(false);
  const [error,setError]=useState('');

  const refresh = async () => {
    const [d,i] = await Promise.all([
      fetch(`${API}/api/dashboard`,{cache:'no-store'}),
      fetch(`${API}/api/demo/infrastructure`,{cache:'no-store'})
    ]);
    if (!d.ok) throw new Error('Dashboard API unavailable');
    setData(await d.json());
    if (i.ok) setInfra((await i.json()).items || []);
  };
  useEffect(()=>{refresh().catch(e=>setError(String(e.message||e)));},[]);

  async function submit(e:FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError(''); setResult(null);
    try {
      const r=await fetch(`${API}/api/process-video`,{method:'POST',body:new FormData(e.currentTarget)});
      const body=await r.json(); if(!r.ok) throw new Error(body.detail||'Video processing failed');
      setResult(body); await refresh();
    } catch(err:any){setError(err.message||String(err));} finally {setBusy(false);}
  }

  async function submitInfrastructure(e:FormEvent<HTMLFormElement>){
    e.preventDefault(); setInfraBusy(true); setError(''); setInfraResult(null);
    try{
      const incoming=new FormData(e.currentTarget);
      const video=incoming.get('infra_file');
      if(!(video instanceof File)){throw new Error('Choose an infrastructure demo video');}
      const body=new FormData();
      body.append('file',video);
      for(const key of ['centre_id','batch_id','camera_id','operability_item_id','roi_x1','roi_y1','roi_x2','roi_y2']){
        const value=incoming.get(key);
        if(value!==null && String(value).trim()!=='') body.append(key,String(value));
      }
      const r=await fetch(`${API}/api/process-infrastructure-video`,{method:'POST',body});
      const payload=await r.json();
      if(!r.ok) throw new Error(payload.detail||'Infrastructure processing failed');
      setInfraResult(payload); await refresh();
    }catch(err:any){setError(err.message||String(err));}finally{setInfraBusy(false);}
  }

  async function review(caseId:string, action:CaseStatus){
    setError('');
    const r=await fetch(`${API}/api/cases/${caseId}/review`,{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})
    });
    if(!r.ok){setError('Could not update case');return;}
    await refresh();
  }

  const priority = useMemo(()=>[...(data?.cases||[])].reverse(),[data]);

  return <main>
    <div className="prototype">PROTOTYPE — SIMULATED OPERATIONAL DATA</div>
    <header>
      <div><p className="eyebrow">PMKVY VISUAL MONITORING</p><h1>KaushalWatch Command Centre</h1><p className="muted">Evidence-backed exceptions. Track position, not identity.</p></div>
      <div className="pill">Human review required</div>
    </header>

    <section className="metrics">
      <Metric label="Demo centres" value={data?.centres_monitored??'—'} />
      <Metric label="Open cases" value={data?.open_cases??'—'} />
      <Metric label="Camera issues" value={data?.camera_issues??'—'} />
      <Metric label="Synced edge events" value={data?.synced_edge_events??'—'} />
      <Metric label="Privacy mode" value="Anonymous" />
    </section>

    <section className="grid">
      <div className="card">
        <div className="sectionHead"><div><h2>Attendance verification</h2><p className="muted">Single-camera footage vs simulated AEBAS attendance.</p></div><span className="tag">LIVE PIPELINE</span></div>
        <form onSubmit={submit}>
          <label>Demo CCTV video<input name="file" type="file" accept="video/*,.avi" required /></label>
          <div className="two">
            <label>Reported attendance<input name="reported_attendance" type="number" defaultValue="12" min="0" required /></label>
            <label>Centre ID<input name="centre_id" defaultValue="DEMO-KA-104" /></label>
          </div>
          <label>Batch ID<input name="batch_id" defaultValue="ELEC-DEMO-01" /></label>
          <button disabled={busy}>{busy?'Analysing…':'Analyse video'}</button>
        </form>
        {error&&<div className="error">{error}</div>}
        {result&&<div className="result">
          <Result label="Reported" value={result.reported_attendance}/><Result label="Visual occupancy" value={result.estimated_occupancy}/>
          <Result label="Mismatch" value={`${result.discrepancy_pct}%`}/><Result label="Case" value={result.case?'Created':'No persistent case'}/>
        </div>}
      </div>

      <div className="card">
        <div className="sectionHead"><div><h2>Priority exceptions</h2><p className="muted">Persistent cases, not frame-level noise.</p></div></div>
        <div className="caseList">
          {priority.length===0&&<div className="empty">No demo cases yet.</div>}
          {priority.map(c=><div className="case" key={c.case_id}>
            <div><span className={`dot ${c.severity}`}></span><strong>{c.centre_id}</strong> · {c.case_id}</div>
            <p>{c.summary}</p>
            <div className="caseMeta"><span>{c.status.replaceAll('_',' ')}</span><span>{c.case_type.replaceAll('_',' ')}</span></div>
            {c.details?.apparent_operability?.state&&<div className="caseDetail"><strong>Apparent operability:</strong> {c.details.apparent_operability.state.replaceAll('_',' ')}</div>}
            <div className="caseLinks">
              {c.evidence?.[0]&&<a className="evidenceLink" href={`${API}/evidence/${c.evidence[0].evidence_id}.jpg`} target="_blank" rel="noreferrer">Open evidence</a>}
              <a className="evidenceLink" href={`${API}/api/cases/${c.case_id}/evidence-pack`} target="_blank" rel="noreferrer">Evidence pack</a>
            </div>
            {c.evidence?.[0]?.duplicate_of&&<div className="warning">Possible duplicate evidence of {c.evidence[0].duplicate_of}</div>}
            {!!c.review_history?.length&&<div className="auditHint">Audit trail: {c.review_history.length} officer action{c.review_history.length===1?'':'s'}</div>}
            <div className="actions">
              <button className="ghost" onClick={()=>review(c.case_id,'under_review')}>Review</button>
              <button className="ghost" onClick={()=>review(c.case_id,'virtual_verification')}>Virtual verify</button>
              <button className="ghost" onClick={()=>review(c.case_id,'false_positive')}>False positive</button>
              <button className="ghost" onClick={()=>review(c.case_id,'confirmed')}>Confirm</button>
            </div>
          </div>)}
        </div>
      </div>
    </section>

    <section className="card infra">
      <div className="sectionHead"><div><h2>Construction Electrician - LV · Visual Compliance Manifest</h2><p className="muted">Cached detections are a stage-safe fallback. Quantities below are demo configuration, not official sanctioned figures.</p></div><span className="tag">DEMO MANIFEST</span></div>
      <form className="infraUpload" onSubmit={submitInfrastructure}>
        <label>Infrastructure demo video<input name="infra_file" type="file" accept="video/*,.avi" required /></label>
        <div className="three">
          <label>Centre ID<input name="centre_id" defaultValue="DEMO-KA-104" /></label>
          <label>Batch ID<input name="batch_id" defaultValue="ELEC-DEMO-01" /></label>
          <label>Camera ID<input name="camera_id" defaultValue="LAB-CAM-02" /></label>
        </div>
        <div className="roiGroup">
          <div><strong>Optional apparent-operability ROI</strong><span>Demo defaults target a moving machine region; this is a visual activity proxy only.</span></div>
          <input aria-label="ROI x1" name="roi_x1" type="number" defaultValue="0" />
          <input aria-label="ROI y1" name="roi_y1" type="number" defaultValue="20" />
          <input aria-label="ROI x2" name="roi_x2" type="number" defaultValue="220" />
          <input aria-label="ROI y2" name="roi_y2" type="number" defaultValue="190" />
          <input type="hidden" name="operability_item_id" value="drill_machine" />
        </div>
        <button disabled={infraBusy}>{infraBusy?'Analysing infrastructure…':'Analyse infrastructure evidence'}</button>
      </form>
      {infraResult?.created&&<div className="result infraResult">
        <Result label="Case" value={infraResult.case.case_id}/>
        <Result label="Type" value="Infrastructure"/>
        <Result label="Evidence" value={infraResult.case.evidence?.length?'Captured':'Missing'}/>
        <Result label="Operability" value={infraResult.case.details?.apparent_operability?.state?.replaceAll('_',' ')||'Not evaluated'}/>
      </div>}
      <div className="table">
        <div className="tr th"><span>Item</span><span>Required</span><span>Observed</span><span>State</span></div>
        {infra.map(x=><div className="tr" key={x.id}><span>{x.label}</span><span>{x.required}</span><span>{x.observed??'Officer'}</span><span className={`state ${x.state.toLowerCase()}`}>{x.state.replaceAll('_',' ')}</span></div>)}
      </div>
    </section>

    <section className="card notice"><strong>Evidence policy:</strong> normal raw video is intended to remain at the edge. Central review receives aggregate telemetry and minimal evidence for persistent exceptions. No current prototype compliance check requires individual identification.</section>
  </main>;
}

function Metric({label,value}:{label:string;value:string|number}){return <div className="metric"><span>{label}</span><strong>{value}</strong><small>Demo / prototype</small></div>}
function Result({label,value}:{label:string;value:string|number}){return <div><span>{label}</span><strong>{value}</strong></div>}
