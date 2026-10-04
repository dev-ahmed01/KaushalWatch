'use client';

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react';

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
  review_history?:{timestamp:string;from_status:string;to_status:string;note?:string|null}[];
};

type Dashboard = {
  banner:string;
  centres_monitored:number;
  open_cases:number;
  camera_issues:number;
  synced_edge_events:number;
  cases:Case[];
};

type InfraItem = {
  id:string;
  label:string;
  required:number;
  observed:number|null;
  state:string;
  confidence:number|null;
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
  const [activeView,setActiveView]=useState<ViewKey>('overview');
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
  const [practicalAuth,setPracticalAuth]=useState<'valid'|'absent'|'unknown'>('unknown');

  const refresh=async()=>{
    const [dashboardResponse,infraResponse]=await Promise.all([
      fetch(`${API}/api/dashboard`,{cache:'no-store'}),
      fetch(`${API}/api/demo/infrastructure`,{cache:'no-store'}),
    ]);
    if(!dashboardResponse.ok) throw new Error('Command-centre API is unavailable');
    setData(await dashboardResponse.json());
    if(infraResponse.ok){
      const body=await infraResponse.json();
      setInfra(body.items||[]);
    }
  };

  useEffect(()=>{refresh().catch(err=>setError(String(err.message||err)));},[]);

  const priority=useMemo(
    ()=>[...(data?.cases||[])].reverse(),
    [data]
  );
  const cameraHealthy=(data?.camera_issues??0)===0;

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
      if(!(zonesFile instanceof File)) throw new Error('Choose a work-zone JSON file');

      const body=new FormData();
      body.append('file',video);
      body.append('zones_json',await zonesFile.text());
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
      for(const key of ['centre_id','batch_id','camera_id','operability_item_id','roi_x1','roi_y1','roi_x2','roi_y2']){
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
      await refresh();
    }catch(err:any){
      setError(err.message||String(err));
    }finally{
      setInfraBusy(false);
    }
  }

  async function review(caseId:string,action:CaseStatus){
    setError('');
    const response=await fetch(`${API}/api/cases/${caseId}/review`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action}),
    });
    if(!response.ok){
      setError('Could not update the case');
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
              <strong>DEMO-KA-104</strong>
              <small>Bengaluru · demonstration workspace</small>
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
          <span className="topEyebrow">KAUSHALWATCH / DEMO-KA-104</span>
          <strong>{navItems.find(item=>item.key===activeView)?.label}</strong>
        </div>
        <div className="topStatus">
          <span className={cameraHealthy?'healthChip good':'healthChip warn'}><i></i>Camera trust {cameraHealthy?'nominal':'attention'}</span>
          <span className="healthChip"><Icon name="human"/>Human review enforced</span>
        </div>
      </header>

      <div className="page">
        {error&&<div className="errorBanner"><Icon name="alert"/><span>{error}</span></div>}

        {activeView==='overview'&&<Overview
          data={data}
          priority={priority}
          cameraHealthy={cameraHealthy}
          onOpen={setActiveView}
        />}

        {activeView==='attendance'&&<AttendanceView
          result={attendanceResult}
          busy={attendanceBusy}
          preview={attendancePreview}
          onPreview={(e)=>previewFile(e,setAttendancePreview)}
          onSubmit={submitAttendance}
        />}

        {activeView==='practical'&&<PracticalView
          result={practicalResult}
          busy={practicalBusy}
          preview={practicalPreview}
          auth={practicalAuth}
          setAuth={setPracticalAuth}
          onPreview={(e)=>previewFile(e,setPracticalPreview)}
          onSubmit={submitPractical}
        />}

        {activeView==='infrastructure'&&<InfrastructureView
          infra={infra}
          result={infraResult}
          busy={infraBusy}
          preview={infraPreview}
          onPreview={(e)=>previewFile(e,setInfraPreview)}
          onSubmit={submitInfrastructure}
        />}

        {activeView==='cases'&&<CasesView
          cases={priority}
          review={review}
        />}

        {activeView==='evidence'&&<EvidenceView/>}
      </div>
    </main>
  </div>;
}

function Overview({
  data,
  priority,
  cameraHealthy,
  onOpen,
}:{
  data:Dashboard|null;
  priority:Case[];
  cameraHealthy:boolean;
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
      <Kpi icon="site" label="Centres monitored" value={data?.centres_monitored??'—'} note="Demo workspace"/>
      <Kpi icon="cases" label="Open review cases" value={data?.open_cases??'—'} note="Persistent exceptions only" attention={(data?.open_cases??0)>0}/>
      <Kpi icon="camera" label="Camera integrity" value={cameraHealthy?'Nominal':`${data?.camera_issues??0} issue`} note="Trust gates every inference" attention={!cameraHealthy}/>
      <Kpi icon="sync" label="Edge events synced" value={data?.synced_edge_events??'—'} note="Raw video not required"/>
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
  result,busy,preview,onPreview,onSubmit,
}:{
  result:any;
  busy:boolean;
  preview:string;
  onPreview:(event:ChangeEvent<HTMLInputElement>)=>void;
  onSubmit:(event:FormEvent<HTMLFormElement>)=>void;
}){
  const latest=result?.observations?.[result.observations.length-1];
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
          <div className="formGrid two">
            <Field label="Reported attendance"><input name="reported_attendance" type="number" min="0" defaultValue="12" required/></Field>
            <Field label="Camera ID"><input name="camera_id" defaultValue="LAB-CAM-01"/></Field>
            <Field label="Centre ID"><input name="centre_id" defaultValue="DEMO-KA-104"/></Field>
            <Field label="Batch ID"><input name="batch_id" defaultValue="ELEC-DEMO-01"/></Field>
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
        tone={result.case?'warn':'good'}
        eyebrow="ATTENDANCE RESULT"
        title={result.case?'Persistent attendance exception':'No persistent attendance exception'}
        text={result.case?.summary||'Observed stable occupancy did not produce a persistent review case under the current policy.'}
      />
      <div className="resultGrid">
        <ResultMetric label="Reported" value={result.reported_attendance}/>
        <ResultMetric label="Stable occupancy" value={result.estimated_occupancy}/>
        <ResultMetric label="Mismatch" value={`${result.discrepancy_pct}%`}/>
        <ResultMetric label="Registered now" value={latest?.registered_count??'—'}/>
        <ResultMetric label="Confirmed now" value={latest?.confirmed_count??'—'}/>
        <ResultMetric label="Raw detections now" value={latest?.raw_count??'—'}/>
      </div>
    </section>}
  </>;
}

function PracticalView({
  result,busy,preview,auth,setAuth,onPreview,onSubmit,
}:{
  result:any;
  busy:boolean;
  preview:string;
  auth:'valid'|'absent'|'unknown';
  setAuth:(value:'valid'|'absent'|'unknown')=>void;
  onPreview:(event:ChangeEvent<HTMLInputElement>)=>void;
  onSubmit:(event:FormEvent<HTMLFormElement>)=>void;
}){
  const decision=String(result?.decision||'');
  const tone=decision.includes('unauthorized')?'danger':decision.includes('authorized_')?'good':'warn';

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
            <span><strong>Work-zone JSON</strong><small>Configured practical work cells</small></span>
            <input name="zones_file" type="file" accept=".json,application/json" required/>
          </label>
          <Field label="Zone profile" help="Use the named profile inside your JSON, e.g. authorized or unauthorized.">
            <input name="zone_profile" placeholder="authorized"/>
          </Field>
        </div>

        <div className="formSection">
          <div className="formSectionTitle"><span className="stepNumber">02</span><div><h3>External authorization</h3><p>This state comes from the training schedule or work order—not the camera.</p></div></div>
          <div className="authSelector">
            <AuthChoice active={auth==='valid'} tone="good" title="Valid" detail="Matching training/work authorization exists" onClick={()=>setAuth('valid')}/>
            <AuthChoice active={auth==='absent'} tone="danger" title="Not found" detail="No matching authorization was supplied" onClick={()=>setAuth('absent')}/>
            <AuthChoice active={auth==='unknown'} tone="warn" title="Unknown" detail="Route activity for officer verification" onClick={()=>setAuth('unknown')}/>
          </div>
        </div>

        <div className="formGrid three">
          <Field label="Centre ID"><input name="centre_id" defaultValue="DEMO-KA-104"/></Field>
          <Field label="Batch ID"><input name="batch_id" defaultValue="ELEC-DEMO-01"/></Field>
          <Field label="Camera ID"><input name="camera_id" defaultValue="LAB-CAM-03"/></Field>
        </div>

        <SubmitBar
          busy={busy}
          label="Run practical-work verification"
          busyLabel="Analysing work-cell activity…"
          note="No face recognition. Activity is a visual proxy, not task recognition."
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
        title={decision.replaceAll('_',' ')}
        text={
          decision.includes('unauthorized')
            ? 'Persistent practical-work activity was observed without a supplied matching authorization. A human-review case was created.'
            : decision.includes('authorized_')
              ? 'Persistent practical-work activity was observed and a valid external authorization was supplied. No compliance exception is created.'
              : 'The result requires officer verification before any compliance action.'
        }
      />

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
  infra,result,busy,preview,onPreview,onSubmit,
}:{
  infra:InfraItem[];
  result:any;
  busy:boolean;
  preview:string;
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

    <section className="workbench">
      <form className="analysisCard" onSubmit={onSubmit}>
        <div className="analysisHead">
          <div><span className="stepNumber">01</span><div><h2>Infrastructure evidence</h2><p>Select the CCTV clip to associate with this manifest check.</p></div></div>
          <span className="modeChip">Visual manifest</span>
        </div>

        <VideoDrop name="infra_file" preview={preview} onPreview={onPreview}/>

        <div className="formGrid three">
          <Field label="Centre ID"><input name="centre_id" defaultValue="DEMO-KA-104"/></Field>
          <Field label="Batch ID"><input name="batch_id" defaultValue="ELEC-DEMO-01"/></Field>
          <Field label="Camera ID"><input name="camera_id" defaultValue="LAB-CAM-02"/></Field>
        </div>

        <div className="formSection">
          <div className="formSectionTitle"><span className="stepNumber">02</span><div><h3>Optional operability proxy</h3><p>Visual activity inside an equipment ROI. This is not a mechanical diagnosis.</p></div></div>
          <input type="hidden" name="operability_item_id" value="drill_machine"/>
          <div className="formGrid four">
            <Field label="x1"><input name="roi_x1" type="number" defaultValue="0"/></Field>
            <Field label="y1"><input name="roi_y1" type="number" defaultValue="20"/></Field>
            <Field label="x2"><input name="roi_x2" type="number" defaultValue="220"/></Field>
            <Field label="y2"><input name="roi_y2" type="number" defaultValue="190"/></Field>
          </div>
        </div>

        <SubmitBar
          busy={busy}
          label="Run infrastructure verification"
          busyLabel="Analysing visual manifest…"
          note="Only persistent visual discrepancies should become review cases."
        />
      </form>

      <aside className="manifestCard">
        <div className="cardHead"><div><span className="eyebrow">DEMO MANIFEST</span><h2>Construction Electrician - LV</h2><p>Configured quantities are demonstration data.</p></div></div>
        <div className="manifestList">
          {infra.map(item=><div className="manifestRow" key={item.id}>
            <div><strong>{item.label}</strong><small>{item.state.replaceAll('_',' ')}</small></div>
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
      {result.created&&<div className="resultGrid">
        <ResultMetric label="Case" value={result.case.case_id}/>
        <ResultMetric label="Type" value="Infrastructure"/>
        <ResultMetric label="Evidence" value={result.case.evidence?.length?'Captured':'Missing'}/>
        <ResultMetric label="Operability" value={result.case.details?.apparent_operability?.state?.replaceAll('_',' ')||'Not evaluated'}/>
      </div>}
    </section>}
  </>;
}

function CasesView({cases,review}:{cases:Case[];review:(caseId:string,action:CaseStatus)=>void}){
  return <>
    <ModuleHero
      eyebrow="HUMAN REVIEW"
      title="AI surfaces evidence. Officers make the decision."
      text="Every persistent exception lands in one queue with its evidence, integrity metadata and review history. KaushalWatch does not issue penalties automatically."
      badge={`${cases.length} cases`}
      policy={['Open evidence','Inspect hashes','Virtual verification','Officer decision']}
    />

    <section className="caseWorkspace">
      <div className="queueHeader">
        <div><span className="eyebrow">PRIORITY QUEUE</span><h2>Reviewable exceptions</h2></div>
        <span className="queueCount">{cases.filter(item=>!['resolved','false_positive'].includes(item.status)).length} unresolved</span>
      </div>

      {cases.length===0&&<div className="card"><EmptyState title="No cases yet" text="Run one of the verification lanes to generate evidence-backed exceptions."/></div>}

      <div className="caseGrid">
        {cases.map(item=><CaseCard key={item.case_id} item={item} review={review}/>)}
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
      <PolicyCard icon="evidence" title="Minimal exception evidence" text="When a review case is created, person regions are blurred before central evidence retention."/>
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
  return <label className={preview?'videoDrop hasPreview':'videoDrop'}>
    {preview
      ? <video src={preview} controls muted playsInline/>
      : <div className="dropPlaceholder"><span className="dropIcon"><Icon name="video"/></span><strong>Choose CCTV clip</strong><small>MP4 or AVI · fixed camera recommended</small></div>
    }
    <div className="dropFooter"><span>{preview?'Replace video':'Browse video'}</span><small>Local preview only</small></div>
    <input name={name} type="file" accept="video/*,.avi,.mp4" required onChange={onPreview}/>
  </label>;
}

function SubmitBar({busy,label,busyLabel,note}:{busy:boolean;label:string;busyLabel:string;note:string}){
  return <div className="submitBar">
    <div><Icon name="privacy"/><span>{note}</span></div>
    <button className="primaryButton" type="submit" disabled={busy}>{busy?<><Spinner/>{busyLabel}</>:<>{label}<span>→</span></>}</button>
  </div>;
}

function AuthChoice({active,tone,title,detail,onClick}:{active:boolean;tone:'good'|'danger'|'warn';title:string;detail:string;onClick:()=>void}){
  return <button type="button" className={`authChoice ${tone} ${active?'active':''}`} onClick={onClick}>
    <span className="authRadio"><i></i></span>
    <span><strong>{title}</strong><small>{detail}</small></span>
  </button>;
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
  return <div className="cellResult">
    <div className="cellResultHead"><div><strong>{String(cell.zone_id).replaceAll('_',' ')}</strong><span>{presence}% stable-worker presence</span></div><b>{activity}% active</b></div>
    <div className="progressTrack"><i style={{width:`${activity}%`}}></i></div>
    <div className="cellSignals"><span>Motion p50 <b>{pct(cell.worker_motion_fraction_p50)}</b></span><span>p90 <b>{pct(cell.worker_motion_fraction_p90)}</b></span><span>p95 <b>{pct(cell.worker_motion_fraction_p95)}</b></span></div>
  </div>;
}

function CaseCard({item,review}:{item:Case;review:(caseId:string,action:CaseStatus)=>void}){
  return <article className="caseCard">
    <div className="caseCardHead">
      <div className="caseTitle"><span className={`severityDot ${item.severity}`}></span><div><strong>{item.case_type.replaceAll('_',' ')}</strong><small>{item.case_id} · {item.centre_id}</small></div></div>
      <span className={`statusBadge ${item.status}`}>{item.status.replaceAll('_',' ')}</span>
    </div>
    <p>{item.summary}</p>
    <div className="caseFacts">
      {item.persistence_ratio!=null&&<span>Persistence <b>{Math.round(item.persistence_ratio*100)}%</b></span>}
      {item.evidence?.length?<span>Evidence <b>{item.evidence.length}</b></span>:null}
      <span>Severity <b>{item.severity}</b></span>
    </div>
    <div className="caseLinks">
      {item.evidence?.[0]&&<a href={`${API}/evidence/${item.evidence[0].evidence_id}.jpg`} target="_blank" rel="noreferrer"><Icon name="image"/>Open evidence</a>}
      <a href={`${API}/api/cases/${item.case_id}/evidence-pack`} target="_blank" rel="noreferrer"><Icon name="package"/>Evidence pack</a>
    </div>
    {!!item.review_history?.length&&<div className="auditRow"><Icon name="history"/><span>{item.review_history.length} officer action{item.review_history.length===1?'':'s'} recorded</span></div>}
    <div className="reviewActions">
      <button type="button" onClick={()=>review(item.case_id,'under_review')}>Start review</button>
      <button type="button" onClick={()=>review(item.case_id,'virtual_verification')}>Virtual verify</button>
      <button type="button" onClick={()=>review(item.case_id,'false_positive')}>False positive</button>
      <button type="button" className="confirm" onClick={()=>review(item.case_id,'confirmed')}>Confirm exception</button>
    </div>
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

function Field({label,help,children}:{label:string;help?:string;children:React.ReactNode}){
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
  return <svg {...common}><circle cx="12" cy="12" r="8"/></svg>;
}
