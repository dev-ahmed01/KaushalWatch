export type CentreStatus = 'compliant' | 'attention' | 'high_priority' | 'incomplete';

export type AnalysisRow = {
  analysis_id: string;
  created_at: string;
  centre_id: string;
  batch_id: string;
  analysis_type: 'attendance' | 'practical_work' | 'infrastructure' | string;
  outcome: 'compliant' | 'attention' | 'blocked' | string;
  summary: string;
  details: Record<string, unknown>;
};

export type Centre = {
  centre_id: string;
  name: string;
  location: string;
  district: string;
  state: string;
  batch_id: string;
  job_role: string;
  trainees: number;
  camera_id: string;
  connectivity_mode: string;
  status: CentreStatus;
  pending_cases: number;
  confirmed_cases?: number;
  attendance_status: string;
  practical_status: string;
  infrastructure_status: string;
  camera_status: string;
  evidence_integrity_status?: string;
  verification_complete?: boolean;
  analysis_count?: number;
  escalation: {
    level: number;
    label: string;
    reasons: string[];
    score?: number;
    next_action?: string;
    policy?: Record<string, unknown>;
  };
  last_analysis: string | null;
  settings?: Record<string, unknown>;
  recent_analyses?: AnalysisRow[];
};

export type EvidenceRecord = {
  evidence_id: string;
  created_at?: string;
  frame_path?: string;
  duplicate_of?: string | null;
  sha256?: string;
  perceptual_hash?: string;
  metadata?: Record<string, unknown>;
};

export type CaseRecord = {
  case_id: string;
  centre_id: string;
  batch_id: string;
  case_type: string;
  status: string;
  severity: string;
  summary: string;
  created_at?: string;
  reported_attendance?: number | null;
  visual_occupancy?: number | null;
  discrepancy_pct?: number | null;
  persistence_ratio?: number | null;
  camera_trust?: { trusted?: boolean; reasons?: string[]; [key: string]: unknown } | null;
  evidence?: EvidenceRecord[];
  review_history?: { timestamp: string; from_status: string; to_status: string; note?: string | null; actor?: string | null }[];
  details?: Record<string, any>;
};

export type AssistantReply = {
  message: string;
  session_id: string;
  sources: AssistantSource[];
  tool_calls: AssistantToolCall[];
};

export type AssistantSource = {
  kind: 'analysis' | 'case' | 'evidence' | 'readiness' | 'centre' | string;
  id: string;
  label: string;
  href: string;
  timestamp: string | null;
};

export type AssistantToolCall = { name: string; status: 'success' | 'error' | string; duration_ms: number };
export type AssistantStatus = { enabled: boolean; configured: boolean; available: boolean; voice_configured: boolean; voice_available: boolean };
export type AssistantMessage = { id: string; role: 'user' | 'assistant'; text: string; sources?: AssistantSource[]; voiceOrigin?: boolean };


export type KaushalBriefCentre = {
  centre_id: string;
  name: string;
  location: string;
  district: string;
  job_role: string;
  state: 'verified' | 'review' | 'uncertain' | 'unavailable';
  reason: string;
  period_analysis_count: number;
  period_attention_count: number;
  analysis_types: Record<string, number>;
  open_case_count: number;
  escalation_level: number;
  recommended_action: { label: string; href: string };
  simulated: boolean;
  href: string;
};

export type KaushalBrief = {
  generated_at: string;
  timezone: string;
  period: 'today' | 'yesterday' | 'last_7_days' | 'last_30_days';
  period_label: string;
  window: { start: string; end: string };
  grounded: boolean;
  simulated: boolean;
  headline: string;
  bullets: string[];
  counts: {
    total: number;
    verified: number;
    review: number;
    uncertain: number;
    unavailable: number;
  };
  period_activity: {
    analysis_runs: number;
    attention_or_blocked_runs: number;
    analysis_types: Record<string, number>;
  };
  priority: {
    centre_id: string;
    centre_name: string;
    state: string;
    reason: string;
    label: string;
    href: string;
  } | null;
  recommendations: Array<{
    centre_id: string;
    centre_name: string;
    state: string;
    reason: string;
    label: string;
    href: string;
  }>;
  centres: KaushalBriefCentre[];
  source_counts: {
    analysis_rows_in_period: number;
    unresolved_or_confirmed_cases: number;
  };
  decision_policy: string;
};
