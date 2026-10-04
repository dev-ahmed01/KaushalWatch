'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import { getCentre } from '../../../lib/api';
import type { Centre } from '../../../lib/types';
import { workflowStatesForCentre } from '../../../lib/workflow';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { PageHeader, Status } from '../../../components/Ui';

export default function AnalysisRun(){
  const {centreId}=useParams<{centreId:string}>();
  const id=String(centreId);
  const [centre,setCentre]=useState<Centre|null>(null);
  useEffect(()=>{getCentre(id).then(setCentre).catch(()=>setCentre(null));},[id]);

  const states=workflowStatesForCentre(centre);
  const automatic=(centre?.settings as any)?.automatic_analysis!==false;

  return <div className="pageScene fadeIn">
    <PageHeader
      eyebrow="Selected Centre / Analysis"
      title="Centre Analysis"
      subtitle="Run the three verification checkpoints manually, or let the scheduled edge workflow process them automatically."
      actions={<>
        <Link href={'/centres/'+id+'/history'} className="secondaryBtn">Recent Analysis</Link>
        <Status tone={automatic?'good':'neutral'}>{automatic?'Automatic schedule on':'Manual mode'}</Status>
      </>}
    />

    <WorkflowStepper centreId={id} states={states}/>

    <div className="analysisLaunchGrid">
      <section className="panel analysisLaunchPanel">
        <div className="analysisLaunchHero">
          <span className="analysisLaunchOrb">▶</span>
          <div><span className="sectionKicker">Manual walkthrough</span><h2>Start with the evidence you have</h2><p>Each checkpoint can complete, raise attention, or abstain independently. Nothing is forced into a pass/fail result when the evidence is unreliable.</p></div>
        </div>

        <div className="analysisLaunchSteps">
          <LaunchStep number="1" title="Attendance" text="Stable anonymous occupancy vs submitted attendance." href={'/centres/'+id+'/attendance'} tone="blue"/>
          <LaunchStep number="2" title="Practical Work" text="Persistent work-cell activity + external authorization." href={'/centres/'+id+'/practical'} tone="green"/>
          <LaunchStep number="3" title="Infrastructure" text="Camera-verifiable, partial, and officer-only manifest." href={'/centres/'+id+'/infrastructure'} tone="amber"/>
          <LaunchStep number="4" title="Review Outcome" text="Human decision, escalation and evidence audit." href={'/centres/'+id+'/outcome'} tone="slate"/>
        </div>

        <div className="analysisModeNote">
          <span>ⓘ</span>
          <div><b>Normal operation is automatic.</b><p>Manual Start Analysis remains for demos, rechecks and uploaded footage. Low-bandwidth centres can process locally and sync only summaries plus exception evidence.</p></div>
        </div>
      </section>

      <aside className="analysisLaunchSide">
        <section className="panel runScheduleCard">
          <div className="panelHead"><div><span className="sectionKicker">Schedule</span><h2>Next automatic run</h2></div><Status tone={automatic?'good':'neutral'}>{automatic?'Enabled':'Off'}</Status></div>
          <div className="runScheduleBody">
            <div><span>Frequency</span><b>Every training day</b></div>
            <div><span>Monitoring windows</span><b>09:00–11:00 · 14:00–16:00</b></div>
            <div><span>Connectivity</span><b>{centre?.connectivity_mode?.replaceAll('_',' ')||'normal'}</b></div>
            <div><span>Next run</span><b>Next training window</b></div>
          </div>
        </section>
        <AssistantPanel centreId={id}/>
      </aside>
    </div>
  </div>;
}

function LaunchStep({number,title,text,href,tone}:{number:string;title:string;text:string;href:string;tone:string}){
  return <Link href={href} className={'analysisLaunchStep '+tone}>
    <span>{number}</span>
    <div><b>{title}</b><small>{text}</small></div>
    <em>Open →</em>
  </Link>;
}
