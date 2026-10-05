export type CentreStatus = 'compliant'|'attention'|'high_priority'|'incomplete';

export type Centre = {
  centre_id:string;
  name:string;
  location:string;
  district:string;
  state:string;
  batch_id:string;
  job_role:string;
  trainees:number;
  camera_id:string;
  connectivity_mode:string;
  status:CentreStatus;
  pending_cases:number;
  confirmed_cases?:number;
  attendance_status:string;
  practical_status:string;
  infrastructure_status:string;
  camera_status:string;
  evidence_integrity_status?:string;
  verification_complete?:boolean;
  analysis_count?:number;
  escalation:{
    level:number;
    label:string;
    reasons:string[];
    score?:number;
    next_action?:string;
    policy?:Record<string,unknown>;
  };
  last_analysis:string|null;
  settings?:Record<string,unknown>;
  recent_analyses?:AnalysisRow[];
};

export type AnalysisRow = {
  analysis_id:string;
  created_at:string;
  centre_id:string;
  batch_id:string;
  analysis_type:'attendance'|'practical_work'|'infrastructure'|string;
  outcome:'compliant'|'attention'|'blocked'|string;
  summary:string;
  details:Record<string,unknown>;
};

export type CaseRecord = {
  case_id:string;
  centre_id:string;
  batch_id:string;
  case_type:string;
  status:string;
  severity:string;
  summary:string;
  created_at?:string;
  evidence?:{evidence_id:string;created_at?:string;duplicate_of?:string|null;sha256?:string;perceptual_hash?:string;metadata?:Record<string,unknown>}[];
  review_history?:{timestamp:string;from_status:string;to_status:string;note?:string|null;actor?:string|null}[];
  details?:Record<string,any>;
};

export type AssistantReply = {
  message:string;
  session_id:string;
  sources:AssistantSource[];
  tool_calls:AssistantToolCall[];
};

export type AssistantSource = {
  kind:'analysis'|'case'|'evidence'|'readiness'|'centre'|string;
  id:string;
  label:string;
  href:string;
  timestamp:string|null;
};

export type AssistantToolCall = {
  name:string;
  status:'success'|'error'|string;
  duration_ms:number;
};

export type AssistantStatus = {
  enabled:boolean;
  configured:boolean;
  available:boolean;
  voice_configured:boolean;
  voice_available:boolean;
};

export type AssistantMessage = {
  id:string;
  role:'user'|'assistant';
  text:string;
  sources?:AssistantSource[];
  voiceOrigin?:boolean;
};
