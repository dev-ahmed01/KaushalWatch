import type { Centre, AnalysisRow } from './types';

export type WorkflowState='pending'|'running'|'complete'|'attention'|'blocked';

function stateFor(row:AnalysisRow|undefined):WorkflowState{
  if(!row) return 'pending';
  if(row.outcome==='compliant') return 'complete';
  if(row.outcome==='blocked') return 'blocked';
  return 'attention';
}

function latestByType(centre:Centre|undefined|null,type:string){
  return (centre?.recent_analyses||[]).find(row=>row.analysis_type===type);
}

export function workflowStatesForCentre(centre:Centre|undefined|null){
  const attendance=stateFor(latestByType(centre,'attendance'));
  const practical=stateFor(latestByType(centre,'practical_work'));
  const infrastructure=stateFor(latestByType(centre,'infrastructure'));
  const checkpoints=[attendance,practical,infrastructure];
  const allRun=checkpoints.every(state=>state!=='pending'&&state!=='running');

  let review:WorkflowState='pending';
  if(allRun){
    if(checkpoints.includes('blocked')) review='blocked';
    else if((centre?.pending_cases||0)>0||checkpoints.includes('attention')) review='attention';
    else review='complete';
  }

  return {attendance,practical,infrastructure,review};
}

export function withRunningStep(
  centre:Centre|undefined|null,
  step:'attendance'|'practical'|'infrastructure',
  running:boolean,
  resolved?:WorkflowState,
){
  const states=workflowStatesForCentre(centre);
  return {
    ...states,
    [step]: running ? 'running' : (resolved||states[step]),
  };
}
