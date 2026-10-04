'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { getCentre } from '../../lib/api';
import type { Centre } from '../../lib/types';
import { workflowStatesForCentre } from '../../lib/workflow';
import AssistantPanel from '../../components/AssistantPanel';
import WorkflowStepper from '../../components/WorkflowStepper';
import { PageHeader, Status, Skeleton } from '../../components/Ui';

export default function CentreOverview(){
  const params=useParams<{centreId:string}>();
  const centreId=String(params.centreId);
  const [centre,setCentre]=useState<Centre|null>(null);
  useEffect(()=>{getCentre(centreId).then(setCentre).catch(()=>setCentre(null));},[centreId]);

  const stepStates=useMemo(()=>workflowStatesForCentre(centre),[centre]);

  if(!centre) return <div className="pageScene"><Skeleton lines={8}/></div>;

  return <div className="pageScene fadeIn">
    <PageHeader
      eyebrow="Selected Centre"
      title={centre.name}
      subtitle={`${centre.location} · Batch ${centre.batch_id} · ${centre.job_role}`}
      actions={<>
        <Link href={`/centres/${centreId}/history`} className="secondaryBtn">Recent Analysis</Link>
        <Link href={`/reports?centre=${centreId}`} className="secondaryBtn">Generate Report</Link>
        <Link href={`/centres/${centreId}/analysis`} className="primaryBtn">Start Analysis</Link>
      </>}
    />

    <WorkflowStepper centreId={centreId} states={stepStates}/>

    <div className="centreLayout">
      <div className="centreMain">
        <section className="overviewCards">
          <div className="panel centreIdentityCard">
            <div className="centreIllustration"><div className="buildingGlyph">▥</div><span>No centre photo required</span></div>
            <div><Status tone={centre.status==='compliant'?'good':centre.status==='high_priority'?'danger':'warn'}>{centre.status.replace('_',' ')}</Status><h2>{centre.name}</h2><p>{centre.job_role}</p>
              <div className="identityFacts"><span>⌖ {centre.district}</span><span>◫ {centre.batch_id}</span><span>♙ {centre.trainees} enrolled trainees</span></div>
            </div>
          </div>

          <div className="panel scheduleCard">
            <div className="panelHead"><div><span className="sectionKicker">Analysis Schedule</span><h2>Automatic monitoring</h2></div><Status tone={(centre.settings as any)?.automatic_analysis===false?'neutral':'good'}>{(centre.settings as any)?.automatic_analysis===false?'Manual':'Automatic'}</Status></div>
            <div className="scheduleRows">
              <div><span>Frequency</span><b>Every training day</b></div>
              <div><span>Monitoring windows</span><b>09:00–11:00 · 14:00–16:00</b></div>
              <div><span>Connectivity</span><b>{centre.connectivity_mode.replace('_',' ')}</b></div>
              <div><span>Next run</span><b>Next training window</b></div>
            </div>
            <Link href={`/centres/${centreId}/analysis`} className="runNowBtn">▶ Run analysis now</Link>
          </div>
        </section>

        <section className="panel verificationSummary">
          <div className="panelHead"><div><span className="sectionKicker">Verification status</span><h2>Current centre picture</h2></div><Link href={`/centres/${centreId}/review`}>Open review →</Link></div>
          <div className="verificationRows">
            <div><span className="verifyIcon good">✓</span><b>Attendance</b><Status tone={centre.attendance_status==='compliant'?'good':'warn'}>{centre.attendance_status}</Status><small>Aggregate presence only</small></div>
            <div><span className="verifyIcon good">✓</span><b>Practical Work</b><Status tone={centre.practical_status==='compliant'?'good':'warn'}>{centre.practical_status}</Status><small>Activity + external authorization</small></div>
            <div><span className={`verifyIcon ${centre.infrastructure_status==='compliant'?'good':'warn'}`}>{centre.infrastructure_status==='compliant'?'✓':'!'}</span><b>Infrastructure</b><Status tone={centre.infrastructure_status==='compliant'?'good':'warn'}>{centre.infrastructure_status}</Status><small>Three verification tiers</small></div>
            <div><span className={`verifyIcon ${centre.camera_status==='nominal'?'good':'warn'}`}>{centre.camera_status==='nominal'?'✓':'!'}</span><b>Camera Integrity</b><Status tone={centre.camera_status==='nominal'?'good':'warn'}>{centre.camera_status}</Status><small>Inference suspends on poor imagery</small></div>
          </div>
        </section>

        <section className="panel recentActivity">
          <div className="panelHead"><div><span className="sectionKicker">Recent Analysis</span><h2>What happened recently</h2></div><Link href={`/centres/${centreId}/history`}>Full history →</Link></div>
          <div className="activityTimeline">
            {(centre.recent_analyses||[]).length===0&&<div className="calmState">No recorded analysis yet. Start one when you are ready.</div>}
            {(centre.recent_analyses||[]).slice(0,5).map(row=><div className="activityItem" key={row.analysis_id}><span className={row.outcome}></span><div><b>{row.analysis_type.replace('_',' ')}</b><p>{row.summary}</p><small>{new Date(row.created_at).toLocaleString()}</small></div></div>)}
          </div>
        </section>
      </div>

      <div className="centreSide">
        <section className="centrePulseCard">
          <div className="centrePulseHead">
            <span className="aiPulseIcon">✦</span>
            <div><span className="sectionKicker">AI summary</span><h2>Centre pulse</h2></div>
          </div>
          <p className="centrePulseSummary">
            {centre.status==='compliant'
              ? 'All current verification pillars are clear. No unresolved exception is blocking this centre.'
              : centre.status==='high_priority'
                ? `This centre needs priority attention. ${centre.pending_cases} case(s) remain unresolved and the escalation policy has been triggered.`
                : `${centre.pending_cases} evidence-backed case(s) still need officer review before the current cycle can be closed.`}
          </p>
          <div className="centrePulseFacts">
            <div><span>Pending</span><b>{centre.pending_cases}</b></div>
            <div><span>Connectivity</span><b>{centre.connectivity_mode.replace('_',' ')}</b></div>
            <div><span>Camera</span><b>{centre.camera_status}</b></div>
          </div>
          <div className={`pulseEscalation level${centre.escalation.level}`}>
            <div><span>Escalation</span><strong>{centre.escalation.label}</strong></div>
            <p>{centre.escalation.reasons[0]}</p>
            <small>{centre.escalation.next_action}</small>
            <Link href="/escalations">View escalation details →</Link>
          </div>
        </section>
        <AssistantPanel centreId={centreId}/>
      </div>
    </div>
  </div>;
}
