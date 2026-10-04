'use client';

import { ChangeEvent, FormEvent, ReactNode, useEffect, useMemo, useState } from 'react';

type ViewKey = 'overview'|'attendance'|'practical'|'infrastructure'|'cases'|'evidence';
type CaseStatus = 'open'|'under_review'|'confirmed'|'false_positive'|'virtual_verification'|'resolved';

type Case = {
  case_id:string;
  centre_id:string;
  batch_id:string;
  case_type:string;
  severity:string;
  summary:string;
  status:CaseStatus;
  discrepancy_pct?:number;
  reported_attendance?:number;
  visual_occupancy?:number;
  persistence_ratio?:number;
  evidence?:{evidence_id:string; duplicate_of?:string|null; sha256:string}[];
  details?:{apparent_operability?:{state?:string;activity_score?:number};[key:string]:any};
  review_history?:{timestamp:string;from_status:string;to_status:string;note?:string|null;actor?:string|null}[];
  created_at?:string;
};

type Dashboard = {
  banner:string;
  centres_monitored:number;
  open_cases:number;
  global_open_cases?:number;
  resolved_cases?:number;
  scope?:{
    centre_id?:string|null;
    batch_id?:string|null;
    is_filtered?:boolean;
  };
  camera_issues:number;
  synced_edge_events:number;
  edge_sync_state?:string;
  pending_cases?:Case[];
  resolved_case_history?:Case[];
  cases:Case[];
};

type WorkflowStepState = 'pending'|'passed'|'attention'|'blocked';

type WorkflowProgress = {
  attendance:WorkflowStepState;
  practical:WorkflowStepState;
  infrastructure:WorkflowStepState;
};

type RuntimeReadiness = {
  attendance?:{
    ready:boolean;
    backend:string;
    mode:string;
    message:string;
  };
  practical_work?:{
    ready:boolean;
    backend?:string;
    message:string;
  };
  infrastructure?:{
    ready:boolean;
    mode:string;
    message:string;
  };
};

type InfraItem = {
  id:string;
  label:string;
  required:number;
  observed:number|null;
  state:string;
  confidence:number|null;
  verification_tier?:string;
  presence_method?:string;
};

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const navItems:{key:ViewKey;label:string;description:string;icon:string}[] = [
  {key:'overview',label:'Overview',description:'Operational picture',icon:'overview'},
  {key:'attendance',label:'Attendance',description:'Stable occupancy',icon:'attendance'},
  {key:'practical',label:'Practical work',description:'Work-cell activity',icon:'activity'},
  {key:'infrastructure',label:'Infrastructure',description:'Visual manifest',icon:'infrastructure'},
  {key:'cases',label:'Review queue',description:'Human decisions',icon:'cases'},
  {key:'evidence',label:'Evidence policy',description:'Privacy & integrity',icon:'evidence'},
];

export default function Page(){
  const [activeView,setActiveView]=useState<ViewKey>('infrastructure');
  const [data,setData]=useState<Dashboard|null>(null);
  const [infra,setInfra]=useState<InfraItem[]>([]);
  const [attendanceResult,setAttendanceResult]=useState<any>(null);
  const [practicalResult,setPracticalResult]=useState<any>(null);
  const [infraResult,setInfraResult]=useState<any>(null);
  const [attendanceBusy,setAttendanceBusy]=useState(false);
  const [practicalBusy,setPracticalBusy]=useState(false);
  const [infraBusy,setInfraBusy]=useState(false);
  const [error,setError]=useState('');
  const [attendancePreview,setAttendancePreview]=useState('');
  const [practicalPreview,setPracticalPreview]=useState('');
  const [infraPreview,setInfraPreview]=useState('');
  const [practicalAuth,setPracticalAuth]=useState<'valid'|'absent'|'unknown'>('valid');
  const [practicalProfile,setPracticalProfile]=useState<'authorized'|'unauthorized'|'default'>('authorized');
  const [attendanceReported,setAttendanceReported]=useState(3);
  const [centreId,setCentreId]=useState('DEMO-KA-104');
  const [batchId,setBatchId]=useState('ELEC-DEMO-01');
  const [workflowProgress,setWorkflowProgress]=useState<WorkflowProgress>({
    attendance:'pending',
    practical:'pending',
    infrastructure:'pending',
  });
  const [runtimeReadiness,setRuntimeReadiness]=useState<RuntimeReadiness|null>(null);
  const readyEngineCount=[
    runtimeReadiness?.attendance?.ready,
    runtimeReadiness?.practical_work?.ready,
    runtimeReadiness?.infrastructure?.ready,
  ].filter(Boolean).length;

  const refresh=async()=>{
    const dashboardQuery=new URLSearchParams({
      centre_id:centreId,
      batch_id:batchId,
    });
    const [dashboardResponse,infraResponse,readinessResponse]=await Promise.all([
      fetch(`${API}/api/dashboard?${dashboardQuery.toString()}`,{cache:'no-store'}),
      fetch(`${API}/api/demo/infrastructure`,{cache:'no-store'}),
      fetch(`${API}/api/runtime-readiness`,{cache:'no-store'}),
    ]);
    if(!dashboardResponse.ok) throw new Error('Command-centre API is unavailable');
    setData(await dashboardResponse.json());
    if(infraResponse.ok){
      const body=await infraResponse.json();
      setInfra(body.items||[]);
    }
    if(readinessResponse.ok){
      setRuntimeReadiness(await readinessResponse.json());
    }
  };

  useEffect(()=>{
    const handle=window.setTimeout(()=>{
      refresh().catch(err=>setError(String(err.message||err)));
    },200);
    return ()=>window.clearTimeout(handle);
  },[centreId,batchId]);
  const progressStorageKey=`kaushalwatch-centre-progress:${centreId}:${batchId}`;

  useEffect(()=>{
    setAttendanceResult(null);
    setPracticalResult(null);
    setInfraResult(null);
    const pending:WorkflowProgress={
      attendance:'pending',
      practical:'pending',
      infrastructure:'pending',
    };
    try{
      const saved=window.localStorage.getItem(progressStorageKey);
      if(!saved){
        setWorkflowProgress(pending);
        return;
      }
      const parsed=JSON.parse(saved);
      const normalize=(value:any):WorkflowStepState=>{
        if(value===true) return 'passed';
        if(['pending','passed','attention','blocked'].includes(value)) return value;
        return 'pending';
      };
      setWorkflowProgress({
        attendance:normalize(parsed.attendance),
        practical:normalize(parsed.practical),
        infrastructure:normalize(parsed.infrastructure),
      });
    }catch{
      setWorkflowProgress(pending);
    }
  },[progressStorageKey]);

  function markWorkflow(step:keyof WorkflowProgress,state:WorkflowStepState){
    setWorkflowProgress(current=>{
      const next={...current,[step]:state};
      try{window.localStorage.setItem(progressStorageKey,JSON.stringify(next));}catch{}
      return next;
    });
  }

  function resetWorkflow(){
    const next:WorkflowProgress={
      attendance:'pending',
      practical:'pending',
      infrastructure:'pending',
    };
    setWorkflowProgress(next);
    setAttendanceResult(null);
    setPracticalResult(null);
    setInfraResult(null);
    try{window.localStorage.setItem(progressStorageKey,JSON.stringify(next));}catch{}
  }

  const priority=useMemo(
    ()=>sortPriorityCases(
      data?.pending_cases
      || data?.cases?.filter(item=>['open','under_review','virtual_verification'].includes(item.status))
      || [],
    ),
    [data]
  );
  const history=useMemo(
    ()=>[...(data?.resolved_case_history||data?.cases?.filter(item=>!['open','under_review','virtual_verification'].includes(item.status))||[])].reverse(),
    [data]
  );
  function previewFile(
    event:ChangeEvent<HTMLInputElement>,
    setter:(value:string)=>void,
  ){
    const file=event.target.files?.[0];
    if(!file){setter('');return;}
    setter(URL.createObjectURL(file));
  }

  async function submitAttendance(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    setAttendanceBusy(true);
    setAttendanceResult(null);
    setError('');
    try{
      const response=await fetch(`${API}/api/process-video`,{
        method:'POST',
        body:new FormData(event.currentTarget),
      });
      const body=await response.json();
      if(!response.ok) throw new Error(body.detail||'Attendance analysis failed');
      setAttendanceResult(body);
      markWorkflow(
        'attendance',
        body.decision==='detector_unavailable'
          ? 'blocked'
          : body.decision==='compliant'
            ? 'passed'
            : 'attention',
      );
      await refresh();
    }catch(err:any){
      setError(err.message||String(err));
    }finally{
      setAttendanceBusy(false);
    }
  }

  async function submitPractical(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    setPracticalBusy(true);
    setPracticalResult(null);
    setError('');
    try{
      const incoming=new FormData(event.currentTarget);
      const video=incoming.get('practical_file');
      const zonesFile=incoming.get('zones_file');
      if(!(video instanceof File)) throw new Error('Choose a practical-work CCTV video');

      const body=new FormData();
      body.append('file',video);
      if(zonesFile instanceof File && zonesFile.size>0){
        body.append('zones_json',await zonesFile.text());
      }
      body.append('authorization',practicalAuth);

      for(const key of ['zone_profile','centre_id','batch_id','camera_id']){
        const value=incoming.get(key);
        if(value!==null) body.append(key,String(value));
      }

      const response=await fetch(`${API}/api/process-practical-activity`,{
        method:'POST',
        body,
      });
      const payload=await response.json();
      if(!response.ok) throw new Error(payload.detail||'Practical-work analysis failed');
      setPracticalResult(payload);
      markWorkflow(
        'practical',
        payload.decision==='camera_evidence_insufficient'
          ? 'blocked'
          : payload.case
            ? 'attention'
            : 'passed',
      );
      await refresh();
    }catch(err:any){
      setError(err.message||String(err));
    }finally{
      setPracticalBusy(false);
    }
  }

  async function submitInfrastructure(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    setInfraBusy(true);
    setInfraResult(null);
    setError('');
    try{
      const incoming=new FormData(event.currentTarget);
      const video=incoming.get('infra_file');
      if(!(video instanceof File)) throw new Error('Choose an infrastructure demo video');

      const body=new FormData();
      body.append('file',video);
      for(const key of ['centre_id','batch_id','camera_id','demo_profile','operability_item_id','roi_x1','roi_y1','roi_x2','roi_y2']){
        const value=incoming.get(key);
        if(value!==null&&String(value).trim()!=='') body.append(key,String(value));
      }

      const response=await fetch(`${API}/api/process-infrastructure-video`,{
        method:'POST',
        body,
      });
      const payload=await response.json();
      if(!response.ok) throw new Error(payload.detail||'Infrastructure analysis failed');
      setInfraResult(payload);
      markWorkflow('infrastructure',payload.created?'attention':'passed');
      await refresh();
    }catch(err:any){
      setError(err.message||String(err));
    }finally{
      setInfraBusy(false);
    }
  }

  async function review(caseId:string,action:CaseStatus,note?:string){
    setError('');
    const response=await fetch(`${API}/api/cases/${caseId}/review`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action,note:note?.trim()||null}),
    });
    if(!response.ok){
      const payload=await response.json().catch(()=>null);
      setError(payload?.detail||'Could not update the case');
      return;
    }
    await refresh();
  }

  return <div className="shell">
    <aside className="sidebar">
      <div>
        <div className="brand">
          <div className="brandMark"><Icon name="shield"/></div>
          <div>
            <strong>KaushalWatch</strong>
            <span>Visual compliance command centre</span>
          </div>
        </div>

        <div className="workspaceCard">
          <span className="workspaceLabel">Active training centre</span>
          <div className="workspaceRow">
            <span className="liveDot"></span>
            <div>
              <strong>{centreId}</strong>
              <small>{batchId} · demonstration workspace</small>
            </div>
          </div>
        </div>

        <nav className="nav" aria-label="Primary navigation">
          {navItems.map(item=><button
            key={item.key}
            className={activeView===item.key?'navItem active':'navItem'}
            onClick={()=>setActiveView(item.key)}
            type="button"
          >
            <span className="navIcon"><Icon name={item.icon}/></span>
            <span className="navText"><strong>{item.label}</strong><small>{item.description}</small></span>
            <span className="navArrow">›</span>
          </button>)}
        </nav>
      </div>

      <div className="sidebarFooter">
        <div className="privacyIcon"><Icon name="privacy"/></div>
        <div><strong>Anonymous by design</strong><span>No face recognition or cross-camera identity</span></div>
      </div>
    </aside>

    <main className="main">
      <header className="topbar">
        <div>
          <span className="topEyebrow">KAUSHALWATCH / {centreId} / {batchId}</span>
          <strong>{navItems.find(item=>item.key===activeView)?.label}</strong>
        </div>
        <div className="topStatus">
          <span className={readyEngineCount===3?'healthChip good':'healthChip warn'}>
            <i></i>
            Verification runtime {runtimeReadiness?`${readyEngineCount}/3 ready`:'checking…'}
          </span>
          <span className="healthChip"><Icon name="human"/>Human review enforced</span>
        </div>
      </header>

      <div className="page">
        <ContextBar
          centreId={centreId}
          setCentreId={setCentreId}
          batchId={batchId}
          setBatchId={setBatchId}
          scopedPending={data?.open_cases??0}
          globalPending={data?.global_open_cases??data?.open_cases??0}
        />
        <CentreProgress
          progress={workflowProgress}
          activeView={activeView}
          onOpen={setActiveView}
          onReset={resetWorkflow}
        />
        <CentreOutcome progress={workflowProgress} onOpen={setActiveView}/>
        {error&&<div className="errorBanner"><Icon name="alert"/><span>{error}</span></div>}

        {activeView==='overview'&&<Overview
          data={data}
          priority={priority}
          onOpen={setActiveView}
        />}

        {activeView==='attendance'&&<AttendanceView
          result={attendanceResult}
          busy={attendanceBusy}
          preview={attendancePreview}
          reported={attendanceReported}
          setReported={setAttendanceReported}
          centreId={centreId}
          batchId={batchId}
          onPreview={(e)=>previewFile(e,setAttendancePreview)}
          onSubmit={submitAttendance}
        />}

        {activeView==='practical'&&<PracticalView
          result={practicalResult}
          busy={practicalBusy}
          preview={practicalPreview}
          auth={practicalAuth}
          setAuth={setPracticalAuth}
          profile={practicalProfile}
          setProfile={setPracticalProfile}
          readiness={runtimeReadiness?.practical_work}
          centreId={centreId}
          batchId={batchId}
          onPreview={(e)=>previewFile(e,setPracticalPreview)}
          onSubmit={submitPractical}
        />}

        {activeView==='infrastructure'&&<InfrastructureView
          infra={infra}
          result={infraResult}
          busy={infraBusy}
          preview={infraPreview}
          readiness={runtimeReadiness?.infrastructure}
          centreId={centreId}
          batchId={batchId}
          onPreview={(e)=>previewFile(e,setInfraPreview)}
          onSubmit={submitInfrastructure}
        />}

        {activeView==='cases'&&<CasesView
          cases={priority}
          history={history}
          review={review}
          centreId={centreId}
          batchId={batchId}
        />}

        {activeView==='evidence'&&<EvidenceView/>}
      </div>
    </main>
  </div>;
}

function Overview({
  data,
  priority,
  onOpen,
}:{
  data:Dashboard|null;
  priority:Case[];
  onOpen:(view:ViewKey)=>void;
}){
  return <>
    <section className="hero">
      <div>
        <span className="eyebrow">VISUAL COMPLIANCE OPERATIONS</span>
        <h1>See what is happening. Verify what was reported.</h1>
        <p>KaushalWatch turns fixed-camera evidence into privacy-preserving attendance, practical-work and infrastructure signals—then routes only persistent exceptions to a human reviewer.</p>
      </div>
      <div className="heroBadge">
        <span>Demo environment</span>
        <strong>Simulated operational records</strong>
        <small>Visual evidence is real where a CCTV file is supplied.</small>
      </div>
    </section>

    <section className="kpis">
      <Kpi icon="site" label="Demo centres loaded" value={data?.centres_monitored??'—'} note="Simulated command-centre dataset"/>
      <Kpi
        icon="cases"
        label="Pending in active batch"
        value={data?.open_cases??'—'}
        note={(data?.global_open_cases??data?.open_cases??0)>(data?.open_cases??0)
          ? `${data?.global_open_cases} pending across all demo contexts`
          : 'Scoped to the active centre / batch'}
        attention={(data?.open_cases??0)>0}
      />
      <Kpi
        icon="camera"
        label="Open camera-integrity cases"
        value={data==null?'—':`${data.camera_issues} open`}
        note="Case-derived status · not a live camera-health reading"
        attention={(data?.camera_issues??0)>0}
      />
      <Kpi
        icon="sync"
        label="Edge sync"
        value={data==null?'—':`${data.synced_edge_events} synced`}
        note={(data?.synced_edge_events??0)===0?'Idle · no pending events':'Synced · raw video not required'}
      />
    </section>

    <section className="sectionBlock">
      <div className="sectionHeading">
        <div><span className="eyebrow">VERIFICATION LANES</span><h2>Three checks, one review workflow</h2></div>
        <p>Each lane answers a different question. The product does not collapse every visual signal into a single “AI score”.</p>
      </div>

      <div className="laneGrid">
        <LaneCard
          icon="attendance"
          title="Attendance verification"
          question="Are enough people persistently present?"
          steps={['Camera trust','Stable anonymous tracks','Reported vs observed']}
          action="Open attendance"
          onClick={()=>onOpen('attendance')}
        />
        <LaneCard
          icon="activity"
          title="Practical-work verification"
          question="Is sustained work-cell activity actually visible?"
          steps={['Stable worker','Worker-centric motion','External authorization']}
          action="Open practical work"
          onClick={()=>onOpen('practical')}
          accent
        />
        <LaneCard
          icon="infrastructure"
          title="Infrastructure verification"
          question="Does the visible training setup match the manifest?"
          steps={['Manifest','Visual evidence','Human verification']}
          action="Open infrastructure"
          onClick={()=>onOpen('infrastructure')}
        />
      </div>
    </section>

    <section className="overviewSplit">
      <div className="card">
        <div className="cardHead">
          <div><span className="eyebrow">DECISION ARCHITECTURE</span><h2>How KaushalWatch reaches a case</h2></div>
        </div>
        <div className="decisionFlow">
          <FlowStep number="01" title="Trust the camera" detail="Darkness, freeze, blur and scene-shift checks can suspend inference."/>
          <FlowStep number="02" title="Require persistence" detail="Short-lived detections do not become attendance or activity evidence."/>
          <FlowStep number="03" title="Join external context" detail="Reported attendance and training authorization remain separate from vision."/>
          <FlowStep number="04" title="Escalate, don’t punish" detail="Exceptions become evidence-backed cases for a human officer."/>
        </div>
      </div>

      <div className="card">
        <div className="cardHead row">
          <div><span className="eyebrow">REVIEW QUEUE</span><h2>Latest exceptions</h2></div>
          <button className="textButton" type="button" onClick={()=>onOpen('cases')}>Open queue →</button>
        </div>
        <div className="compactCases">
          {priority.length===0&&<EmptyState title="No active exceptions" text="Persistent compliance exceptions will appear here."/>}
          {priority.slice(0,4).map(item=><CompactCase key={item.case_id} item={item}/>)}
        </div>
      </div>
    </section>
  </>;
}

function AttendanceView({
  result,busy,preview,reported,setReported,centreId,batchId,onPreview,onSubmit,
}:{
  result:any;
  busy:boolean;
  preview:string;
  reported:number;
  setReported:(value:number)=>void;
  centreId:string;
  batchId:string;
  onPreview:(event:ChangeEvent<HTMLInputElement>)=>void;
  onSubmit:(event:FormEvent<HTMLFormElement>)=>void;
}){
  const latest=result?.observations?.[result.observations.length-1];
  const attendanceDecision=String(result?.decision||'unknown');
  const attendanceTone:'good'|'warn'|'danger'=
    attendanceDecision==='compliant'
      ? 'good'
      : attendanceDecision==='attendance_exception'
        ? 'danger'
        : 'warn';
  const attendanceTitle=
    attendanceDecision==='compliant'
      ? 'Attendance evidence is within policy'
      : attendanceDecision==='attendance_exception'
        ? 'Persistent attendance discrepancy'
        : attendanceDecision==='camera_integrity_exception'
          ? 'Camera integrity prevents attendance verification'
          : 'Detector unavailable / fallback mode';
  const attendanceText=
    attendanceDecision==='compliant'
      ? 'Stable anonymous occupancy is consistent with the reported attendance under the configured persistence policy.'
      : result?.case?.summary
        || result?.detector_message
        || 'Attendance conclusions were withheld because the evidence pipeline could not produce an authoritative result.';
  return <>
    <ModuleHero
      eyebrow="ATTENDANCE / STABLE OCCUPANCY"
      title="Verify presence without identifying people."
      text="Short detections remain tentative. A track must persist before it can contribute to stable occupancy, and camera-integrity failures suspend attendance conclusions."
      badge="Frozen policy"
      policy={['1.0 s confirm','2.0 s register','0.8 s grace','5-sample smoothing']}
    />

    <PipelineStrip items={[
      ['1','Upload CCTV'],
      ['2','Camera trust'],
      ['3','Stable tracks'],
      ['4','Compare report'],
      ['5','Review exception'],
    ]}/>

    <section className="workbench">
      <form className="analysisCard" onSubmit={onSubmit}>
        <div className="analysisHead">
          <div><span className="stepNumber">01</span><div><h2>Evidence source</h2><p>Select a fixed-camera CCTV clip.</p></div></div>
          <span className="modeChip">Anonymous tracking</span>
        </div>

        <VideoDrop name="file" preview={preview} onPreview={onPreview}/>

        <div className="formSection">
          <div className="formSectionTitle"><span className="stepNumber">02</span><div><h3>Reported context</h3><p>Values supplied by the training-centre record.</p></div></div>
          <div className="scenarioPresetRow">
            <span>Quick demo</span>
            <button type="button" className={reported===3?'presetChip active':'presetChip'} onClick={()=>setReported(3)}>Matching report · 3</button>
            <button type="button" className={reported===12?'presetChip active attention':'presetChip attention'} onClick={()=>setReported(12)}>Mismatch report · 12</button>
          </div>
          <input type="hidden" name="centre_id" value={centreId}/>
          <input type="hidden" name="batch_id" value={batchId}/>
          <div className="formGrid two">
            <Field label="Reported attendance" help="Demo clean preset = 3. Use 12 to demonstrate a deliberate mismatch.">
              <input
                name="reported_attendance"
                type="number"
                min="0"
                value={reported}
                onChange={event=>setReported(Number(event.target.value))}
                required
              />
            </Field>
            <Field label="Camera ID"><input name="camera_id" defaultValue="LAB-CAM-01"/></Field>
          </div>
        </div>

        <SubmitBar
          busy={busy}
          label="Run attendance verification"
          busyLabel="Analysing stable occupancy…"
          note="Only mature anonymous tracks can affect attendance."
        />
      </form>

      <aside className="explainCard">
        <span className="eyebrow">WHAT THE SYSTEM WILL DO</span>
        <h2>Presence is not a single-frame count.</h2>
        <CheckRow title="Ignore transient detections" detail="Short false positives never become attendance-ready tracks."/>
        <CheckRow title="Bridge brief detector misses" detail="A bounded grace period avoids turning one person into repeated entries."/>
        <CheckRow title="Abstain on bad imagery" detail="Camera integrity takes precedence over attendance inference."/>
        <CheckRow title="Escalate persistent mismatch" detail="A case is created only after temporal evidence crosses policy thresholds."/>
      </aside>
    </section>

    {result&&<section className="resultSection">
      <DecisionHeader
        tone={attendanceTone}
        eyebrow="ATTENDANCE RESULT"
        title={attendanceTitle}
        text={attendanceText}
      />
      <div className="resultGrid">
        <ResultMetric label="Reported" value={result.reported_attendance}/>
        <ResultMetric label="Stable occupancy" value={result.detector_authoritative?(result.estimated_occupancy??'—'):'Unavailable'}/>
        <ResultMetric label="Mismatch" value={result.detector_authoritative&&result.discrepancy_pct!=null?`${result.discrepancy_pct}%`:'Suspended'}/>
        <ResultMetric label="Trusted samples" value={pct(result.trusted_sample_ratio)}/>
        <ResultMetric label="Mismatch persistence" value={result.detector_authoritative?pct(result.mismatch_persistence_ratio):'Suspended'}/>
        <ResultMetric label="Detector" value={result.detector_backend||'—'}/>
      </div>
      {result.detector_authoritative&&<OccupancyTimeline
        observations={result.observations||[]}
        reported={result.reported_attendance}
      />}
      <div className="analysisMetaBar">
        <span>Frames sampled <b>{result.frames_sampled??'—'}</b></span>
        <span>Sample interval <b>{result.sample_every_seconds??'—'}s</b></span>
        <span>Latest raw detections <b>{latest?.raw_count??'—'}</b></span>
        <span>Detector failures <b>{result.detector_failures??0}</b></span>
      </div>
      {!result.detector_authoritative&&<div className="detectorNotice">
        <Icon name="alert"/>
        <div><strong>Attendance decision withheld</strong><span>Fallback detector counts are diagnostic only and are never presented as real occupancy.</span></div>
      </div>}
    </section>}
  </>;
}

function PracticalView({
  result,busy,preview,auth,setAuth,profile,setProfile,readiness,centreId,batchId,onPreview,onSubmit,
}:{
  result:any;
  busy:boolean;
  preview:string;
  auth:'valid'|'absent'|'unknown';
  setAuth:(value:'valid'|'absent'|'unknown')=>void;
  profile:'authorized'|'unauthorized'|'default';
  setProfile:(value:'authorized'|'unauthorized'|'default')=>void;
  readiness?:RuntimeReadiness['practical_work'];
  centreId:string;
  batchId:string;
  onPreview:(event:ChangeEvent<HTMLInputElement>)=>void;
  onSubmit:(event:FormEvent<HTMLFormElement>)=>void;
}){
  const decision=String(result?.decision||'');
  const tone:'good'|'warn'|'danger'=
    decision==='authorized_practical_activity'
      ? 'good'
      : decision==='unauthorized_practical_activity'
        ? 'danger'
        : 'warn';
  const practicalTitle=
    decision==='authorized_practical_activity'
      ? 'Authorized practical activity observed'
      : decision==='unauthorized_practical_activity'
        ? 'Practical activity without matching authorization'
        : decision==='authorization_review_required'
          ? 'Practical activity needs authorization review'
          : decision==='camera_evidence_insufficient'
            ? 'Camera evidence is insufficient'
            : decision==='no_persistent_practical_activity'
              ? 'No persistent practical-work activity observed'
              : 'Practical-work result';
  const practicalText=
    decision==='authorized_practical_activity'
      ? 'Persistent work-cell activity was observed and a valid external authorization was supplied. No compliance exception is created.'
      : decision==='unauthorized_practical_activity'
        ? 'Persistent work-cell activity was observed without a supplied matching authorization. A human-review case was created.'
        : decision==='authorization_review_required'
          ? 'Persistent work-cell activity was observed, but authorization state is unknown. The case requires officer verification.'
          : decision==='camera_evidence_insufficient'
            ? 'The camera-trust gate suspended the practical-work conclusion. Review the camera-integrity evidence before interpreting activity.'
            : decision==='no_persistent_practical_activity'
              ? 'No configured work cell crossed the sustained worker-motion threshold during trusted imagery. No authorization conclusion is made from absence alone.'
              : 'The result requires officer verification before any compliance action.';

  return <>
    <ModuleHero
      eyebrow="PRACTICAL WORK / WORK-CELL ACTIVITY"
      title="Separate visible activity from authorization."
      text="Vision establishes stable anonymous worker presence and sustained worker-centric motion. Training authorization is supplied separately and is never inferred from appearance."
      badge="Frozen policy"
      policy={['2.0 s mature track','1.0 s motion window','60% positive','2% motion threshold']}
    />

    <PipelineStrip items={[
      ['1','Upload CCTV'],
      ['2','Stable worker'],
      ['3','Work-cell motion'],
      ['4','External authorization'],
      ['5','Review exception'],
    ]}/>

    {readiness&&!readiness.ready&&<ReadinessNotice
      title="Practical-work runtime unavailable"
      text={readiness.message}
      tone="warn"
    />}

    <section className="workbench">
      <form className="analysisCard" onSubmit={onSubmit}>
        <div className="analysisHead">
          <div><span className="stepNumber">01</span><div><h2>Visual evidence</h2><p>Use a fixed-camera clip and matching work-zone configuration.</p></div></div>
          <span className="modeChip">Worker-centric motion</span>
        </div>

        <VideoDrop name="practical_file" preview={preview} onPreview={onPreview}/>

        <div className="filePair">
          <label className="fileBox">
            <span className="fileIcon"><Icon name="zones"/></span>
            <span><strong>Work-zone JSON · optional</strong><small>Override the bundled demo profile only when needed</small></span>
            <input name="zones_file" type="file" accept=".json,application/json"/>
          </label>
          <Field label="Bundled zone profile" help="Works without uploading JSON. Same-camera geometry auto-scales if the clip resolution changes.">
            <select name="zone_profile" value={profile} onChange={event=>setProfile(event.target.value as 'authorized'|'unauthorized'|'default')}>
              <option value="authorized">Authorized demo layout</option>
              <option value="unauthorized">Unauthorized demo layout</option>
              <option value="default">Default demo layout</option>
            </select>
          </Field>
        </div>

        <div className="formSection">
          <div className="formSectionTitle"><span className="stepNumber">02</span><div><h3>External authorization</h3><p>This state comes from the training schedule or work order—not the camera.</p></div></div>
          <div className="scenarioPresetRow">
            <span>Quick demo</span>
            <button type="button" className={profile==='authorized'&&auth==='valid'?'presetChip active':'presetChip'} onClick={()=>{setProfile('authorized');setAuth('valid');}}>Authorized activity</button>
            <button type="button" className={profile==='unauthorized'&&auth==='absent'?'presetChip attention active':'presetChip attention'} onClick={()=>{setProfile('unauthorized');setAuth('absent');}}>Unauthorized alert</button>
            <button type="button" className={auth==='unknown'?'presetChip active':'presetChip'} onClick={()=>{setProfile('authorized');setAuth('unknown');}}>Needs review</button>
          </div>
          <div className="authSelector">
            <AuthChoice active={auth==='valid'} tone="good" title="Valid" detail="Matching training/work authorization exists" onClick={()=>setAuth('valid')}/>
            <AuthChoice active={auth==='absent'} tone="danger" title="Not found" detail="No matching authorization was supplied" onClick={()=>setAuth('absent')}/>
            <AuthChoice active={auth==='unknown'} tone="warn" title="Unknown" detail="Route activity for officer verification" onClick={()=>setAuth('unknown')}/>
          </div>
        </div>

        <input type="hidden" name="centre_id" value={centreId}/>
        <input type="hidden" name="batch_id" value={batchId}/>
        <div className="formGrid one">
          <Field label="Camera ID"><input name="camera_id" defaultValue="LAB-CAM-03"/></Field>
        </div>

        <SubmitBar
          busy={busy}
          disabled={readiness?.ready===false}
          label="Run practical-work verification"
          busyLabel="Analysing work-cell activity…"
          note={readiness?.ready===false
            ? 'Install the YOLO demo runtime before running this checkpoint.'
            : 'No face recognition. Activity is a visual proxy, not task recognition.'}
        />
      </form>

      <aside className="explainCard practicalExplain">
        <span className="eyebrow">WHAT COUNTS AS EVIDENCE</span>
        <h2>Standing in a rectangle is not enough.</h2>
        <SignalRow label="Stable worker" state="Required" detail="Track must survive the attendance maturity gate."/>
        <SignalRow label="Work-cell association" state="Required" detail="Visible worker must be assigned to a configured cell."/>
        <SignalRow label="Worker motion" state="Required" detail="Motion is measured around visible registered workers—not the whole ROI."/>
        <SignalRow label="Authorization" state="External" detail="Joined after visual activity is established."/>
        <div className="explainNote"><Icon name="info"/>The system can say “persistent visual practical-work activity”; it cannot infer exact skill quality or authorization from pixels.</div>
      </aside>
    </section>

    {result&&<section className="resultSection">
      <DecisionHeader
        tone={tone}
        eyebrow="PRACTICAL-WORK RESULT"
        title={practicalTitle}
        text={practicalText}
      />

      {result.zone_scaled&&<div className="resultSourceBanner">
        <Icon name="zones"/>
        <div>
          <strong>Work-zone profile auto-scaled</strong>
          <span>Same camera geometry scaled from {result.zone_reference_width}×{result.zone_reference_height} to the uploaded video resolution.</span>
        </div>
      </div>}
      <div className="resultGrid">
        <ResultMetric label="Peak stable workers" value={result.peak_stable_workers}/>
        <ResultMetric label="Active work cells" value={result.active_work_cells}/>
        <ResultMetric label="Activity coverage" value={pct(result.practical_activity_fraction)}/>
        <ResultMetric label="Trusted imagery" value={pct(result.trusted_frame_ratio)}/>
        <ResultMetric label="First activity" value={result.first_practical_activity_time_sec==null?'—':`${result.first_practical_activity_time_sec}s`}/>
        <ResultMetric label="Evidence" value={result.case?.evidence?.length?'Captured':'No exception evidence'}/>
      </div>

      {!!result.work_cells?.length&&<div className="cellResults">
        <div className="subHead"><span className="eyebrow">WORK-CELL BREAKDOWN</span><h3>Where activity was actually sustained</h3></div>
        <div className="cellGrid">
          {result.work_cells.map((cell:any)=><WorkCellResult key={cell.zone_id} cell={cell}/>)}
        </div>
      </div>}
    </section>}
  </>;
}

function InfrastructureView({
  infra,result,busy,preview,readiness,centreId,batchId,onPreview,onSubmit,
}:{
  infra:InfraItem[];
  result:any;
  busy:boolean;
  preview:string;
  readiness?:RuntimeReadiness['infrastructure'];
  centreId:string;
  batchId:string;
  onPreview:(event:ChangeEvent<HTMLInputElement>)=>void;
  onSubmit:(event:FormEvent<HTMLFormElement>)=>void;
}){
  return <>
    <ModuleHero
      eyebrow="INFRASTRUCTURE / VISUAL MANIFEST"
      title="Turn visible training infrastructure into reviewable evidence."
      text="Compare a stage-safe visual manifest against observed equipment evidence. Quantities remain a demo configuration until an official sanctioned source is connected."
      badge="Stage-safe fallback"
      policy={['Temporal evidence','Cached detector adapter','Optional activity ROI','Human verification']}
    />

    <PipelineStrip items={[
      ['1','Upload CCTV'],
      ['2','Read manifest'],
      ['3','Compare evidence'],
      ['4','Flag discrepancy'],
      ['5','Human review'],
    ]}/>

    {readiness&&!readiness.ready&&<ReadinessNotice
      title="Infrastructure demo assets unavailable"
      text={readiness.message}
      tone="warn"
    />}

    <section className="workbench">
      <form className="analysisCard" onSubmit={onSubmit}>
        <div className="analysisHead">
          <div><span className="stepNumber">01</span><div><h2>Infrastructure evidence</h2><p>Select the CCTV clip to associate with this manifest check.</p></div></div>
          <span className="modeChip">Visual manifest</span>
        </div>

        <VideoDrop name="infra_file" preview={preview} onPreview={onPreview}/>

        <input type="hidden" name="centre_id" value={centreId}/>
        <input type="hidden" name="batch_id" value={batchId}/>
        <div className="formGrid two">
          <Field label="Demo evidence profile" help="Equipment counts below are demo telemetry, not live detections from the uploaded clip.">
            <select name="demo_profile" defaultValue="compliant">
              <option value="compliant">Compliant demo telemetry</option>
              <option value="discrepancy">Discrepancy demo telemetry</option>
            </select>
          </Field>
          <Field label="Camera ID · optional"><input name="camera_id" defaultValue="LAB-CAM-02"/></Field>
        </div>

        <div className="sourceDisclosure">
          <Icon name="info"/>
          <div>
            <strong>What comes from where</strong>
            <span>Manifest counts use stage-safe demo telemetry. The uploaded CCTV supplies the evidence frame and optional visual-motion proxy.</span>
          </div>
        </div>

        <details className="advancedOptions">
          <summary><span>Advanced · operability ROI</span><small>Optional visual-motion proxy</small></summary>
          <div className="advancedBody">
            <input type="hidden" name="operability_item_id" value="drill_machine"/>
            <p>Use only when the equipment region is known. This measures visible motion, not mechanical or electrical health.</p>
            <div className="formGrid four">
              <Field label="x1"><input name="roi_x1" type="number" defaultValue="0"/></Field>
              <Field label="y1"><input name="roi_y1" type="number" defaultValue="20"/></Field>
              <Field label="x2"><input name="roi_x2" type="number" defaultValue="220"/></Field>
              <Field label="y2"><input name="roi_y2" type="number" defaultValue="190"/></Field>
            </div>
          </div>
        </details>

        <SubmitBar
          busy={busy}
          disabled={readiness?.ready===false}
          label="Run infrastructure verification"
          busyLabel="Analysing visual manifest…"
          note={readiness?.ready===false
            ? 'Restore the manifest/cache before running this checkpoint.'
            : 'Only persistent visual discrepancies should become review cases.'}
        />
      </form>

      <aside className="manifestCard">
        <div className="cardHead"><div><span className="eyebrow">DEMO MANIFEST</span><h2>Construction Electrician - LV</h2><p>Configured quantities are demonstration data.</p></div></div>
        <div className="manifestList">
          {infra.map(item=><div className="manifestRow" key={item.id}>
            <div>
              <strong>{item.label}</strong>
              <small>{tierLabel(item.verification_tier)} · {item.state.replaceAll('_',' ')}</small>
            </div>
            <div className="manifestNumbers"><span>Required <b>{item.required}</b></span><span>Observed <b>{item.observed??'Officer'}</b></span></div>
          </div>)}
        </div>
      </aside>
    </section>

    {result&&<section className="resultSection">
      <DecisionHeader
        tone={result.created?'warn':'good'}
        eyebrow="INFRASTRUCTURE RESULT"
        title={result.created?'Visual manifest exception created':'No persistent visual manifest exception'}
        text={result.case?.summary||result.banner||'No persistent infrastructure exception was created.'}
      />
      <div className="resultSourceBanner">
        <Icon name="info"/>
        <div><strong>Observation source</strong><span>Equipment counts: stage-safe demo telemetry · CCTV: evidence / optional motion proxy</span></div>
      </div>
      <div className="resultGrid">
        <ResultMetric label="Outcome" value={result.created?'Exception':'Compliant'}/>
        <ResultMetric label="Profile" value={result.demo_profile||'—'}/>
        <ResultMetric label="Case" value={result.created?result.case.case_id:'No case created'}/>
        <ResultMetric label="Evidence" value={result.created?(result.case.evidence?.length?'Captured':'Missing'):'Not required'}/>
        <ResultMetric label="Items checked" value={result.items?.length??'—'}/>
        <ResultMetric label="Operability" value={result.created?(result.case.details?.apparent_operability?.state?.replaceAll('_',' ')||'Not evaluated'):'Not escalated'}/>
      </div>
      {!!result.items?.length&&<div className="cellResults">
        <div className="subHead"><span className="eyebrow">MANIFEST DECISIONS</span><h3>Camera-verifiable, partial and officer-only outcomes</h3></div>
        <div className="cellGrid">
          {result.items.map((item:any)=><div className={`cellResult state-${String(item.state).toLowerCase()}`} key={item.id}>
            <div className="cellResultHead">
              <div><strong>{item.label}</strong><span>{tierLabel(item.verification_tier)} · required {item.required} · observed {item.observed??'officer'}</span></div>
              <b>{String(item.state).replaceAll('_',' ')}</b>
            </div>
          </div>)}
        </div>
      </div>}
    </section>}
  </>;
}

function CasesView({
  cases,history,review,centreId,batchId,
}:{
  cases:Case[];
  history:Case[];
  review:(caseId:string,action:CaseStatus,note?:string)=>void;
  centreId:string;
  batchId:string;
}){
  return <>
    <ModuleHero
      eyebrow="HUMAN REVIEW"
      title="AI surfaces evidence. Officers make the decision."
      text={`Showing only cases for ${centreId} / ${batchId}. Pending exceptions stay in the priority queue; final decisions move into resolved history.`}
      badge={`${cases.length} pending`}
      policy={['Open evidence','Inspect hashes','Virtual verification','Officer decision']}
    />

    <section className="caseWorkspace">
      <div className="queueHeader">
        <div><span className="eyebrow">PRIORITY EXCEPTIONS</span><h2>Pending review · active batch only</h2></div>
        <span className="queueCount">{cases.length} pending</span>
      </div>

      {cases.length===0&&<EmptyState title="Priority queue clear" text="No pending cases require an officer decision."/>}

      <div className="caseGrid">
        {cases.map(item=><CaseCard key={item.case_id} item={item} review={review}/>)}
      </div>

      <div className="resolvedSection">
        <div className="queueHeader resolvedHead">
          <div><span className="eyebrow">RESOLVED / HISTORY</span><h2>Closed decisions</h2></div>
          <span className="queueCount">{history.length} archived</span>
        </div>
        {history.length===0
          ? <div className="historyEmpty">Confirmed and false-positive decisions will move here.</div>
          : <div className="caseGrid resolvedGrid">
              {history.map(item=><CaseCard key={item.case_id} item={item} review={review} resolved/>)}
            </div>
        }
      </div>
    </section>
  </>;
}

function EvidenceView(){
  return <>
    <ModuleHero
      eyebrow="PRIVACY / EVIDENCE INTEGRITY"
      title="Keep the evidence small, reviewable and attributable."
      text="Normal raw video is intended to remain at the edge. Central review receives aggregate telemetry and minimal evidence only when a persistent exception is created."
      badge="Privacy-first"
      policy={['Blur person regions','SHA-256','Perceptual duplicate check','No identity embeddings']}
    />

    <section className="evidenceGrid">
      <PolicyCard icon="privacy" title="Identity minimisation" text="Person detections are used for short-lived positional tracking. The current prototype does not create face embeddings or cross-camera identity."/>
      <PolicyCard icon="camera" title="Camera trust first" text="Darkness, blur, freeze and scene-shift checks can suspend downstream conclusions instead of fabricating confidence from poor imagery."/>
      <PolicyCard icon="evidence" title="Minimal exception evidence" text="Detected person regions are blurred before retention; when trustworthy localisation is unavailable, KaushalWatch falls back to a conservative full-frame privacy blur."/>
      <PolicyCard icon="package" title="Integrity metadata" text="Evidence is recorded with a SHA-256 hash and perceptual duplicate signal to support review and audit."/>
    </section>

    <section className="card architectureCard">
      <div className="cardHead"><div><span className="eyebrow">DATA PATH</span><h2>Edge-first evidence flow</h2></div></div>
      <div className="architectureFlow">
        <ArchitectureStep title="CCTV at centre" detail="Raw video source"/>
        <span className="flowArrow">→</span>
        <ArchitectureStep title="Edge analysis" detail="Trust, tracking, activity"/>
        <span className="flowArrow">→</span>
        <ArchitectureStep title="Persistent exception" detail="Evidence minimised"/>
        <span className="flowArrow">→</span>
        <ArchitectureStep title="Human review" detail="Officer decision"/>
      </div>
    </section>
  </>;
}

function ContextBar({
  centreId,setCentreId,batchId,setBatchId,scopedPending,globalPending,
}:{
  centreId:string;
  setCentreId:(value:string)=>void;
  batchId:string;
  setBatchId:(value:string)=>void;
  scopedPending:number;
  globalPending:number;
}){
  return <section className="contextBar" aria-label="Active verification context">
    <div className="contextIdentity">
      <span className="contextIcon"><Icon name="site"/></span>
      <div><span className="eyebrow">ACTIVE VERIFICATION CONTEXT</span><strong>{centreId} · {batchId}</strong></div>
    </div>
    <div className="contextFields">
      <Field label="Centre ID"><input value={centreId} onChange={event=>setCentreId(event.target.value)} aria-label="Active centre ID"/></Field>
      <Field label="Batch ID"><input value={batchId} onChange={event=>setBatchId(event.target.value)} aria-label="Active batch ID"/></Field>
    </div>
    <div className="contextQueue">
      <span>Scoped queue <b>{scopedPending}</b></span>
      <small>{globalPending===scopedPending?'All pending cases are in this context':`${globalPending} pending across all demo contexts`}</small>
    </div>
  </section>;
}

function CentreOutcome({
  progress,onOpen,
}:{
  progress:WorkflowProgress;
  onOpen:(view:ViewKey)=>void;
}){
  const values=Object.values(progress);
  if(values.some(value=>value==='pending')) return null;

  const blocked=values.filter(value=>value==='blocked').length;
  const attention=values.filter(value=>value==='attention').length;
  const passed=values.filter(value=>value==='passed').length;

  const tone=blocked>0?'blocked':attention>0?'attention':'passed';
  const title=blocked>0
    ? 'Centre verification incomplete'
    : attention>0
      ? 'Centre requires human review'
      : 'Centre checkpoints completed with no exception';
  const text=blocked>0
    ? `${blocked} checkpoint${blocked===1?'':'s'} could not produce an authoritative result. Resolve runtime/camera issues before final review.`
    : attention>0
      ? `${attention} checkpoint${attention===1?'':'s'} produced an exception; ${passed} completed without an exception.`
      : 'All three checkpoints completed without creating a review exception in this walkthrough.';

  return <section className={`centreOutcome ${tone}`}>
    <span className="centreOutcomeIcon"><Icon name={tone==='passed'?'check':'alert'}/></span>
    <div><span className="eyebrow">CENTRE-LEVEL OUTCOME</span><strong>{title}</strong><p>{text}</p></div>
    {attention>0&&<button type="button" onClick={()=>onOpen('cases')}>Open scoped review queue →</button>}
  </section>;
}

function CentreProgress({
  progress,activeView,onOpen,onReset,
}:{
  progress:WorkflowProgress;
  activeView:ViewKey;
  onOpen:(view:ViewKey)=>void;
  onReset:()=>void;
}){
  const steps:[
    keyof WorkflowProgress,
    ViewKey,
    string
  ][]=[
    ['attendance','attendance','Attendance'],
    ['practical','practical','Practical Work'],
    ['infrastructure','infrastructure','Infrastructure'],
  ];

  const meta:Record<WorkflowStepState,{label:string;symbol:string}> = {
    pending:{label:'Pending',symbol:'•'},
    passed:{label:'Completed · no exception',symbol:'✓'},
    attention:{label:'Exception · review',symbol:'!'},
    blocked:{label:'Could not verify',symbol:'×'},
  };

  return <section className="centreProgress" aria-label="Centre verification progress">
    <div className="centreProgressLead">
      <span className="eyebrow">CENTRE VERIFICATION</span>
      <strong>One centre · three checkpoints</strong>
      <button type="button" className="resetFlowButton" onClick={onReset}>Reset walkthrough</button>
    </div>
    <div className="centreProgressSteps">
      {steps.map(([key,view,label],index)=>{
        const state=progress[key];
        return <button
          key={key}
          type="button"
          className={`centreProgressStep ${state} ${activeView===view?'active':''}`}
          onClick={()=>onOpen(view)}
        >
          <span>{state==='pending'?index+1:meta[state].symbol}</span>
          <div><strong>{label}</strong><small>{meta[state].label}</small></div>
        </button>;
      })}
    </div>
  </section>;
}

function casePillar(caseType:string){
  if(caseType==='attendance_discrepancy') return {label:'Attendance discrepancy',icon:'attendance'};
  if(caseType.startsWith('practical_activity')) return {label:'Practical-work authorization',icon:'activity'};
  if(caseType==='infrastructure_compliance') return {label:'Infrastructure gap',icon:'infrastructure'};
  if(caseType==='camera_integrity') return {label:'Camera integrity',icon:'camera'};
  return {label:'Compliance review',icon:'cases'};
}

function ModuleHero({eyebrow,title,text,badge,policy}:{eyebrow:string;title:string;text:string;badge:string;policy:string[]}){
  return <section className="moduleHero">
    <div>
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      <p>{text}</p>
    </div>
    <div className="policyCard">
      <span>{badge}</span>
      <div>{policy.map(item=><b key={item}>{item}</b>)}</div>
    </div>
  </section>;
}

function PipelineStrip({items}:{items:[string,string][]}){
  return <section className="pipelineStrip">
    {items.map(([number,label],index)=><div className="pipelineItem" key={label}>
      <span>{number}</span><strong>{label}</strong>{index<items.length-1&&<i>→</i>}
    </div>)}
  </section>;
}

function VideoDrop({name,preview,onPreview}:{name:string;preview:string;onPreview:(event:ChangeEvent<HTMLInputElement>)=>void}){
  const [fileMeta,setFileMeta]=useState<{name:string;size:number}|null>(null);
  function handleChange(event:ChangeEvent<HTMLInputElement>){
    const file=event.target.files?.[0];
    setFileMeta(file?{name:file.name,size:file.size}:null);
    onPreview(event);
  }
  return <label className={preview?'videoDrop hasPreview':'videoDrop'}>
    {preview
      ? <video src={preview} controls muted playsInline/>
      : <div className="dropPlaceholder"><span className="dropIcon"><Icon name="video"/></span><strong>Choose CCTV clip</strong><small>MP4 / AVI / MOV / MKV · fixed camera recommended</small></div>
    }
    <div className="dropFooter">
      <span>{preview?'Replace video':'Browse video'}</span>
      <small>{fileMeta?`${fileMeta.name} · ${formatFileSize(fileMeta.size)}`:'Local preview only · max 500 MB by default'}</small>
    </div>
    <input name={name} type="file" accept="video/*,.avi,.mp4,.mov,.mkv,.mpeg,.mpg" required onChange={handleChange}/>
  </label>;
}

function SubmitBar({
  busy,disabled=false,label,busyLabel,note,
}:{
  busy:boolean;
  disabled?:boolean;
  label:string;
  busyLabel:string;
  note:string;
}){
  return <div className="submitBar">
    <div><Icon name="privacy"/><span>{note}</span></div>
    <button className="primaryButton" type="submit" disabled={busy||disabled}>{busy?<><Spinner/>{busyLabel}</>:<>{label}<span>→</span></>}</button>
  </div>;
}

function ReadinessNotice({title,text,tone}:{title:string;text:string;tone:'warn'|'good'}){
  return <div className={`readinessNotice ${tone}`}>
    <span><Icon name={tone==='good'?'check':'alert'}/></span>
    <div><strong>{title}</strong><p>{text}</p></div>
  </div>;
}

function AuthChoice({active,tone,title,detail,onClick}:{active:boolean;tone:'good'|'danger'|'warn';title:string;detail:string;onClick:()=>void}){
  return <button type="button" className={`authChoice ${tone} ${active?'active':''}`} onClick={onClick}>
    <span className="authRadio"><i></i></span>
    <span><strong>{title}</strong><small>{detail}</small></span>
  </button>;
}

function OccupancyTimeline({observations,reported}:{observations:any[];reported:number}){
  const samples=(observations||[]).filter(item=>Number.isFinite(Number(item?.smoothed_count)));
  if(samples.length<2) return null;

  const width=600;
  const height=160;
  const padX=28;
  const padY=22;
  const maxCount=Math.max(
    1,
    reported,
    ...samples.map(item=>Number(item.smoothed_count||0)),
    ...samples.map(item=>Number(item.raw_count||0)),
  );
  const x=(index:number)=>padX+(index/(samples.length-1))*(width-padX*2);
  const y=(value:number)=>height-padY-(value/maxCount)*(height-padY*2);
  const stablePoints=samples.map((item,index)=>`${x(index)},${y(Number(item.smoothed_count||0))}`).join(' ');
  const rawPoints=samples.map((item,index)=>`${x(index)},${y(Number(item.raw_count||0))}`).join(' ');
  const reportY=y(reported);

  return <div className="timelineCard">
    <div className="timelineHead">
      <div><span className="eyebrow">TEMPORAL PROOF</span><strong>Occupancy over sampled time</strong></div>
      <div className="timelineLegend">
        <span><i className="legendStable"></i>Stable occupancy</span>
        <span><i className="legendRaw"></i>Raw detections</span>
        <span><i className="legendReported"></i>Reported</span>
      </div>
    </div>
    <svg className="occupancyChart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Attendance occupancy timeline">
      <line x1={padX} y1={reportY} x2={width-padX} y2={reportY} className="reportedLine"/>
      <polyline points={rawPoints} className="rawLine"/>
      <polyline points={stablePoints} className="stableLine"/>
      <text x={padX} y={14} className="chartLabel">{maxCount}</text>
      <text x={padX} y={height-5} className="chartLabel">0</text>
      <text x={width-padX-5} y={height-5} textAnchor="end" className="chartLabel">{samples.at(-1)?.second??'—'}s</text>
    </svg>
  </div>;
}

function DecisionHeader({tone,eyebrow,title,text}:{tone:'good'|'warn'|'danger';eyebrow:string;title:string;text:string}){
  return <div className={`decisionHeader ${tone}`}>
    <span className="decisionIcon"><Icon name={tone==='good'?'check':'alert'}/></span>
    <div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2><p>{text}</p></div>
  </div>;
}

function WorkCellResult({cell}:{cell:any}){
  const activity=Math.round((cell.activity_fraction||0)*100);
  const presence=Math.round((cell.registered_worker_presence_fraction||0)*100);
  const state=activity>0?'Activity sustained':presence>0?'Worker present · no sustained motion':'No stable worker';
  return <div className="cellResult">
    <div className="cellResultHead">
      <div><strong>{String(cell.zone_id).replaceAll('_',' ')}</strong><span>{presence}% stable-worker presence</span></div>
      <b>{activity}% active</b>
    </div>
    <div className="cellStateLine">{state}</div>
    <div className="progressTrack"><i style={{width:`${activity}%`}}></i></div>
    <details className="technicalDetails">
      <summary>Technical motion evidence</summary>
      <div className="cellSignals">
        <span>Motion p50 <b>{pct(cell.worker_motion_fraction_p50)}</b></span>
        <span>p90 <b>{pct(cell.worker_motion_fraction_p90)}</b></span>
        <span>p95 <b>{pct(cell.worker_motion_fraction_p95)}</b></span>
      </div>
    </details>
  </div>;
}

function CaseCard({item,review,resolved=false}:{item:Case;review:(caseId:string,action:CaseStatus,note?:string)=>void;resolved?:boolean}){
  const pillar=casePillar(item.case_type);
  const duplicate=item.evidence?.find(evidence=>Boolean(evidence.duplicate_of));
  const [reviewNote,setReviewNote]=useState('');
  const [showEvidence,setShowEvidence]=useState(false);
  const finalReady=reviewNote.trim().length>0;
  const latestReview=item.review_history?.at(-1);

  return <article className={resolved?'caseCard resolvedCase':'caseCard'}>
    <div className="caseCardHead">
      <div className="caseTitle"><span className={`severityDot ${item.severity}`}></span><div><strong>{item.case_type.replaceAll('_',' ')}</strong><small>{item.case_id} · {item.centre_id} · {item.batch_id}</small></div></div>
      <span className={`statusBadge ${item.status}`}>{item.status.replaceAll('_',' ')}</span>
    </div>
    <div className="pillarLabel"><Icon name={pillar.icon}/><span>{pillar.label}</span></div>
    <p>{item.summary}</p>
    {duplicate&&<div className="duplicateAlert">
      <span className="duplicateIcon"><Icon name="fingerprint"/></span>
      <div>
        <strong>Evidence integrity signal</strong>
        <span>Possible duplicate evidence detected · matches {duplicate.duplicate_of}</span>
        <small>This is independent of the compliance finding above.</small>
      </div>
    </div>}
    <div className="caseFacts">
      {item.persistence_ratio!=null&&<span>Persistence <b>{Math.round(item.persistence_ratio*100)}%</b></span>}
      {item.evidence?.length?<span>Evidence <b>{item.evidence.length}</b></span>:null}
      <span>Severity <b>{item.severity}</b></span>
    </div>
    <div className="caseLinks">
      {item.evidence?.[0]&&<button type="button" className="evidenceToggle" onClick={()=>setShowEvidence(value=>!value)}><Icon name="image"/>{showEvidence?'Hide evidence':'Inspect evidence'}</button>}
      <a href={`${API}/api/cases/${item.case_id}/evidence-pack`} target="_blank" rel="noreferrer"><Icon name="package"/>Evidence pack</a>
    </div>
    {showEvidence&&item.evidence?.[0]&&<div className="evidenceInspector">
      <div className="evidenceImageWrap">
        <img src={`${API}/evidence/${item.evidence[0].evidence_id}.jpg`} alt={`Evidence for ${item.case_id}`}/>
      </div>
      <div className="evidenceMeta">
        <span className="eyebrow">EVIDENCE SNAPSHOT</span>
        <strong>{item.evidence[0].evidence_id}</strong>
        <dl>
          <div><dt>SHA-256</dt><dd title={item.evidence[0].sha256}>{shortHash(item.evidence[0].sha256)}</dd></div>
          <div><dt>Integrity</dt><dd>{item.evidence[0].duplicate_of?`Possible duplicate · ${item.evidence[0].duplicate_of}`:'No duplicate signal'}</dd></div>
          <div><dt>Captured</dt><dd>{formatTimestamp(item.created_at)}</dd></div>
        </dl>
      </div>
    </div>}
    {!!item.review_history?.length&&<div className="auditRow"><Icon name="history"/><span>{item.review_history.length} officer action{item.review_history.length===1?'':'s'} recorded</span></div>}
    {resolved&&latestReview?.note&&<div className="resolvedRationale">
      <span>Officer rationale</span>
      <strong>{latestReview.note}</strong>
    </div>}
    {!resolved&&<>
      <label className="reviewNoteField">
        <span>Officer note <b>required for final decision</b></span>
        <textarea
          value={reviewNote}
          onChange={event=>setReviewNote(event.target.value)}
          placeholder="What did you verify, and why is this case confirmed or a false positive?"
          rows={3}
        />
      </label>
      <div className="reviewActions">
        <button type="button" onClick={()=>review(item.case_id,'under_review',reviewNote)}>Start review</button>
        <button type="button" onClick={()=>review(item.case_id,'virtual_verification',reviewNote)}>Virtual verify</button>
        <button type="button" disabled={!finalReady} onClick={()=>review(item.case_id,'false_positive',reviewNote)}>False positive</button>
        <button type="button" disabled={!finalReady} className="confirm" onClick={()=>review(item.case_id,'confirmed',reviewNote)}>Confirm exception</button>
      </div>
    </>}
  </article>;
}

function CompactCase({item}:{item:Case}){
  return <div className="compactCase">
    <span className={`severityDot ${item.severity}`}></span>
    <div><strong>{item.case_type.replaceAll('_',' ')}</strong><small>{item.centre_id} · {item.status.replaceAll('_',' ')}</small></div>
    <span className="caseChevron">›</span>
  </div>;
}

function Kpi({icon,label,value,note,attention=false}:{icon:string;label:string;value:string|number;note:string;attention?:boolean}){
  return <div className={attention?'kpi attention':'kpi'}>
    <span className="kpiIcon"><Icon name={icon}/></span>
    <div><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
  </div>;
}

function LaneCard({icon,title,question,steps,action,onClick,accent=false}:{icon:string;title:string;question:string;steps:string[];action:string;onClick:()=>void;accent?:boolean}){
  return <button className={accent?'laneCard accent':'laneCard'} type="button" onClick={onClick}>
    <div className="laneTop"><span className="laneIcon"><Icon name={icon}/></span><span className="laneArrow">↗</span></div>
    <h3>{title}</h3>
    <p>{question}</p>
    <div className="laneSteps">{steps.map((step,index)=><span key={step}><i>{index+1}</i>{step}</span>)}</div>
    <strong className="laneAction">{action}</strong>
  </button>;
}

function FlowStep({number,title,detail}:{number:string;title:string;detail:string}){
  return <div className="flowStep"><span>{number}</span><div><strong>{title}</strong><p>{detail}</p></div></div>;
}

function CheckRow({title,detail}:{title:string;detail:string}){
  return <div className="checkRow"><span><Icon name="check"/></span><div><strong>{title}</strong><p>{detail}</p></div></div>;
}

function SignalRow({label,state,detail}:{label:string;state:string;detail:string}){
  return <div className="signalRow"><div><strong>{label}</strong><p>{detail}</p></div><span>{state}</span></div>;
}

function Field({label,help,children}:{label:string;help?:string;children:ReactNode}){
  return <label className="field"><span>{label}</span>{children}{help&&<small>{help}</small>}</label>;
}

function ResultMetric({label,value}:{label:string;value:string|number}){
  return <div className="resultMetric"><span>{label}</span><strong>{value}</strong></div>;
}

function EmptyState({title,text}:{title:string;text:string}){
  return <div className="emptyState"><span><Icon name="check"/></span><strong>{title}</strong><p>{text}</p></div>;
}

function PolicyCard({icon,title,text}:{icon:string;title:string;text:string}){
  return <div className="policyTile"><span><Icon name={icon}/></span><strong>{title}</strong><p>{text}</p></div>;
}

function ArchitectureStep({title,detail}:{title:string;detail:string}){
  return <div className="architectureStep"><strong>{title}</strong><span>{detail}</span></div>;
}

function Spinner(){return <span className="spinner"></span>;}

function formatFileSize(bytes:number){
  if(bytes<1024) return `${bytes} B`;
  if(bytes<1024*1024) return `${(bytes/1024).toFixed(1)} KB`;
  return `${(bytes/(1024*1024)).toFixed(1)} MB`;
}

function shortHash(value:string|undefined){
  if(!value) return '—';
  return value.length>18?`${value.slice(0,10)}…${value.slice(-6)}`:value;
}

function formatTimestamp(value:string|undefined){
  if(!value) return '—';
  const date=new Date(value);
  if(Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined,{
    year:'numeric',
    month:'short',
    day:'numeric',
    hour:'2-digit',
    minute:'2-digit',
  });
}

function sortPriorityCases(cases:Case[]){
  const severityRank:Record<string,number>={high:0,medium:1,low:2};
  const statusRank:Record<CaseStatus,number>={
    open:0,
    under_review:1,
    virtual_verification:2,
    confirmed:3,
    false_positive:3,
    resolved:3,
  };
  return [...cases].sort((a,b)=>{
    const severity=(severityRank[a.severity]??9)-(severityRank[b.severity]??9);
    if(severity!==0) return severity;
    const status=(statusRank[a.status]??9)-(statusRank[b.status]??9);
    if(status!==0) return status;
    return String(b.created_at||'').localeCompare(String(a.created_at||''));
  });
}

function tierLabel(value:string|undefined){
  if(value==='camera_verifiable') return 'Camera-verifiable';
  if(value==='camera_partially_verifiable') return 'Partially verifiable';
  if(value==='officer_verification_required') return 'Officer-only';
  return 'Verification tier';
}

function pct(value:number|undefined|null){
  if(value==null||Number.isNaN(Number(value))) return '—';
  return `${(Number(value)*100).toFixed(1)}%`;
}

function Icon({name}:{name:string}){
  const common={width:18,height:18,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.8,strokeLinecap:'round' as const,strokeLinejoin:'round' as const,'aria-hidden':true};
  if(name==='overview') return <svg {...common}><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>;
  if(name==='attendance'||name==='human') return <svg {...common}><circle cx="12" cy="8" r="3"/><path d="M5.5 20a6.5 6.5 0 0 1 13 0"/></svg>;
  if(name==='activity') return <svg {...common}><path d="M3 15h4l2-8 4 12 2-7h6"/><path d="M3 4v16"/></svg>;
  if(name==='infrastructure') return <svg {...common}><path d="M4 20V7l8-4 8 4v13"/><path d="M8 20v-5h8v5M8 9h.01M12 9h.01M16 9h.01"/></svg>;
  if(name==='cases'||name==='alert') return <svg {...common}><path d="M12 3 2.8 19h18.4L12 3Z"/><path d="M12 9v4M12 17h.01"/></svg>;
  if(name==='evidence'||name==='package') return <svg {...common}><path d="M4 7.5 12 3l8 4.5V17l-8 4-8-4V7.5Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></svg>;
  if(name==='shield'||name==='privacy') return <svg {...common}><path d="M12 3 5 6v5c0 4.5 2.8 8.1 7 10 4.2-1.9 7-5.5 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-4"/></svg>;
  if(name==='site') return <svg {...common}><path d="M4 21h16M6 21V5h12v16M9 9h2M13 9h2M9 13h2M13 13h2"/></svg>;
  if(name==='camera'||name==='video') return <svg {...common}><rect x="3" y="6" width="14" height="12" rx="2"/><path d="m17 10 4-2v8l-4-2"/><circle cx="10" cy="12" r="2.5"/></svg>;
  if(name==='sync') return <svg {...common}><path d="M20 7h-5V2M4 17h5v5"/><path d="M19 12a7 7 0 0 0-12-5l-2 2M5 12a7 7 0 0 0 12 5l2-2"/></svg>;
  if(name==='check') return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/></svg>;
  if(name==='info') return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>;
  if(name==='image') return <svg {...common}><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 15-4-4L5 20"/></svg>;
  if(name==='history') return <svg {...common}><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></svg>;
  if(name==='zones') return <svg {...common}><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4z"/><path d="M14 17h6M17 14v6"/></svg>;
  if(name==='fingerprint') return <svg {...common}><path d="M8 11a4 4 0 0 1 8 0v2"/><path d="M6 11a6 6 0 0 1 12 0v3"/><path d="M10 13v2a4 4 0 0 0 4 4"/><path d="M14 11v3a6 6 0 0 0 2 4.5"/><path d="M6.5 15a8 8 0 0 0 3 5"/></svg>;
  return <svg {...common}><circle cx="12" cy="12" r="8"/></svg>;
}
