'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { getCentre, getDashboard } from '../../../lib/api';
import type { Centre } from '../../../lib/types';
import { PageHeader, Status } from '../../../components/Ui';

export default function FinalOutcome(){
  const {centreId}=useParams<{centreId:string}>();
  const id=String(centreId);
  const [centre,setCentre]=useState<Centre|null>(null);
  const [dashboard,setDashboard]=useState<any>(null);

  useEffect(()=>{
    Promise.all([getCentre(id),getDashboard(id)])
      .then(([c,d])=>{setCentre(c);setDashboard(d);})
      .catch(()=>{});
  },[id]);

  const pending=dashboard?.open_cases??0;
  const high=(dashboard?.pending_cases||[]).filter((c:any)=>c.severity==='high').length;
  const hasAttention=pending>0;

  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Selected Centre / Final Review" title="Final Review Outcome" subtitle="One centre-level summary across attendance, practical work, infrastructure, camera integrity and evidence integrity."
      actions={<><Link href={`/centres/${id}/review`} className="secondaryBtn">Open Review Queue</Link><Link href={`/reports?centre=${id}&period=7d`} className="secondaryBtn">Download / Print Report</Link><Link href={`/centres/${id}`} className="primaryBtn">Close Analysis</Link></>}/>
    <WorkflowStepper centreId={id} states={{attendance:'complete',practical:'complete',infrastructure:centre?.infrastructure_status==='compliant'?'complete':'attention',review:hasAttention?'attention':'complete'}}/>

    <div className="outcomeLayout">
      <section className={`finalOutcomeHero ${hasAttention?'attention':'good'}`}>
        <div className="finalOutcomeIcon">{hasAttention?'!':'✓'}</div>
        <div>
          <span className="sectionKicker">Centre-level result</span>
          <h2>{hasAttention?'Human review required':'Compliant'}</h2>
          <p>{hasAttention?`${pending} pending case(s) still require an officer decision before this centre can be closed for the current review cycle.`:'All current verification checkpoints completed without an unresolved compliance exception.'}</p>
        </div>
        {centre&&<Status tone={centre.escalation.level>=3?'danger':centre.escalation.level>0?'warn':'good'}>{centre.escalation.label}</Status>}
      </section>

      <div className="outcomeContent">
        <section className="panel pillarSummary">
          <div className="panelHead"><div><span className="sectionKicker">Verification pillars</span><h2>What each checkpoint concluded</h2></div></div>
          <div className="pillarRows">
            <PillarRow title="Attendance" state={centre?.attendance_status||'compliant'} text="Stable anonymous occupancy compared with centre-reported attendance."/>
            <PillarRow title="Practical Work" state={centre?.practical_status||'compliant'} text="Persistent worker-centric motion combined with external authorization."/>
            <PillarRow title="Infrastructure" state={centre?.infrastructure_status||'compliant'} text="Camera-verifiable, partially verifiable and officer-only manifest items."/>
            <PillarRow title="Camera Integrity" state={centre?.camera_status||'nominal'} text="Poor imagery suspends affected conclusions instead of creating false certainty."/>
            <PillarRow title="Evidence Integrity" state={(dashboard?.pending_cases||[]).some((c:any)=>c.evidence?.some((e:any)=>e.duplicate_of))?'attention':'compliant'} text="Duplicate-evidence checks remain an independent integrity signal."/>
          </div>
        </section>

        <section className="panel outcomeActions">
          <div className="panelHead"><div><span className="sectionKicker">Officer actions</span><h2>What happens next</h2></div></div>
          <div className="outcomeActionRows">
            <div><span>Pending review</span><b>{pending}</b><small>Evidence-backed cases awaiting action</small></div>
            <div><span>High priority</span><b>{high}</b><small>Cases requiring urgent review</small></div>
            <div><span>Escalation</span><b>{centre?.escalation.label||'Normal'}</b><small>{centre?.escalation.reasons?.[0]||'No escalation trigger'}</small></div>
          </div>
          <Link href={`/centres/${id}/review`} className="primaryBtn fullBtn">{pending?'Review pending cases':'View audit history'}</Link>
        </section>

        <AssistantPanel centreId={id}/>
      </div>
    </div>
  </div>;
}

function PillarRow({title,state,text}:{title:string;state:string;text:string}){
  const attention=!['compliant','nominal'].includes(state);
  return <div className="pillarRow">
    <span className={attention?'pillarState warn':'pillarState good'}>{attention?'!':'✓'}</span>
    <div><b>{title}</b><small>{text}</small></div>
    <Status tone={attention?'warn':'good'}>{state.replaceAll('_',' ')}</Status>
  </div>;
}
