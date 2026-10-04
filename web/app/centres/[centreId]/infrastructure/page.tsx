'use client';

import { ChangeEvent, FormEvent, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import EvidenceGallery from '../../../components/EvidenceGallery';
import VideoSampleStrip from '../../../components/VideoSampleStrip';
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
    getCentre(id).then(setCentre).catch(()=>setCentre(null));
  },[id]);

  useEffect(()=>{
    fetch(`${API}/api/demo/infrastructure?profile=${encodeURIComponent(profile)}`)
      .then(r=>r.json())
      .then(p=>setManifest(p.items||[]))
      .catch(()=>{});
  },[profile]);

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
        <a className="secondaryBtn" href={'/centres/'+id+'/history'}>Recent Analysis</a>
        <button form="infra-form" className="primaryBtn" disabled={busy}>{busy?'Analysing…':'Analyse Infrastructure'}</button>
      </>}
    />
    <WorkflowStepper centreId={id} states={withRunningStep(centre,'infrastructure',busy,result?(result.created?'attention':'complete'):undefined)}/>
    {error&&<div className="inlineError">{error}</div>}

    <div className="infrastructureLayout">
      <form id="infra-form" className="infraMediaPanel" onSubmit={analyse}>
        <VideoWorkspace preview={preview} inputName="file" onFile={onFile} label="Infrastructure camera" badge={preview?'Recorded clip':'No feed'}/>
        <VideoSampleStrip file={file} count={4}/>
        <div className="infraSetupCard">
          <div>
            <span>Demo evidence profile</span>
            <select value={profile} onChange={e=>setProfile(e.target.value)}>
              <option value="compliant">Compliant demo telemetry</option>
              <option value="discrepancy">Discrepancy demo telemetry</option>
            </select>
          </div>
          <p>The selected profile controls the stage-safe detector telemetry shown before analysis, so the preview never contradicts the profile you are about to run. The uploaded video supplies the review frame and optional visual-motion evidence.</p>
        </div>
      </form>

      <div className="infraResultsColumn">
        <div className="infraTierGrid">
          <TierCard title="Camera-Verifiable Assets" icon="▣" tone="good" items={tier('camera_verifiable')}/>
          <TierCard title="Partially Verifiable Assets" icon="◉" tone="warn" items={tier('camera_partially_verifiable')}/>
          <TierCard title="Officer-Only Assets" icon="◆" tone="info" items={tier('officer_verification_required')}/>
        </div>

        {result&&<div className="infraInlineOutcome">
          <OutcomeCard
            tone={result.created?'danger':'good'}
            title={result.created?'Infrastructure item not detected':'Infrastructure profile completed without a persistent exception'}
            text={result.case?.summary||result.banner}
          />
          <div className="infraEvidenceSource">
            <span>Observation source</span>
            <b>{result.case?.details?.observation_source||'stage-safe detector adapter'}</b>
            <small>Uploaded video supplies the retained review frame; equipment counts currently come from the declared detector adapter/profile.</small>
          </div>
        </div>}
        {result.created&&result.case?.evidence?.length>0&&<EvidenceGallery evidence={result.case.evidence} title="Infrastructure evidence" compact/>}
      </div>

      <AssistantPanel centreId={id}/>
    </div>
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
