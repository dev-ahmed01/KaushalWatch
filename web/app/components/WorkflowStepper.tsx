'use client';

import Link from 'next/link';

export type StepState='pending'|'running'|'complete'|'attention'|'blocked';

const META:Record<StepState,{label:string;symbol:string}> = {
  pending:{label:'Pending',symbol:'•'},
  running:{label:'In progress',symbol:'↻'},
  complete:{label:'Completed',symbol:'✓'},
  attention:{label:'Needs review',symbol:'!'},
  blocked:{label:'Blocked',symbol:'×'},
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

  return <section className="neoWorkflow" aria-label="Centre verification workflow">
    {steps.map(([key,label,href],index)=>{
      const state=states?.[key]||'pending';
      const meta=META[state];
      return <div className={'neoWorkflowNode '+state} key={key}>
        <Link href={href}>
          <span className="neoWorkflowCircle">{state==='pending'?index+1:meta.symbol}</span>
          <div><b>{label}</b><small>{meta.label}</small></div>
        </Link>
        {index<steps.length-1&&<span className="neoWorkflowLine"><i></i></span>}
      </div>;
    })}
  </section>;
}
