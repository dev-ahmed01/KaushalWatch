'use client';

import Link from 'next/link';

export type StepState='pending'|'running'|'complete'|'attention'|'blocked';

export default function WorkflowStepper({
  centreId,
  states,
}:{
  centreId:string;
  states?:Partial<Record<'attendance'|'practical'|'infrastructure'|'review',StepState>>;
}){
  const steps=[
    ['attendance','Attendance',`/centres/${centreId}/attendance`],
    ['practical','Practical Work',`/centres/${centreId}/practical`],
    ['infrastructure','Infrastructure',`/centres/${centreId}/infrastructure`],
    ['review','Review Outcome',`/centres/${centreId}/review`],
  ] as const;
  return <div className="workflowStepper">
    {steps.map(([key,label,href],index)=>{
      const state=states?.[key]||'pending';
      return <div className={`workflowNode ${state}`} key={key}>
        <Link href={href} className="workflowStepLink">
          <span>{state==='complete'?'✓':state==='attention'?'!':state==='blocked'?'×':index+1}</span>
          <div><strong>{label}</strong><small>{state==='complete'?'Completed':state==='attention'?'Needs Review':state==='running'?'In Progress':state==='blocked'?'Blocked':'Pending'}</small></div>
        </Link>
        {index<steps.length-1&&<i></i>}
      </div>;
    })}
  </div>;
}
