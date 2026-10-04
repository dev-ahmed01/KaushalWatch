'use client';

import Link from 'next/link';

export type StepState='pending'|'running'|'complete'|'attention'|'blocked';

const META:Record<StepState,{label:string;short:string;symbol:string}> = {
  pending:{label:'Pending',short:'Pending',symbol:'•'},
  running:{label:'Analysis in progress',short:'In progress',symbol:'↻'},
  complete:{label:'Completed',short:'Completed',symbol:'✓'},
  attention:{label:'Needs human review',short:'Needs review',symbol:'!'},
  blocked:{label:'Verification blocked',short:'Blocked',symbol:'×'},
};

export default function WorkflowStepper({
  centreId,
  states,
}:{
  centreId:string;
  states?:Partial<Record<'attendance'|'practical'|'infrastructure'|'review',StepState>>;
}){
  const steps=[
    ['attendance','Attendance','/centres/'+centreId+'/attendance'],
    ['practical','Practical Work','/centres/'+centreId+'/practical'],
    ['infrastructure','Infrastructure','/centres/'+centreId+'/infrastructure'],
    ['review','Review Outcome','/centres/'+centreId+'/outcome'],
  ] as const;

  return <section className="workflowShell" aria-label="Centre verification workflow">
    <div className="workflowIntro">
      <span>Centre verification</span>
      <strong>4 checkpoints</strong>
    </div>
    <div className="workflowStepper">
      {steps.map(([key,label,href],index)=>{
        const state=states?.[key]||'pending';
        const meta=META[state];
        return <div className={'workflowNode '+state} key={key}>
          <Link href={href} className="workflowStepLink" title={meta.label}>
            <span className="workflowStepIcon">{state==='pending'?index+1:meta.symbol}</span>
            <div><strong>{label}</strong><small>{meta.short}</small></div>
          </Link>
          {index<steps.length-1&&<i className="workflowConnector"><b></b></i>}
        </div>;
      })}
    </div>
  </section>;
}
