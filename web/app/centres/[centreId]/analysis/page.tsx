'use client';

import Link from 'next/link';
import { ChangeEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import VideoWorkspace from '../../../components/VideoWorkspace';
import { API, getCentre, getRuntimeReadiness } from '../../../lib/api';
import type { Centre } from '../../../lib/types';
import { workflowStatesForCentre, type WorkflowState } from '../../../lib/workflow';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { PageHeader, Status } from '../../../components/Ui';

type RunState='pending'|'running'|'complete'|'attention'|'blocked';
type RunStages={
  attendance:RunState;
  practical:RunState;
  infrastructure:RunState;
  report:RunState;
};

const INITIAL:RunStages={attendance:'pending',practical:'pending',infrastructure:'pending',report:'pending'};

export default function AnalysisRun(){
  const {centreId}=useParams<{centreId:string}>();
  const id=String(centreId);
  const [centre,setCentre]=useState<Centre|null>(null);
  const [readiness,setReadiness]=useState<any>(null);
  const [file,setFile]=useState<File|null>(null);
  const [preview,setPreview]=useState('');
  const [reported,setReported]=useState(3);
  const [stages,setStages]=useState<RunStages>(INITIAL);
  const [messages,setMessages]=useState<Record<string,string>>({});
  const [running,setRunning]=useState(false);
  const [error,setError]=useState('');
  const controller=useRef<AbortController|null>(null);

  useEffect(()=>{
    Promise.all([getCentre(id),getRuntimeReadiness()])
      .then(([c,r])=>{setCentre(c);setReadiness(r);})
      .catch(()=>{});
  },[id]);

  function onFile(e:ChangeEvent<HTMLInputElement>){
    const next=e.target.files?.[0]||null;
    setFile(next);
    setPreview(next?URL.createObjectURL(next):'');
    setStages(INITIAL);
    setMessages({});
    setError('');
  }

  const baseStates=useMemo(()=>workflowStatesForCentre(centre),[centre]);
  const workflowStates=running||Object.values(stages).some(state=>state!=='pending')
    ? {
        attendance:toWorkflow(stages.attendance,baseStates.attendance),
        practical:toWorkflow(stages.practical,baseStates.practical),
        infrastructure:toWorkflow(stages.infrastructure,baseStates.infrastructure),
        review:toWorkflow(stages.report,baseStates.review),
      }
    : baseStates;

  const automatic=(centre?.settings as any)?.automatic_analysis!==false&&(centre?.settings as any)?.frequency!=='manual';
  const settings=(centre?.settings||{}) as any;
  const frequency=settings.frequency==='daily'?'Daily':settings.frequency==='manual'?'Manual only':'Every training day';
  const windows=Array.isArray(settings.monitoring_windows)&&settings.monitoring_windows.length?settings.monitoring_windows.join(' · '):'Not configured';
  const completed=Object.values(stages).filter(state=>state!=='pending'&&state!=='running').length;
  const progress=running?Math.max(8,Math.round((completed/4)*100)):completed?100:0;

  async function post(path:string,body:FormData){
    const next=new AbortController();
    controller.current=next;
    const response=await fetch(API+path,{method:'POST',body,signal:next.signal});
    const payload=await response.json().catch(()=>({}));
    if(!response.ok) throw new Error(payload.detail||'Analysis step failed');
    return payload;
  }

  async function runFullAnalysis(){
    if(!file){setError('Choose a CCTV clip before starting the full analysis.');return;}
    setRunning(true);setError('');setStages(INITIAL);setMessages({});
    const batch=centre?.batch_id||'ELEC-2026-08';

    try{
      setStages(s=>({...s,attendance:'running'}));
      const attendanceBody=new FormData();
      attendanceBody.append('file',file);
      attendanceBody.append('reported_attendance',String(reported));
      attendanceBody.append('centre_id',id);
      attendanceBody.append('batch_id',batch);
      attendanceBody.append('camera_id',centre?.camera_id||'LAB-CAM-01');
      const attendance=await post('/api/process-video',attendanceBody);
      const attendanceState:RunState=attendance.decision==='compliant'?'complete':attendance.decision==='attendance_exception'?'attention':'blocked';
      setStages(s=>({...s,attendance:attendanceState}));
      setMessages(m=>({...m,attendance:attendance.case?.summary||attendance.detector_message||'Attendance check completed.'}));

      setStages(s=>({...s,practical:'running'}));
      const practicalBody=new FormData();
      practicalBody.append('file',file);
      practicalBody.append('authorization','valid');
      practicalBody.append('zone_profile','authorized');
      practicalBody.append('centre_id',id);
      practicalBody.append('batch_id',batch);
      practicalBody.append('camera_id','LAB-CAM-03');
      try{
        const practical=await post('/api/process-practical-activity',practicalBody);
        const practicalState:RunState=['camera_evidence_insufficient','detector_unavailable'].includes(practical.decision)?'blocked':practical.case?'attention':'complete';
        setStages(s=>({...s,practical:practicalState}));
        setMessages(m=>({...m,practical:practical.case?.summary||practical.detector_message||String(practical.decision).replaceAll('_',' ')}));
      }catch(stepError:any){
        setStages(s=>({...s,practical:'blocked'}));
        setMessages(m=>({...m,practical:stepError.message||'Practical-work analysis unavailable.'}));
      }

      setStages(s=>({...s,infrastructure:'running'}));
      const infrastructureBody=new FormData();
      infrastructureBody.append('file',file);
      infrastructureBody.append('centre_id',id);
      infrastructureBody.append('batch_id',batch);
      infrastructureBody.append('camera_id','LAB-CAM-02');
      infrastructureBody.append('demo_profile','compliant');
      const infrastructure=await post('/api/process-infrastructure-video',infrastructureBody);
      setStages(s=>({...s,infrastructure:infrastructure.created?'attention':'complete'}));
      setMessages(m=>({...m,infrastructure:infrastructure.case?.summary||infrastructure.banner||'Infrastructure check completed.'}));

      setStages(s=>({...s,report:'running'}));
      const refreshed=await getCentre(id);
      setCentre(refreshed);
      setStages(s=>({...s,report:'complete'}));
      setMessages(m=>({...m,report:'Centre result, history and report data refreshed.'}));
    }catch(runError:any){
      if(runError?.name==='AbortError'){
        setError('Analysis stopped. Completed checkpoints remain in history; the active checkpoint was cancelled.');
      }else{
        setError(runError.message||'Full analysis could not be completed.');
      }
      setStages(current=>{
        const next={...current};
        for(const key of Object.keys(next) as (keyof RunStages)[]){
          if(next[key]==='running') next[key]='blocked';
        }
        return next;
      });
    }finally{
      controller.current=null;
      setRunning(false);
    }
  }

  function stop(){
    controller.current?.abort();
  }

  return <div className="pageScene fadeIn">
    <PageHeader
      eyebrow="Selected Centre / Analysis"
      title={running?'Running Analysis':'Centre Analysis'}
      subtitle={running?'KaushalWatch is processing the uploaded evidence through each independent checkpoint.':'Run all verification checkpoints from one recorded clip, or open an individual checkpoint for a targeted recheck.'}
      actions={<>
        <Link href={'/centres/'+id+'/history'} className="secondaryBtn">Recent Analysis</Link>
        {running
          ? <button className="secondaryBtn dangerText" type="button" onClick={stop}>Stop Analysis</button>
          : <Status tone={automatic?'good':'neutral'}>{automatic?'Schedule configured':'Manual mode'}</Status>
        }
      </>}
    />

    <WorkflowStepper centreId={id} states={workflowStates as any}/>

    <div className="analysisRunner">
      <section className="panel analysisRunnerMain">
        <div className="panelHead">
          <div><span className="sectionKicker">Full verification run</span><h2>{running?'Analysis in progress':'Upload one centre recording'}</h2></div>
          {running&&<Status tone="info">{progress}%</Status>}
        </div>

        <VideoWorkspace preview={preview} inputName="analysis-file" onFile={onFile} label="Shared centre evidence clip" badge={preview?'Ready for analysis':'No recording'}/>

        <div className="analysisRunnerControls">
          <label>
            <span>Centre-reported attendance</span>
            <input type="number" min="0" value={reported} onChange={event=>setReported(Number(event.target.value))} disabled={running}/>
          </label>
          <button className="primaryBtn" type="button" disabled={running||!file} onClick={runFullAnalysis}>{running?'Analysing…':'Start Full Analysis'}</button>
        </div>

        {running&&<div className="analysisProgress"><i style={{width:progress+'%'}}></i></div>}
        {error&&<div className="inlineError">{error}</div>}

        <div className="analysisRunStages">
          <RunStage number="1" title="Attendance" state={stages.attendance} message={messages.attendance||'Anonymous stable occupancy vs reported attendance.'}/>
          <RunStage number="2" title="Practical Work" state={stages.practical} message={messages.practical||'Work-cell activity + external authorization.'}/>
          <RunStage number="3" title="Infrastructure" state={stages.infrastructure} message={messages.infrastructure||'Camera-verifiable, partial and officer-only assets.'}/>
          <RunStage number="4" title="Review Outcome" state={stages.report} message={messages.report||'Refresh centre result, history and report readiness.'}/>
        </div>
      </section>

      <aside className="analysisLaunchSide">
        <section className="panel runScheduleCard">
          <div className="panelHead"><div><span className="sectionKicker">Automation policy</span><h2>Configured monitoring</h2></div><Status tone={automatic?'good':'neutral'}>{automatic?'Configured':'Off'}</Status></div>
          <div className="runScheduleBody">
            <div><span>Frequency</span><b>{frequency}</b></div>
            <div><span>Monitoring windows</span><b>{windows}</b></div>
            <div><span>Connectivity</span><b>{centre?.connectivity_mode?.replaceAll('_',' ')||'normal'}</b></div>
          </div>
          <div className="runtimeNotice warn">Automatic policy is stored centrally. The connected edge scheduler currently runs attendance once per configured window and syncs compact telemetry. Practical work and infrastructure remain part of the full-analysis workflow until their edge adapters are connected.</div>
        </section>

        <section className="panel runScheduleCard">
          <div className="panelHead"><div><span className="sectionKicker">Runtime readiness</span><h2>Analysis engines</h2></div></div>
          <div className="runScheduleBody">
            <div><span>Attendance</span><b>{readiness?.attendance?.ready?'Ready':'Fallback / blocked conclusions'}</b></div>
            <div><span>Practical work</span><b>{readiness?.practical_work?.ready?'Ready':'Optional YOLO runtime missing'}</b></div>
            <div><span>Infrastructure</span><b>{readiness?.infrastructure?.ready?'Ready':'Unavailable'}</b></div>
          </div>
        </section>

        <AssistantPanel centreId={id}/>
      </aside>
    </div>

    <section className="panel analysisLaunchPanel">
      <div className="analysisLaunchHero">
        <span className="analysisLaunchOrb">↗</span>
        <div><span className="sectionKicker">Targeted recheck</span><h2>Open one checkpoint</h2><p>Use these pages when you only need to re-run one verification pillar or inspect its controls in detail.</p></div>
      </div>
      <div className="analysisLaunchSteps">
        <LaunchStep number="1" title="Attendance" text="Stable anonymous occupancy vs submitted attendance." href={'/centres/'+id+'/attendance'} tone="blue"/>
        <LaunchStep number="2" title="Practical Work" text="Persistent work-cell activity + external authorization." href={'/centres/'+id+'/practical'} tone="green"/>
        <LaunchStep number="3" title="Infrastructure" text="Camera-verifiable, partial, and officer-only manifest." href={'/centres/'+id+'/infrastructure'} tone="amber"/>
        <LaunchStep number="4" title="Review Outcome" text="Human decision, escalation and evidence audit." href={'/centres/'+id+'/outcome'} tone="slate"/>
      </div>
    </section>
  </div>;
}

function toWorkflow(state:RunState,fallback:WorkflowState):WorkflowState{
  if(state==='pending') return fallback;
  if(state==='complete') return 'complete';
  return state;
}

function RunStage({number,title,state,message}:{number:string;title:string;state:RunState;message:string}){
  const label=state==='pending'?'Pending':state==='running'?'In progress':state==='complete'?'Completed':state==='attention'?'Needs review':'Blocked';
  const symbol=state==='pending'?number:state==='running'?'↻':state==='complete'?'✓':state==='attention'?'!':'×';
  return <div className={'analysisRunStage '+state}>
    <span>{symbol}</span>
    <div><b>{title}</b><small>{message}</small></div>
    <em>{label}</em>
  </div>;
}

function LaunchStep({number,title,text,href,tone}:{number:string;title:string;text:string;href:string;tone:string}){
  return <Link href={href} className={'analysisLaunchStep '+tone}>
    <span>{number}</span>
    <div><b>{title}</b><small>{text}</small></div>
    <em>Open →</em>
  </Link>;
}
