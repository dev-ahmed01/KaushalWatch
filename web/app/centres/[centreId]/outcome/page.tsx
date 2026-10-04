'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { getCentre, getDashboard } from '../../../lib/api';
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

  const pending=dashboard?.open_cases??0;
  const high=(dashboard?.pending_cases||[]).filter((c:any)=>c.severity==='high').length;
  const duplicate=(dashboard?.pending_cases||[]).some((c:any)=>c.evidence?.some((e:any)=>e.duplicate_of));
  const hasAttention=pending>0;

  return <div className="pageScene fadeIn">
    <PageHeader
      eyebrow="Selected Centre / Final Review"
      title="Final Review Outcome"
      subtitle="A single centre-level decision view across attendance, practical work, infrastructure and integrity checks."
      actions={<>
        <Link href={'/centres/'+id+'/review'} className="secondaryBtn">Open Review Queue</Link>
        <Link href={'/reports?centre='+id+'&period=7d'} className="secondaryBtn">Generate Report</Link>
        <Link href={'/centres/'+id} className="primaryBtn">Close Analysis</Link>
      </>}
    />

    <WorkflowStepper centreId={id} states={workflowStatesForCentre(centre)}/>

    <div className="finalOutcomeGrid">
      <section className="finalOutcomeMain">
        <article className={'finalDecisionCard '+(hasAttention?'attention':'good')}>
          <span className="finalDecisionIcon">{hasAttention?'!':'✓'}</span>
          <div>
            <span className="sectionKicker">Centre-level result</span>
            <h2>{hasAttention?'Human review required':'Compliant'}</h2>
            <p>{hasAttention
              ? pending+' pending case(s) still require an officer decision before this review cycle can be closed.'
              : 'All current verification checkpoints completed without an unresolved compliance exception.'}</p>
          </div>
          {centre&&<Status tone={centre.escalation.level>=3?'danger':centre.escalation.level>0?'warn':'good'}>{centre.escalation.label}</Status>}
        </article>

        <section className="pillarDecisionGrid">
          <PillarCard title="Attendance" state={centre?.attendance_status||'compliant'} text="Stable anonymous occupancy vs submitted attendance."/>
          <PillarCard title="Practical Work" state={centre?.practical_status||'compliant'} text="Observed activity + external authorization."/>
          <PillarCard title="Infrastructure" state={centre?.infrastructure_status||'compliant'} text="Three-tier visual compliance manifest."/>
          <PillarCard title="Camera Integrity" state={centre?.camera_status||'nominal'} text="Image trust gate before any visual conclusion."/>
          <PillarCard title="Evidence Integrity" state={duplicate?'attention':'compliant'} text="Independent duplicate-evidence signal."/>
        </section>

        <section className="panel nextActionsCard">
          <div className="panelHead"><div><span className="sectionKicker">What happens next</span><h2>Officer actions</h2></div></div>
          <div className="nextActionGrid">
            <div><span>Pending review</span><b>{pending}</b><small>Evidence-backed cases awaiting action</small></div>
            <div><span>High priority</span><b>{high}</b><small>Urgent review items</small></div>
            <div><span>Escalation</span><b>{centre?.escalation.label||'Normal'}</b><small>{centre?.escalation.reasons?.[0]||'No escalation trigger'}</small></div>
          </div>
          <div className="finalActionRow">
            <Link href={'/centres/'+id+'/review'} className="primaryBtn">{pending?'Review pending cases':'View review history'}</Link>
            <Link href={'/reports?centre='+id+'&period=7d'} className="secondaryBtn">Create 7-day report</Link>
            <Link href={'/centres/'+id+'/history'} className="secondaryBtn">Open analysis history</Link>
          </div>
        </section>
      </section>

      <aside className="finalOutcomeSide">
        <AssistantPanel centreId={id}/>
      </aside>
    </div>
  </div>;
}

function PillarCard({title,state,text}:{title:string;state:string;text:string}){
  const attention=!['compliant','nominal','clear'].includes(state);
  return <article className={'pillarDecision '+(attention?'attention':'good')}>
    <span>{attention?'!':'✓'}</span>
    <div><b>{title}</b><p>{text}</p></div>
    <em>{state.replaceAll('_',' ')}</em>
  </article>;
}
