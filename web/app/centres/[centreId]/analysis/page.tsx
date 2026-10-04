'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import { getCentre } from '../../../lib/api';
import type { Centre } from '../../../lib/types';
import { workflowStatesForCentre } from '../../../lib/workflow';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { PageHeader } from '../../../components/Ui';

export default function AnalysisRun(){
  const {centreId}=useParams<{centreId:string}>();
  const id=String(centreId);
  const [centre,setCentre]=useState<Centre|null>(null);
  useEffect(()=>{getCentre(id).then(setCentre).catch(()=>setCentre(null));},[id]);
  const states=workflowStatesForCentre(centre);
  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Selected Centre / Analysis" title="Start Centre Analysis" subtitle="Run the three verification checkpoints in order. Each step remains independent and can abstain if its evidence is unreliable."/>
    <WorkflowStepper centreId={id} states={states}/>
    <div className="runningLayout">
      <section className="panel runningPanel">
        <div className="runningHeader"><span className="spinnerOrb"></span><div><h2>Guided analysis workflow</h2><p>Run each checkpoint when evidence is available. Progress updates only after a recorded analysis completes.</p></div></div>
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
