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

  const latest=(centre.recent_analyses||[])[0];
  const attention=centre.pending_cases>0||centre.escalation.level>0;

  return <div className="pageScene fadeIn">
    <PageHeader
      eyebrow="Selected Centre"
      title={centre.name}
      subtitle={centre.location+' · Batch '+centre.batch_id+' · '+centre.job_role}
      actions={<>
        <Link href={'/centres/'+centreId+'/history'} className="secondaryBtn">Recent Analysis</Link>
        <Link href={'/reports?centre='+centreId+'&period=7d'} className="secondaryBtn">Generate Report</Link>
        <Link href={'/centres/'+centreId+'/analysis'} className="primaryBtn">Start Analysis →</Link>
      </>}
    />

    <WorkflowStepper centreId={centreId} states={stepStates}/>

    <div className="centreOverviewGrid">
      <section className="centreOverviewMain">
        <div className="centreTopCards">
          <article className="panel centreProfileCard">
            <div className="centrePhotoEmpty">
              <span>▥</span>
              <b>{centre.name}</b>
              <small>Centre image optional</small>
            </div>
            <div className="centreProfileCopy">
              <div className="centreStatusRow">
                <Status tone={centre.status==='compliant'?'good':centre.status==='high_priority'?'danger':'warn'}>{centre.status.replaceAll('_',' ')}</Status>
                <span>Centre Code · {centre.centre_id}</span>
              </div>
              <h2>{centre.name}</h2>
              <p>{centre.job_role}</p>
              <div className="centreFacts">
                <span>⌖ {centre.district}</span>
                <span>◫ {centre.batch_id}</span>
                <span>♙ {centre.trainees} trainees</span>
              </div>
            </div>
          </article>

          <article className="panel simpleScheduleCard">
            <div className="panelHead">
              <div><span className="sectionKicker">Analysis Schedule</span><h2>Automatic monitoring</h2></div>
              <Status tone={(centre.settings as any)?.automatic_analysis===false?'neutral':'good'}>{(centre.settings as any)?.automatic_analysis===false?'Manual':'Automatic'}</Status>
            </div>
            <div className="scheduleCompact">
              <div><span>Frequency</span><b>Every training day</b></div>
              <div><span>Windows</span><b>09:00–11:00 · 14:00–16:00</b></div>
              <div><span>Connectivity</span><b>{centre.connectivity_mode.replaceAll('_',' ')}</b></div>
              <div><span>Next run</span><b>Next training window</b></div>
            </div>
            <Link href={'/centres/'+centreId+'/analysis'} className="scheduleAction">Run analysis now →</Link>
          </article>

          <article className="panel latestResultCard">
            <div className="panelHead"><div><span className="sectionKicker">Latest result</span><h2>{latest?'Most recent analysis':'No analysis yet'}</h2></div></div>
            {latest
              ? <div className="latestResultBody">
                  <Status tone={latest.outcome==='compliant'?'good':latest.outcome==='blocked'?'danger':'warn'}>{latest.outcome}</Status>
                  <b>{latest.analysis_type.replaceAll('_',' ')}</b>
                  <p>{latest.summary}</p>
                  <small>{new Date(latest.created_at).toLocaleString()}</small>
                </div>
              : <div className="latestResultBody empty"><b>Ready when you are</b><p>Run a manual analysis or wait for the next scheduled monitoring window.</p></div>
            }
          </article>
        </div>

        <section className="panel verificationBoard">
          <div className="panelHead">
            <div><span className="sectionKicker">Verification status</span><h2>Current centre picture</h2></div>
            <Link href={'/centres/'+centreId+'/outcome'}>Open final outcome →</Link>
          </div>
          <div className="verificationBoardGrid">
            <VerifyTile label="Attendance" value={centre.attendance_status} description="Stable presence vs submitted attendance"/>
            <VerifyTile label="Practical Work" value={centre.practical_status} description="Activity + external authorization"/>
            <VerifyTile label="Infrastructure" value={centre.infrastructure_status} description="Three-tier visual compliance"/>
            <VerifyTile label="Camera Integrity" value={centre.camera_status} description="Trust gate for video evidence"/>
            <VerifyTile label="Evidence Integrity" value="clear" description="Duplicate-evidence signal"/>
          </div>
        </section>

        <section className="panel recentAnalysisCard">
          <div className="panelHead">
            <div><span className="sectionKicker">Recent analysis</span><h2>What happened recently</h2></div>
            <Link href={'/centres/'+centreId+'/history'}>View all →</Link>
          </div>
          <div className="recentAnalysisList">
            {(centre.recent_analyses||[]).length===0&&<div className="calmState">No recorded analysis yet.</div>}
            {(centre.recent_analyses||[]).slice(0,4).map(row=><div className="recentAnalysisRow" key={row.analysis_id}>
              <span className={'recentState '+row.outcome}></span>
              <div><b>{row.analysis_type.replaceAll('_',' ')}</b><p>{row.summary}</p></div>
              <small>{new Date(row.created_at).toLocaleString()}</small>
            </div>)}
          </div>
        </section>
      </section>

      <aside className="centreOverviewSide">
        <section className={'centreSummaryCard '+(attention?'attention':'good')}>
          <div className="centreSummaryTitle"><span>✦</span><div><small>AI summary</small><b>Centre pulse</b></div></div>
          <p>{centre.status==='compliant'
            ? 'All current checks are clear. No unresolved exception is blocking this centre.'
            : centre.status==='high_priority'
              ? 'This centre needs priority attention. Repeated or multi-signal issues have triggered escalation.'
              : 'One or more evidence-backed findings still need officer review before this cycle is closed.'}</p>
          <div className="centreSummaryStats">
            <div><span>Pending</span><b>{centre.pending_cases}</b></div>
            <div><span>Camera</span><b>{centre.camera_status}</b></div>
            <div><span>Escalation</span><b>{centre.escalation.label}</b></div>
          </div>
          <div className="centreSummaryReason">
            <span>Why</span>
            <p>{centre.escalation.reasons?.[0]||'No escalation trigger.'}</p>
            <small>{centre.escalation.next_action||'Continue scheduled monitoring.'}</small>
          </div>
          {centre.pending_cases>0&&<Link href={'/centres/'+centreId+'/review'} className="summaryReviewBtn">Open review queue →</Link>}
        </section>

        <AssistantPanel centreId={centreId}/>
      </aside>
    </div>
  </div>;
}

function VerifyTile({label,value,description}:{label:string;value:string;description:string}){
  const good=['compliant','nominal','clear'].includes(value);
  return <div className={'verifyTile '+(good?'good':'attention')}>
    <span>{good?'✓':'!'}</span>
    <div><b>{label}</b><small>{description}</small></div>
    <em>{value.replaceAll('_',' ')}</em>
  </div>;
}
