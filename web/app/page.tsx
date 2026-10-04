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

const navItems = [
  {label:'Overview',href:'#overview',icon:'overview'},
  {label:'Attendance',href:'#attendance',icon:'attendance'},
  {label:'Practical work',href:'#practical-work',icon:'activity'},
  {label:'Infrastructure',href:'#infrastructure',icon:'infrastructure'},
  {label:'Cases',href:'#cases',icon:'cases'},
  {label:'Evidence',href:'#evidence-policy',icon:'evidence'},
] as const;

export default function Page() {
  const [data,setData]=useState<Dashboard|null>(null);
  const [infra,setInfra]=useState<InfraItem[]>([]);
  const [result,setResult]=useState<any>(null);
  const [infraResult,setInfraResult]=useState<any>(null);
  const [practicalResult,setPracticalResult]=useState<any>(null);
  const [busy,setBusy]=useState(false);
  const [infraBusy,setInfraBusy]=useState(false);
  const [practicalBusy,setPracticalBusy]=useState(false);
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

  async function submitPractical(e:FormEvent<HTMLFormElement>){
    e.preventDefault(); setPracticalBusy(true); setError(''); setPracticalResult(null);
    try{
      const incoming=new FormData(e.currentTarget);
      const video=incoming.get('practical_file');
      const zonesFile=incoming.get('zones_file');
      if(!(video instanceof File)){throw new Error('Choose a practical-work CCTV video');}
      if(!(zonesFile instanceof File)){throw new Error('Choose a work-zone JSON file');}

      const body=new FormData();
      body.append('file',video);
      body.append('zones_json',await zonesFile.text());

      for(const key of ['authorization','zone_profile','centre_id','batch_id','camera_id']){
        const value=incoming.get(key);
        if(value!==null) body.append(key,String(value));
      }

      const r=await fetch(`${API}/api/process-practical-activity`,{method:'POST',body});
      const payload=await r.json();
      if(!r.ok) throw new Error(payload.detail||'Practical-work analysis failed');
      setPracticalResult(payload);
      await refresh();
    }catch(err:any){
      setError(err.message||String(err));
    }finally{
      setPracticalBusy(false);
    }
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
  const cameraHealthy = (data?.camera_issues ?? 0) === 0;

  return <div className="appShell">
    <aside className="sidebar" aria-label="Primary navigation">
      <div>
        <div className="brand">
          <div className="brandMark" aria-hidden="true"><Icon name="shield" /></div>
          <div>
            <strong>KaushalWatch Command Centre</strong>
            <span>Visual compliance operations</span>
          </div>
        </div>

        <div className="siteSwitcher">
          <span className="siteLabel">Active workspace</span>
          <div className="siteRow">
            <span className="siteDot" aria-hidden="true"></span>
            <div><strong>DEMO-KA-104</strong><small>Training centre</small></div>
            <span className="chevron">⌄</span>
          </div>
        </div>

        <nav className="navList" aria-label="Primary navigation">
          {navItems.map(item=><a href={item.href} key={item.label}>
            <Icon name={item.icon} />
            <span>{item.label}</span>
          </a>)}
        </nav>
      </div>

      <div className="sidebarFoot">
        <div className="privacyGlyph"><Icon name="privacy" /></div>
        <div><strong>Privacy-first</strong><span>Track position, not identity</span></div>
      </div>
    </aside>

    <main className="workspace">
      <div className="topbar">
        <div className="breadcrumbs"><span>Training Centres</span><b>/</b><strong>DEMO-KA-104</strong></div>
        <div className="topActions">
          <span className="statusPill neutral"><span className="statusPulse"></span>Edge telemetry</span>
          <span className="statusPill review"><Icon name="human" />Human review required</span>
        </div>
      </div>

      <div className="content">
        <div className="prototype"><Icon name="info" />PROTOTYPE — SIMULATED OPERATIONAL DATA</div>

        <section className="pageIntro" id="overview">
          <div>
            <p className="eyebrow">VISUAL COMPLIANCE OPERATIONS</p>
            <h1>Centre overview</h1>
            <p className="muted">Evidence-backed exceptions across attendance, infrastructure and camera trust.</p>
          </div>
          <div className="contextBlock">
            <span>Job role</span>
            <strong>Construction Electrician - LV</strong>
            <small>CON/Q0603 · demo quantities</small>
          </div>
        </section>

        <section className="metrics" aria-label="Operational summary">
          <Metric label="Demo centres" value={data?.centres_monitored??'—'} icon="site" />
          <Metric label="Open cases" value={data?.open_cases??'—'} icon="cases" emphasize={(data?.open_cases??0)>0} />
          <Metric label="Camera issues" value={data?.camera_issues??'—'} icon="camera" emphasize={(data?.camera_issues??0)>0} />
          <Metric label="Synced edge events" value={data?.synced_edge_events??'—'} icon="sync" />
          <Metric label="Privacy mode" value="Anonymous" icon="privacy" />
        </section>

        {error&&<div className="error globalError"><Icon name="alert" />{error}</div>}

        <section className="operationsGrid">
          <div className="mainColumn">
            <section className="panel" id="attendance">
              <div className="panelHead">
                <div>
                  <div className="titleLine"><span className="panelIcon"><Icon name="attendance" /></span><h2>Attendance verification</h2></div>
                  <p>Compare single-camera visual occupancy against simulated reported attendance.</p>
                </div>
                <span className="tag live"><span className="statusPulse"></span>LIVE PIPELINE</span>
              </div>

              <form className="operationForm" onSubmit={submit}>
                <label className="fileField">
                  <span>Demo CCTV video</span>
                  <input name="file" type="file" accept="video/*,.avi" required />
                </label>
                <div className="two">
                  <label>Reported attendance<input name="reported_attendance" type="number" defaultValue="12" min="0" required /></label>
                  <label>Centre ID<input name="centre_id" defaultValue="DEMO-KA-104" /></label>
                </div>
                <label>Batch ID<input name="batch_id" defaultValue="ELEC-DEMO-01" /></label>
                <div className="formFooter">
                  <p><Icon name="privacy" />Anonymous positional tracking only</p>
                  <button disabled={busy}>{busy?'Analysing…':'Analyse video'}<span>→</span></button>
                </div>
              </form>

              {result&&<div className="result">
                <Result label="Reported" value={result.reported_attendance}/>
                <Result label="Visual occupancy" value={result.estimated_occupancy}/>
                <Result label="Mismatch" value={`${result.discrepancy_pct}%`}/>
                <Result label="Case" value={result.case?'Created':'No persistent case'}/>
              </div>}
            </section>

            <section className="panel" id="practical-work">
              <div className="panelHead">
                <div>
                  <div className="titleLine"><span className="panelIcon"><Icon name="activity" /></span><h2>Practical-work verification</h2></div>
                  <p>Confirm stable anonymous worker presence and sustained worker-centric motion inside configured work cells.</p>
                </div>
                <span className="tag live"><span className="statusPulse"></span>YOLO + TRACKING</span>
              </div>

              <form className="operationForm" onSubmit={submitPractical}>
                <label className="fileField">
                  <span>Practical-work CCTV video</span>
                  <input name="practical_file" type="file" accept="video/*,.avi,.mp4" required />
                </label>

                <label className="fileField">
                  <span>Work-zone configuration (.json)</span>
                  <input name="zones_file" type="file" accept=".json,application/json" required />
                </label>

                <div className="three">
                  <label>Authorization
                    <select name="authorization" defaultValue="unknown">
                      <option value="valid">Valid</option>
                      <option value="absent">Not found</option>
                      <option value="unknown">Unknown / review</option>
                    </select>
                  </label>
                  <label>Zone profile
                    <input name="zone_profile" placeholder="optional, e.g. authorized" />
                  </label>
                  <label>Camera ID
                    <input name="camera_id" defaultValue="LAB-CAM-03" />
                  </label>
                </div>

                <div className="two">
                  <label>Centre ID<input name="centre_id" defaultValue="DEMO-KA-104" /></label>
                  <label>Batch ID<input name="batch_id" defaultValue="ELEC-DEMO-01" /></label>
                </div>

                <div className="formFooter">
                  <p><Icon name="privacy" />No face recognition · authorization is external state</p>
                  <button disabled={practicalBusy}>{practicalBusy?'Analysing practical work…':'Analyse practical work'}<span>→</span></button>
                </div>
              </form>

              {practicalResult&&<div className="practicalResultWrap">
                <div className="result">
                  <Result label="Stable workers" value={practicalResult.peak_stable_workers}/>
                  <Result label="Active work cells" value={practicalResult.active_work_cells}/>
                  <Result label="Activity" value={`${Math.round((practicalResult.practical_activity_fraction||0)*100)}%`}/>
                  <Result label="Camera coverage" value={`${Math.round((practicalResult.trusted_frame_ratio||0)*100)}%`}/>
                </div>
                <div className={`decisionBanner ${String(practicalResult.decision||'').includes('unauthorized')?'danger':String(practicalResult.decision||'').includes('authorized_')?'success':'review'}`}>
                  <div>
                    <span>Decision</span>
                    <strong>{String(practicalResult.decision||'').replaceAll('_',' ')}</strong>
                  </div>
                  <div>
                    <span>Authorization</span>
                    <strong>{String(practicalResult.authorization||'unknown').replaceAll('_',' ')}</strong>
                  </div>
                  <div>
                    <span>Evidence</span>
                    <strong>{practicalResult.case?.evidence?.length?'Exception captured':'Edge-only / none'}</strong>
                  </div>
                </div>
                {!!practicalResult.work_cells?.length&&<div className="workCellGrid">
                  {practicalResult.work_cells.map((cell:any)=><div className="workCellCard" key={cell.zone_id}>
                    <div><strong>{cell.zone_id.replaceAll('_',' ')}</strong><span>{Math.round(cell.registered_worker_presence_fraction*100)}% stable presence</span></div>
                    <b>{Math.round(cell.activity_fraction*100)}% active</b>
                  </div>)}
                </div>}
              </div>}
            </section>

            <section className="panel posturePanel">
              <div className="panelHead compact">
                <div>
                  <div className="titleLine"><span className="panelIcon"><Icon name="health" /></span><h2>System posture</h2></div>
                  <p>Trust signals that govern whether visual conclusions may proceed.</p>
                </div>
              </div>
              <div className="postureRows">
                <PostureRow label="Camera trust" detail="Darkness, blur, freeze and scene-shift checks" state={cameraHealthy?'Nominal':'Attention'} tone={cameraHealthy?'good':'warn'} />
                <PostureRow label="Edge sync" detail="Aggregate telemetry and persistent exceptions only" state={`${data?.synced_edge_events??0} synced`} tone="neutral" />
                <PostureRow label="Identity handling" detail="No face recognition or cross-camera re-identification" state="Anonymous" tone="good" />
              </div>
            </section>
          </div>

          <section className="panel casePanel" id="cases">
            <div className="panelHead compact">
              <div>
                <div className="titleLine"><span className="panelIcon"><Icon name="cases" /></span><h2>Priority exceptions</h2></div>
                <p>Persistent cases surfaced for officer review.</p>
              </div>
              <span className="countBadge">{priority.length}</span>
            </div>

            <div className="caseList">
              {priority.length===0&&<div className="empty"><Icon name="check" /><strong>No demo cases yet</strong><span>Persistent exceptions will appear here.</span></div>}
              {priority.map(c=><article className="case" key={c.case_id}>
                <div className="caseTop">
                  <div className="caseIdentity"><span className={`dot ${c.severity}`}></span><div><strong>{c.centre_id}</strong><small>{c.case_id}</small></div></div>
                  <span className={`caseStatus ${c.status}`}>{c.status.replaceAll('_',' ')}</span>
                </div>
                <p>{c.summary}</p>
                <div className="caseMeta"><span>{c.case_type.replaceAll('_',' ')}</span>{c.evidence?.length?<span>{c.evidence.length} evidence</span>:null}</div>
                {c.details?.apparent_operability?.state&&<div className="caseDetail"><strong>Apparent operability</strong><span>{c.details.apparent_operability.state.replaceAll('_',' ')}</span></div>}
                <div className="caseLinks">
                  {c.evidence?.[0]&&<a className="evidenceLink" href={`${API}/evidence/${c.evidence[0].evidence_id}.jpg`} target="_blank" rel="noreferrer"><Icon name="image" />Open evidence</a>}
                  <a className="evidenceLink" href={`${API}/api/cases/${c.case_id}/evidence-pack`} target="_blank" rel="noreferrer"><Icon name="package" />Evidence pack</a>
                </div>
                {c.evidence?.[0]?.duplicate_of&&<div className="warning">Possible duplicate evidence of {c.evidence[0].duplicate_of}</div>}
                {!!c.review_history?.length&&<div className="auditHint">Audit trail · {c.review_history.length} officer action{c.review_history.length===1?'':'s'}</div>}
                <div className="actions">
                  <button className="ghost primaryGhost" onClick={()=>review(c.case_id,'under_review')}>Review</button>
                  <button className="ghost" onClick={()=>review(c.case_id,'virtual_verification')}>Virtual verify</button>
                  <button className="ghost" onClick={()=>review(c.case_id,'false_positive')}>False positive</button>
                  <button className="ghost" onClick={()=>review(c.case_id,'confirmed')}>Confirm</button>
                </div>
              </article>)}
            </div>
          </section>
        </section>

        <section className="panel infra" id="infrastructure">
          <div className="panelHead">
            <div>
              <div className="titleLine"><span className="panelIcon"><Icon name="infrastructure" /></span><h2>Visual Compliance Manifest</h2></div>
              <p>Construction Electrician - LV · Cached detections are a stage-safe fallback. Quantities below are demo configuration, not official sanctioned figures.</p>
            </div>
            <span className="tag">DEMO MANIFEST</span>
          </div>

          <div className="manifestLayout">
            <form className="infraUpload operationForm" onSubmit={submitInfrastructure}>
              <label className="fileField">Infrastructure demo video<input name="infra_file" type="file" accept="video/*,.avi" required /></label>
              <div className="three">
                <label>Centre ID<input name="centre_id" defaultValue="DEMO-KA-104" /></label>
                <label>Batch ID<input name="batch_id" defaultValue="ELEC-DEMO-01" /></label>
                <label>Camera ID<input name="camera_id" defaultValue="LAB-CAM-02" /></label>
              </div>
              <div className="roiBlock">
                <div className="roiCopy"><strong>Optional apparent-operability ROI</strong><span>Visual activity proxy only; this does not establish mechanical or electrical health.</span></div>
                <div className="roiInputs">
                  <label>x1<input aria-label="ROI x1" name="roi_x1" type="number" defaultValue="0" /></label>
                  <label>y1<input aria-label="ROI y1" name="roi_y1" type="number" defaultValue="20" /></label>
                  <label>x2<input aria-label="ROI x2" name="roi_x2" type="number" defaultValue="220" /></label>
                  <label>y2<input aria-label="ROI y2" name="roi_y2" type="number" defaultValue="190" /></label>
                </div>
                <input type="hidden" name="operability_item_id" value="drill_machine" />
              </div>
              <div className="formFooter">
                <p><Icon name="evidence" />Persistent evidence only</p>
                <button disabled={infraBusy}>{infraBusy?'Analysing infrastructure…':'Analyse infrastructure evidence'}<span>→</span></button>
              </div>
            </form>

            <div className="manifestTableWrap">
              <div className="table">
                <div className="tr th"><span>Item</span><span>Required</span><span>Observed</span><span>State</span></div>
                {infra.map(x=><div className="tr" key={x.id}>
                  <span className="itemName">{x.label}</span>
                  <span>{x.required}</span>
                  <span>{x.observed??'Officer'}</span>
                  <span className={`state ${x.state.toLowerCase()}`}>{x.state.replaceAll('_',' ')}</span>
                </div>)}
              </div>
            </div>
          </div>

          {infraResult?.created&&<div className="result infraResult">
            <Result label="Case" value={infraResult.case.case_id}/>
            <Result label="Type" value="Infrastructure"/>
            <Result label="Evidence" value={infraResult.case.evidence?.length?'Captured':'Missing'}/>
            <Result label="Operability" value={infraResult.case.details?.apparent_operability?.state?.replaceAll('_',' ')||'Not evaluated'}/>
          </div>}
        </section>

        <section className="evidenceNotice" id="evidence-policy">
          <span className="noticeIcon"><Icon name="privacy" /></span>
          <div><strong>Evidence policy</strong><p>Normal raw video is intended to remain at the edge. Central review receives aggregate telemetry and minimal evidence for persistent exceptions. No current prototype compliance check requires individual identification.</p></div>
        </section>
      </div>
    </main>
  </div>;
}

function Metric({label,value,icon,emphasize=false}:{label:string;value:string|number;icon:string;emphasize?:boolean}){
  return <div className={`metric ${emphasize?'metricAttention':''}`}>
    <span className="metricIcon"><Icon name={icon} /></span>
    <div><span>{label}</span><strong>{value}</strong><small>Demo / prototype</small></div>
  </div>
}

function Result({label,value}:{label:string;value:string|number}){
  return <div><span>{label}</span><strong>{value}</strong></div>
}

function PostureRow({label,detail,state,tone}:{label:string;detail:string;state:string;tone:'good'|'warn'|'neutral'}){
  return <div className="postureRow">
    <div><strong>{label}</strong><span>{detail}</span></div>
    <span className={`postureState ${tone}`}><i></i>{state}</span>
  </div>
}

function Icon({name}:{name:string}){
  const common={width:18,height:18,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.8,strokeLinecap:'round' as const,strokeLinejoin:'round' as const,'aria-hidden':true};
  if(name==='overview') return <svg {...common}><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>;
  if(name==='attendance'||name==='human') return <svg {...common}><circle cx="12" cy="8" r="3"/><path d="M5.5 20a6.5 6.5 0 0 1 13 0"/></svg>;
  if(name==='activity') return <svg {...common}><path d="M4 17V7M8 20V4M12 16V8M16 19V5M20 14v-4"/><path d="M3 12h18"/></svg>;
  if(name==='infrastructure') return <svg {...common}><path d="M4 20V7l8-4 8 4v13"/><path d="M8 20v-5h8v5M8 9h.01M12 9h.01M16 9h.01"/></svg>;
  if(name==='cases'||name==='alert') return <svg {...common}><path d="M12 3 2.8 19h18.4L12 3Z"/><path d="M12 9v4M12 17h.01"/></svg>;
  if(name==='evidence'||name==='package') return <svg {...common}><path d="M4 7.5 12 3l8 4.5V17l-8 4-8-4V7.5Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></svg>;
  if(name==='shield'||name==='privacy') return <svg {...common}><path d="M12 3 5 6v5c0 4.5 2.8 8.1 7 10 4.2-1.9 7-5.5 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-4"/></svg>;
  if(name==='site') return <svg {...common}><path d="M4 21h16M6 21V5h12v16M9 9h2M13 9h2M9 13h2M13 13h2"/></svg>;
  if(name==='camera') return <svg {...common}><rect x="3" y="6" width="14" height="12" rx="2"/><path d="m17 10 4-2v8l-4-2"/><circle cx="10" cy="12" r="2.5"/></svg>;
  if(name==='sync') return <svg {...common}><path d="M20 7h-5V2M4 17h5v5"/><path d="M19 12a7 7 0 0 0-12-5l-2 2M5 12a7 7 0 0 0 12 5l2-2"/></svg>;
  if(name==='health') return <svg {...common}><path d="M3 12h4l2-5 4 10 2-5h6"/></svg>;
  if(name==='image') return <svg {...common}><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 15-4-4L5 20"/></svg>;
  if(name==='check') return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/></svg>;
  if(name==='info') return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>;
  return <svg {...common}><circle cx="12" cy="12" r="8"/></svg>;
}
