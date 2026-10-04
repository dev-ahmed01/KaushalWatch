'use client';

import { ChangeEvent, FormEvent, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import EvidenceGallery from '../../../components/EvidenceGallery';
import VideoWorkspace from '../../../components/VideoWorkspace';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { API, getCentre } from '../../../lib/api';
import type { Centre } from '../../../lib/types';
import { withRunningStep } from '../../../lib/workflow';
import { OutcomeCard, PageHeader, Status } from '../../../components/Ui';

export default function PracticalVerification(){
  const {centreId}=useParams<{centreId:string}>();
  const id=String(centreId);
  const [file,setFile]=useState<File|null>(null);
  const [zonesFile,setZonesFile]=useState<File|null>(null);
  const [preview,setPreview]=useState('');
  const [authorization,setAuthorization]=useState('valid');
  const [profile,setProfile]=useState('authorized');
  const [result,setResult]=useState<any>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [centre,setCentre]=useState<Centre|null>(null);
  const [zoneConfig,setZoneConfig]=useState<any>({reference:{width:1920,height:1080},zones:[]});
  useEffect(()=>{getCentre(id).then(setCentre).catch(()=>setCentre(null));},[id]);

  useEffect(()=>{
    if(zonesFile) return;
    fetch(`${API}/api/practical-work-zones?profile=${encodeURIComponent(profile)}`)
      .then(response=>response.json())
      .then(payload=>setZoneConfig(payload))
      .catch(()=>setZoneConfig({reference:{width:1920,height:1080},zones:[]}));
  },[profile,zonesFile]);

  function onFile(e:ChangeEvent<HTMLInputElement>){
    const next=e.target.files?.[0]||null;
    setFile(next);
    setPreview(next?URL.createObjectURL(next):'');
  }

  async function onZonesFile(e:ChangeEvent<HTMLInputElement>){
    const next=e.target.files?.[0]||null;
    setZonesFile(next);
    if(!next) return;
    try{
      const parsed=JSON.parse(await next.text());
      const reference=parsed?._reference||{width:1920,height:1080};
      const zones=Array.isArray(parsed)?parsed:Array.isArray(parsed?.zones)?parsed.zones:Array.isArray(parsed?.[profile])?parsed[profile]:[];
      setZoneConfig({reference,zones,profile:'custom'});
      setError('');
    }catch{
      setError('Custom work-zone JSON could not be parsed.');
    }
  }

  async function analyse(e:FormEvent){
    e.preventDefault();
    if(!file){setError('Choose a CCTV clip before starting practical-work analysis.');return;}
    setBusy(true);setError('');setResult(null);
    const body=new FormData();
    body.append('file',file);
    body.append('authorization',authorization);
    body.append('zone_profile',profile);
    body.append('centre_id',id);
    body.append('batch_id','ELEC-2026-08');
    body.append('camera_id','LAB-CAM-03');
    if(zonesFile) body.append('zones_json',await zonesFile.text());
    try{
      const response=await fetch(`${API}/api/process-practical-activity`,{method:'POST',body});
      const payload=await response.json();
      if(!response.ok) throw new Error(payload.detail||'Practical-work analysis failed');
      setResult(payload);
    }catch(err:any){setError(err.message||'Practical-work analysis failed');}
    finally{setBusy(false);}
  }

  return <div className="pageScene fadeIn">
    <PageHeader
      eyebrow="Selected Centre / Practical Work"
      title="Practical Work Verification"
      subtitle="Verify sustained worker activity in configured work cells, then compare it with external training authorization."
      actions={<><a className="secondaryBtn" href={`/centres/${id}/history`}>Recent Analysis</a><button form="practical-form" className="primaryBtn" disabled={busy}>{busy?'Analysing…':'Analyse Practical Work'}</button></>}
    />
    <WorkflowStepper centreId={id} states={withRunningStep(centre,'practical',busy,result?(['camera_evidence_insufficient','detector_unavailable'].includes(result.decision)?'blocked':result.case?'attention':'complete'):undefined)}/>
    {error&&<div className="inlineError">{error}</div>}

    <div className="analysisThreeCol">
      <form id="practical-form" className="analysisPrimary" onSubmit={analyse}>
        <VideoWorkspace
          preview={preview}
          inputName="file"
          onFile={onFile}
          label="Workshop camera · work-cell overlay"
          badge={preview?'Zones overlaid':'No feed'}
          overlay={<WorkZoneOverlay config={zoneConfig} result={result}/>}
        />
        <div className="workZoneStrip">
          {(result?.work_cells||[{zone_id:'Work Zone A'},{zone_id:'Work Zone B'},{zone_id:'Work Zone C'}]).slice(0,3).map((cell:any)=><div className="zoneMini" key={cell.zone_id}>
            <span className={cell.activity_fraction>0.3?'zoneDot active':'zoneDot'}></span>
            <div><b>{String(cell.zone_id).replaceAll('_',' ')}</b><small>{result?`${Math.round((cell.activity_fraction||0)*100)}% activity`:'Awaiting analysis'}</small></div>
          </div>)}
        </div>
      </form>

      <section className="analysisResultsPanel">
        <div className="resultPanelHead"><h2>Verification Results</h2>{result&&<Status tone={result.decision==='detector_unavailable'||result.decision==='camera_evidence_insufficient'?'danger':result.case?'warn':'good'}>{result.decision==='detector_unavailable'?'Blocked':result.decision==='camera_evidence_insufficient'?'Blocked':result.case?'Needs review':'Compliant'}</Status>}</div>
        <div className="resultNumberGrid">
          <div><span>Authorized Activities</span><strong>{result?.decision==='authorized_practical_activity'?result.active_work_cells:0}</strong></div>
          <div><span>Unauthorized Activities</span><strong>{result?.decision==='unauthorized_practical_activity'?result.active_work_cells:0}</strong></div>
          <div><span>Active Work Zones</span><b>{result?.active_work_cells??'—'}</b></div>
          <div><span>First Activity</span><b>{result?.first_practical_activity_time_sec==null?'—':`${result.first_practical_activity_time_sec.toFixed(1)}s`}</b></div>
          <div><span>Peak Stable Workers</span><b>{result?.peak_stable_workers??'—'}</b></div>
          <div><span>Trusted Imagery</span><b>{result?`${Math.round((result.trusted_frame_ratio||0)*100)}%`:'—'}</b></div>
          <div><span>Detector</span><b>{result?.detector_backend||'—'}</b></div>
          <div><span>Detector authority</span><b>{result?result.detector_authoritative?'Authoritative':'Decision withheld':'—'}</b></div>
        </div>
        {result&&<OutcomeCard
          tone={result.decision==='detector_unavailable'||result.decision==='camera_evidence_insufficient'?'blocked':result.case?'warn':'good'}
          title={result.decision==='authorized_practical_activity'?'Authorized practical work detected':result.decision==='detector_unavailable'?'Primary detector unavailable — activity shown, decision withheld':String(result.decision).replaceAll('_',' ')}
          text={result.case?.summary||result.detector_message||'Visual activity stayed within the supplied authorization state.'}
        />}
        {result?.case?.evidence?.length>0&&<EvidenceGallery evidence={result.case.evidence} title="Practical-work evidence" compact/>}
        {!result&&<div className="resultEmpty"><span>⌁</span><b>No analysis yet</b><p>The system confirms stable worker presence and local motion before calling a work cell active.</p></div>}

        <div className="practicalSetup">
          <span className="setupLabel">Authorization source</span>
          <div className="segmentedChoice">
            <button type="button" className={authorization==='valid'?'active good':''} onClick={()=>setAuthorization('valid')}>✓ Valid</button>
            <button type="button" className={authorization==='absent'?'active danger':''} onClick={()=>setAuthorization('absent')}>! Not found</button>
            <button type="button" className={authorization==='unknown'?'active warn':''} onClick={()=>setAuthorization('unknown')}>? Unknown</button>
          </div>
          <details className="advancedCompact">
            <summary>Advanced setup</summary>
            <label><span>Bundled work-zone profile</span><select value={profile} onChange={e=>setProfile(e.target.value)}><option value="authorized">Authorized demo layout</option><option value="unauthorized">Unauthorized demo layout</option><option value="default">Default layout</option></select></label>
            <label className="optionalFile"><span>Work-zone JSON · optional override</span><input type="file" accept=".json,application/json" onChange={onZonesFile}/></label>
          </details>
        </div>
      </section>

      <AssistantPanel centreId={id}/>
    </div>
  </div>;
}


function WorkZoneOverlay({config,result}:{config:any;result:any}){
  const reference=config?.reference||{width:1920,height:1080};
  const width=Number(reference.width)||1920;
  const height=Number(reference.height)||1080;
  const cells=new Map((result?.work_cells||[]).map((cell:any)=>[cell.zone_id,cell]));
  return <>{(config?.zones||[]).map((zone:any,index:number)=>{
    const id=String(zone.zone_id||'work_zone_'+String(index+1));
    const cell:any=cells.get(id);
    const active=Boolean(cell&&(cell.activity_fraction||0)>0);
    return <div
      key={id}
      className={active?'workZoneBox active':'workZoneBox'}
      style={{
        left:(Number(zone.x)/width*100)+'%',
        top:(Number(zone.y)/height*100)+'%',
        width:(Number(zone.w)/width*100)+'%',
        height:(Number(zone.h)/height*100)+'%',
      }}
    >
      <span>{id.replaceAll('_',' ')}</span>
      {cell&&<b>{Math.round((cell.activity_fraction||0)*100)}% activity</b>}
    </div>;
  })}</>;
}
