'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { getCentre, getDashboard, reportPdfUrl } from '../../../lib/api';
import type { Centre } from '../../../lib/types';
import { workflowStatesForCentre } from '../../../lib/workflow';
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

  const states=useMemo(()=>workflowStatesForCentre(centre),[centre]);
  const pending=dashboard?.open_cases??0;
  const high=(dashboard?.pending_cases||[]).filter((c:any)=>c.severity==='high').length;
  const checkpointStates=[states.attendance,states.practical,states.infrastructure];
  const hasBlocked=checkpointStates.includes('blocked');
  const hasPending=checkpointStates.some(state=>state==='pending'||state==='running');
  const hasAttention=pending>0||checkpointStates.includes('attention');

  const outcome=hasAttention
    ? {title:'Human review required',tone:'attention',icon:'!',text:`${pending} pending case(s) still require an officer decision before this centre can be closed for the current review cycle.`}
    : hasBlocked
      ? {title:'Verification blocked',tone:'incomplete',icon:'×',text:'At least one verification ran without authoritative evidence. Re-run that checkpoint after restoring the required detector or camera quality.'}
      : hasPending
        ? {title:'Verification incomplete',tone:'incomplete',icon:'…',text:'One or more verification checkpoints have not been run yet. No centre-level compliance conclusion has been issued.'}
        : {title:'Compliant',tone:'good',icon:'✓',text:'All current verification checkpoints completed without an unresolved compliance exception.'};

  const escalationTone=centre?.escalation.level>=3?'danger':centre?.escalation.level>0?'warn':centre?.status==='incomplete'?'neutral':'good';

  return <div className="pageScene fadeIn">
    <PageHeader
      eyebrow="Selected Centre / Final Review"
      title="Final Review Outcome"
      subtitle="One centre-level summary across attendance, practical work, infrastructure, camera integrity and evidence integrity."
      actions={<>
        <Link href={`/centres/${id}/review`} className="secondaryBtn">Open Review Queue</Link>
        <a href={reportPdfUrl(id,'7d')} className="secondaryBtn">Download PDF</a>
        <Link href={`/centres/${id}`} className="primaryBtn">Close Analysis</Link>
      </>}
    />
    <WorkflowStepper centreId={id} states={states}/>

    <div className="outcomeLayout">
      <section className={`finalOutcomeHero ${outcome.tone}`}>
        <div className="finalOutcomeIcon">{outcome.icon}</div>
        <div>
          <span className="sectionKicker">Centre-level result</span>
          <h2>{outcome.title}</h2>
          <p>{outcome.text}</p>
        </div>
        {centre&&<Status tone={escalationTone as any}>{centre.escalation.label}</Status>}
      </section>

      <div className="outcomeContent">
        <section className="panel pillarSummary">
          <div className="panelHead"><div><span className="sectionKicker">Verification pillars</span><h2>What each checkpoint concluded</h2></div></div>
          <div className="pillarRows">
            <PillarRow title="Attendance" state={centre?.attendance_status||'pending'} text="Stable anonymous occupancy compared with centre-reported attendance."/>
            <PillarRow title="Practical Work" state={centre?.practical_status||'pending'} text="Persistent worker-centric motion combined with external authorization."/>
            <PillarRow title="Infrastructure" state={centre?.infrastructure_status||'pending'} text="Camera-verifiable, partially verifiable and officer-only manifest items."/>
            <PillarRow title="Camera Integrity" state={centre?.camera_status||'pending'} text="Poor imagery suspends affected conclusions instead of creating false certainty."/>
            <PillarRow title="Evidence Integrity" state={centre?.evidence_integrity_status||'pending'} text="Duplicate-evidence checks remain an independent integrity signal."/>
          </div>
        </section>

        <section className="panel outcomeActions">
          <div className="panelHead"><div><span className="sectionKicker">Officer actions</span><h2>What happens next</h2></div></div>
          <div className="outcomeActionRows">
            <div><span>Pending review</span><b>{pending}</b><small>Evidence-backed cases awaiting action</small></div>
            <div><span>High priority</span><b>{high}</b><small>Cases requiring urgent review</small></div>
            <div><span>Escalation</span><b>{centre?.escalation.label||'Normal'}</b><small>{centre?.escalation.reasons?.[0]||'No escalation trigger'}</small></div>
          </div>
          {hasAttention
            ? <Link href={`/centres/${id}/review`} className="primaryBtn fullBtn">Review pending cases</Link>
            : (hasPending||hasBlocked)
              ? <Link href={`/centres/${id}/analysis`} className="primaryBtn fullBtn">Continue verification</Link>
              : <Link href={`/centres/${id}/history`} className="primaryBtn fullBtn">View audit history</Link>
          }
        </section>

        <AssistantPanel centreId={id}/>
      </div>
    </div>
  </div>;
}

function PillarRow({title,state,text}:{title:string;state:string;text:string}){
  const normalized=state.toLowerCase();
  const good=['compliant','nominal','clear'].includes(normalized);
  const blocked=normalized==='blocked';
  const pending=normalized==='pending'||normalized==='not_analysed';
  const tone=good?'good':blocked?'danger':pending?'neutral':'warn';
  const symbol=good?'✓':blocked?'×':pending?'•':'!';
  return <div className="pillarRow">
    <span className={`pillarState ${tone}`}>{symbol}</span>
    <div><b>{title}</b><small>{text}</small></div>
    <Status tone={tone as any}>{state.replaceAll('_',' ')}</Status>
  </div>;
}
