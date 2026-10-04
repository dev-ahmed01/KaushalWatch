'use client';

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import EvidenceGallery from '../../../components/EvidenceGallery';
import VideoWorkspace from '../../../components/VideoWorkspace';
import VideoSampleStrip from '../../../components/VideoSampleStrip';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { API, getCentre } from '../../../lib/api';
import type { Centre } from '../../../lib/types';
import { withRunningStep } from '../../../lib/workflow';
import { OutcomeCard, PageHeader, Status } from '../../../components/Ui';

export default function AttendanceVerification(){
  const {centreId}=useParams<{centreId:string}>();
  const id=String(centreId);
  const [file,setFile]=useState<File|null>(null);
  const [preview,setPreview]=useState('');
  const [reported,setReported]=useState(3);
  const [cameraId,setCameraId]=useState('LAB-CAM-01');
  const [result,setResult]=useState<any>(null);
  const [videoTime,setVideoTime]=useState(0);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [centre,setCentre]=useState<Centre|null>(null);
  useEffect(()=>{getCentre(id).then(setCentre).catch(()=>setCentre(null));},[id]);

  function onFile(e:ChangeEvent<HTMLInputElement>){
    const next=e.target.files?.[0]||null;
    setFile(next);
    setPreview(next?URL.createObjectURL(next):'');
  }

  async function analyse(e:FormEvent){
    e.preventDefault();
    if(!file){setError('Choose a CCTV clip before starting attendance analysis.');return;}
    setBusy(true);setError('');setResult(null);
    const body=new FormData();
    body.append('file',file);
    body.append('reported_attendance',String(reported));
    body.append('centre_id',id);
    body.append('batch_id','ELEC-2026-08');
    body.append('camera_id',cameraId);
    try{
      const response=await fetch(`${API}/api/process-video`,{method:'POST',body});
      const payload=await response.json();
      if(!response.ok) throw new Error(payload.detail||'Attendance analysis failed');
      setResult(payload);
    }catch(err:any){setError(err.message||'Attendance analysis failed');}
    finally{setBusy(false);}
  }

  const authoritative=result?.detector_authoritative;
  const tone=result?.decision==='compliant'?'good':result?.decision==='attendance_exception'?'danger':'warn';
  const overlaySample=useMemo(()=>{
    const samples=(result?.overlay_samples||[]) as any[];
    if(!samples.length) return null;
    let best=samples[0];
    let distance=Math.abs(Number(best.second||0)-videoTime);
    for(const sample of samples){
      const nextDistance=Math.abs(Number(sample.second||0)-videoTime);
      if(nextDistance<distance){best=sample;distance=nextDistance;}
    }
    return distance<=1.1?best:null;
  },[result,videoTime]);

  return <div className="pageScene fadeIn">
    <PageHeader
      eyebrow="Selected Centre / Attendance"
      title="Attendance Verification"
      subtitle="Estimate stable physical presence and compare it with the centre’s reported attendance — without facial identification."
      actions={<><a className="secondaryBtn" href={`/centres/${id}/history`}>Recent Analysis</a><button form="attendance-form" className="primaryBtn" disabled={busy}>{busy?'Analysing…':'Analyse Attendance'}</button></>}
    />
    <WorkflowStepper centreId={id} states={withRunningStep(centre,'attendance',busy,result?(result.decision==='compliant'?'complete':result.decision==='detector_unavailable'?'blocked':'attention'):undefined)}/>
    {error&&<div className="inlineError">{error}</div>}

    <div className="analysisThreeCol">
      <form id="attendance-form" className="analysisPrimary" onSubmit={analyse}>
        <VideoWorkspace
          preview={preview}
          inputName="file"
          onFile={onFile}
          onTimeChange={setVideoTime}
          label="CAM 01 · Training Lab"
          badge={result?(authoritative?'Verified overlay':'Diagnostic overlay'):preview?'Recorded clip':'No feed'}
          overlay={result&&overlaySample?<AttendanceOverlay sample={overlaySample} authoritative={Boolean(authoritative)}/>:undefined}
        />
        <VideoSampleStrip file={file}/>
      </form>

      <section className="analysisResultsPanel">
        <div className="resultPanelHead"><h2>Detection Results</h2>{result&&<Status tone={tone as any}>{result.decision?.replaceAll('_',' ')}</Status>}</div>
        <div className="resultNumberGrid">
          <div><span>Detected People</span><strong>{authoritative?result?.estimated_occupancy??'—':'—'}</strong></div>
          <div><span>Reported Attendance</span><strong>{reported}</strong></div>
          <div><span>Detector Backend</span><b>{result?.detector_backend||'YOLO11 / checking'}</b></div>
          <div><span>Trusted Samples</span><b>{result?`${Math.round((result.trusted_sample_ratio||0)*100)}%`:'—'}</b></div>
          <div><span>Frames Analysed</span><b>{result?.frames_sampled??'—'}</b></div>
          <div><span>Mismatch</span><b>{result?.discrepancy_pct==null?'—':`${result.discrepancy_pct}%`}</b></div>
        </div>
        {result&&<OutcomeCard
          tone={result.decision==='compliant'?'good':result.decision==='detector_unavailable'?'blocked':result.decision==='attendance_exception'?'danger':'warn'}
          title={result.decision==='compliant'?'Attendance matches reported count':result.decision==='detector_unavailable'?'Detector unavailable — decision withheld':'Attendance needs review'}
          text={result.case?.summary||result.detector_message||'Attendance analysis completed.'}
        />}
        {result?.case?.evidence?.length>0&&<EvidenceGallery evidence={result.case.evidence} title="Attendance evidence" compact/>}
        {!result&&<div className="resultEmpty"><span>◎</span><b>No analysis yet</b><p>Choose a clip, confirm the reported count, then start analysis.</p></div>}

        <div className="attendanceSetup">
          <div className="attendanceCountControl">
            <span>Centre-reported attendance</span>
            <div><button type="button" onClick={()=>setReported(Math.max(0,reported-1))}>−</button><strong>{reported}</strong><button type="button" onClick={()=>setReported(reported+1)}>+</button></div>
          </div>
          <div className="quickPresets"><button type="button" onClick={()=>setReported(3)}>Demo match · 3</button><button type="button" onClick={()=>setReported(12)}>Demo mismatch · 12</button></div>
          <details className="advancedCompact">
            <summary>Advanced setup</summary>
            <label><span>Camera ID</span><input value={cameraId} onChange={e=>setCameraId(e.target.value)}/></label>
          </details>
        </div>

        <div className="privacyCallout">✓ Anonymous stable occupancy · no facial identification · overlay IDs are temporary in-stream track labels, not identities · detector failure is shown as unavailable, never as a real zero.</div>
      </section>

      <AssistantPanel centreId={id}/>
    </div>
  </div>;
}


function AttendanceOverlay({sample,authoritative}:{sample:any;authoritative:boolean}){
  const width=Math.max(1,Number(sample.frame_width)||1);
  const height=Math.max(1,Number(sample.frame_height)||1);
  return <div className="attendanceOverlay">
    <div className={authoritative?'overlayMode authoritative':'overlayMode diagnostic'}>
      {authoritative?'Anonymous occupancy overlay':'Diagnostic detector overlay · decision withheld'}
    </div>
    {(sample.boxes||[]).map((box:any)=>{
      const status=String(box.status||'candidate');
      return <div
        key={String(box.track_id)}
        className={'attendanceBox '+status+(authoritative?'':' diagnostic')}
        style={{
          left:(Number(box.x1)/width*100)+'%',
          top:(Number(box.y1)/height*100)+'%',
          width:((Number(box.x2)-Number(box.x1))/width*100)+'%',
          height:((Number(box.y2)-Number(box.y1))/height*100)+'%',
        }}
      >
        <span>Anon {String(box.track_id).padStart(2,'0')}</span>
        <b>{status}</b>
      </div>;
    })}
    <div className="overlayTimestamp">{Number(sample.second||0).toFixed(1)}s · {sample.trusted?'camera trusted':'camera trust warning'}</div>
  </div>;
}
