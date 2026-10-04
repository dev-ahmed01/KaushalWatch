'use client';

import { ChangeEvent, FormEvent, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import VideoWorkspace from '../../../components/VideoWorkspace';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { API } from '../../../lib/api';
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

  function onFile(e:ChangeEvent<HTMLInputElement>){
    const next=e.target.files?.[0]||null;
    setFile(next);
    setPreview(next?URL.createObjectURL(next):'');
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
      const response=await fetch(\`\${API}/api/process-practical-activity\`,{method:'POST',body});
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
      actions={<><button className="secondaryBtn" type="button">Demo Clip⌄</button><button className="secondaryBtn" type="button">⚙ Advanced Settings</button><button form="practical-form" className="primaryBtn" disabled={busy}>{busy?'Analysing…':'Analyse Practical Work'}</button></>}
    />
    <WorkflowStepper centreId={id} states={{attendance:'complete',practical:busy?'running':result?(result.case?'attention':'complete'):'pending'}}/>
    {error&&<div className="inlineError">{error}</div>}

    <div className="analysisThreeCol">
      <form id="practical-form" className="analysisPrimary" onSubmit={analyse}>
        <VideoWorkspace preview={preview} inputName="file" onFile={onFile} label="Work Zone A · Workshop" badge={preview?'Recorded clip':'No feed'}/>
        <div className="workZoneStrip">
          {(result?.work_cells||[{zone_id:'Work Zone A'},{zone_id:'Work Zone B'},{zone_id:'Work Zone C'}]).slice(0,3).map((cell:any)=><div className="zoneMini" key={cell.zone_id}>
            <span className={cell.activity_fraction>0.3?'zoneDot active':'zoneDot'}></span>
            <div><b>{String(cell.zone_id).replaceAll('_',' ')}</b><small>{result?\`\${Math.round((cell.activity_fraction||0)*100)}% activity\`:'Awaiting analysis'}</small></div>
          </div>)}
        </div>
      </form>

      <section className="analysisResultsPanel">
        <div className="resultPanelHead"><h2>Verification Results</h2>{result&&<Status tone={result.case?'warn':'good'}>{result.case?'Needs review':'Compliant'}</Status>}</div>
        <div className="resultNumberGrid">
          <div><span>Authorized Activities</span><strong>{result?.decision==='authorized_practical_activity'?result.active_work_cells:0}</strong></div>
          <div><span>Unauthorized Activities</span><strong>{result?.decision==='unauthorized_practical_activity'?result.active_work_cells:0}</strong></div>
          <div><span>Active Work Zones</span><b>{result?.active_work_cells??'—'}</b></div>
          <div><span>First Activity</span><b>{result?.first_practical_activity_time_sec==null?'—':\`\${result.first_practical_activity_time_sec.toFixed(1)}s\`}</b></div>
          <div><span>Peak Stable Workers</span><b>{result?.peak_stable_workers??'—'}</b></div>
          <div><span>Trusted Imagery</span><b>{result?\`\${Math.round((result.trusted_frame_ratio||0)*100)}%\`:'—'}</b></div>
        </div>
        {result&&<OutcomeCard
          tone={result.case?'warn':'good'}
          title={result.decision==='authorized_practical_activity'?'Authorized practical work detected':String(result.decision).replaceAll('_',' ')}
          text={result.case?.summary||'Visual activity stayed within the supplied authorization state.'}
        />}
        {!result&&<div className="resultEmpty"><span>⌁</span><b>No analysis yet</b><p>The system confirms stable worker presence and local motion before calling a work cell active.</p></div>}

        <div className="analysisControls">
          <label><span>Authorization source</span><select value={authorization} onChange={e=>setAuthorization(e.target.value)}><option value="valid">Valid authorization</option><option value="absent">Authorization not found</option><option value="unknown">Unknown / officer review</option></select></label>
          <label><span>Bundled work-zone profile</span><select value={profile} onChange={e=>setProfile(e.target.value)}><option value="authorized">Authorized demo layout</option><option value="unauthorized">Unauthorized demo layout</option><option value="default">Default layout</option></select></label>
          <label className="optionalFile"><span>Work-zone JSON · optional override</span><input type="file" accept=".json,application/json" onChange={e=>setZonesFile(e.target.files?.[0]||null)}/></label>
        </div>
      </section>

      <AssistantPanel centreId={id}/>
    </div>
  </div>;
}
