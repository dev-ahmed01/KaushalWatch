'use client';

import { ChangeEvent, FormEvent, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import AnalysisProgressOverlay from '../../../components/AnalysisProgressOverlay';
import VideoWorkspace from '../../../components/VideoWorkspace';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { API, getCentre } from '../../../lib/api';
import type { Centre } from '../../../lib/types';
import { withRunningStep } from '../../../lib/workflow';
import { OutcomeCard, PageHeader } from '../../../components/Ui';

export default function InfrastructureVerification(){
  const {centreId}=useParams<{centreId:string}>();
  const id=String(centreId);
  const [file,setFile]=useState<File|null>(null);
  const [preview,setPreview]=useState('');
  const [profile,setProfile]=useState('compliant');
  const [manifest,setManifest]=useState<any[]>([]);
  const [result,setResult]=useState<any>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [centre,setCentre]=useState<Centre|null>(null);

  useEffect(()=>{
    fetch(`${API}/api/demo/infrastructure`)
      .then(r=>r.json())
      .then(p=>setManifest(p.items||[]))
      .catch(()=>{});
    getCentre(id).then(setCentre).catch(()=>setCentre(null));
  },[id]);

  function onFile(e:ChangeEvent<HTMLInputElement>){
    const next=e.target.files?.[0]||null;
    setFile(next);
    setPreview(next?URL.createObjectURL(next):'');
  }

  async function analyse(e:FormEvent){
    e.preventDefault();
    if(!file){setError('Choose a CCTV clip before starting infrastructure analysis.');return;}
    setBusy(true);setError('');setResult(null);
    const body=new FormData();
    body.append('file',file);
    body.append('centre_id',id);
    body.append('batch_id','ELEC-2026-08');
    body.append('camera_id','LAB-CAM-02');
    body.append('demo_profile',profile);
    try{
      const response=await fetch(`${API}/api/process-infrastructure-video`,{method:'POST',body});
      const payload=await response.json();
      if(!response.ok) throw new Error(payload.detail||'Infrastructure analysis failed');
      setResult(payload);
    }catch(err:any){setError(err.message||'Infrastructure analysis failed');}
    finally{setBusy(false);}
  }

  const items=result?.items||manifest;
  const tier=(name:string)=>items.filter((i:any)=>i.verification_tier===name);

  return <div className="pageScene fadeIn">
    <PageHeader
      eyebrow="Selected Centre / Infrastructure"
      title="Infrastructure & Asset Verification"
      subtitle="Separate what the camera can verify, what it can only support, and what still requires an officer."
      actions={<>
        <select className="headerSelect" value={profile} onChange={e=>setProfile(e.target.value)}>
          <option value="compliant">Compliant demo telemetry</option>
          <option value="discrepancy">Discrepancy demo telemetry</option>
        </select>
        <button form="infra-form" className="primaryBtn" disabled={busy}>{busy?'Analysing…':'Analyse Infrastructure'}</button>
      </>}
    />
    <WorkflowStepper centreId={id} states={withRunningStep(centre,'infrastructure',busy,result?(result.created?'attention':'complete'):undefined)}/>
    {error&&<div className="inlineError">{error}</div>}

    <div className="infrastructureLayout">
      <form id="infra-form" className="infraMediaPanel analysisProgressHost" onSubmit={analyse}>
        <VideoWorkspace preview={preview} inputName="file" onFile={onFile} label="Infrastructure camera" badge={preview?'Recorded clip':'No feed'}/>
        {busy&&<AnalysisProgressOverlay mode="infrastructure"/>}
        <div className="sourceDisclosure">ⓘ Equipment counts below are stage-safe demo telemetry. The uploaded video supplies evidence imagery and optional visual-motion evidence.</div>
      </form>

      <div className="infraTierGrid">
        <TierCard title="Camera-Verifiable Assets" icon="▣" tone="good" items={tier('camera_verifiable')}/>
        <TierCard title="Partially Verifiable Assets" icon="◉" tone="warn" items={tier('camera_partially_verifiable')}/>
        <TierCard title="Officer-Only Assets" icon="◆" tone="info" items={tier('officer_verification_required')}/>
      </div>

      <AssistantPanel centreId={id}/>
    </div>

    {result&&<div className="infraOutcomeRow">
      <OutcomeCard
        tone={result.created?'danger':'good'}
        title={result.created?'Infrastructure item not detected':'Infrastructure profile completed without a persistent exception'}
        text={result.case?.summary||result.banner}
      />
      {result.created&&result.case?.evidence?.[0]&&
        <a className="secondaryBtn" href={`${API}/evidence/${result.case.evidence[0].evidence_id}.jpg`} target="_blank" rel="noreferrer">View Evidence</a>}
    </div>}
  </div>;
}

function TierCard({title,icon,tone,items}:{title:string;icon:string;tone:'good'|'warn'|'info';items:any[]}){
  const compliant=items.filter(i=>i.state==='COMPLIANT').length;
  return <section className={`tierCard ${tone}`}>
    <div className="tierHead">
      <span>{icon}</span>
      <div><strong>{title}</strong><small>{tone==='good'?'Automated via CCTV':tone==='warn'?'CCTV + officer review':'Manual verification'}</small></div>
      <b>{compliant}/{items.length}</b>
    </div>
    <div className="tierItems">
      {items.map(i=><div className="tierItem" key={i.id}>
        <span>{i.state==='COMPLIANT'?'✓':i.state==='DISCREPANCY'?'!':'○'}</span>
        <b>{i.label}</b>
        <small>{String(i.state).replaceAll('_',' ')}</small>
      </div>)}
    </div>
  </section>;
}
