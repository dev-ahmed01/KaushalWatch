'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { PageHeader } from '../../../components/Ui';

export default function AnalysisRun(){
  const {centreId}=useParams<{centreId:string}>();
  const id=String(centreId);
  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Selected Centre / Analysis" title="Start Centre Analysis" subtitle="Run the three verification checkpoints in order. Each step remains independent and can abstain if its evidence is unreliable."/>
    <WorkflowStepper centreId={id} states={{attendance:'running'}}/>
    <div className="runningLayout">
      <section className="panel runningPanel">
        <div className="runningHeader"><span className="spinnerOrb"></span><div><h2>Guided analysis workflow</h2><p>Start with attendance, continue to practical work, then verify infrastructure.</p></div></div>
        <div className="runSequence">
          <Link href={`/centres/${id}/attendance`} className="runStage active"><span>1</span><div><b>Analyse Attendance</b><small>Stable anonymous occupancy vs reported count</small></div><em>Start →</em></Link>
          <Link href={`/centres/${id}/practical`} className="runStage"><span>2</span><div><b>Analyse Practical Work</b><small>Persistent work-cell activity + external authorization</small></div><em>Open →</em></Link>
          <Link href={`/centres/${id}/infrastructure`} className="runStage"><span>3</span><div><b>Check Infrastructure</b><small>Camera-verifiable, partial, and officer-only manifest</small></div><em>Open →</em></Link>
          <Link href={`/centres/${id}/review`} className="runStage"><span>4</span><div><b>Review Outcome</b><small>Human review, escalation and evidence audit</small></div><em>Open →</em></Link>
        </div>
        <div className="analysisNotice">ⓘ Automatic scheduled monitoring can run these checks without an officer pressing a button. Manual start remains available for demos, rechecks and uploaded footage.</div>
      </section>
      <AssistantPanel centreId={id}/>
    </div>
  </div>;
}
