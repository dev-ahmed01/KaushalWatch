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


export type CentreEngine = {
  key: string;
  name: string;
  state: 'verified' | 'review' | 'uncertain' | 'unavailable';
  label: string | null;
  summary: string;
  href_suffix: string;
};

export type CentreIntelligence = {
  generated_at: string;
  timezone: string;
  period: 'today' | 'yesterday' | 'last_7_days' | 'last_30_days';
  period_label: string;
  grounded: boolean;
  simulated: boolean;
  centre: {
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
    last_analysis: string | null;
    escalation: Centre['escalation'];
  };
  brief: { headline: string; bullets: string[] };
  engines: CentreEngine[];
  actions: Array<{ priority: string; title: string; reason: string; href: string }>;
  contact: {
    role: string;
    available: boolean;
    name: string | null;
    phone: string | null;
    email: string | null;
    note: string;
  };
  schedule: {
    automatic_analysis: boolean;
    frequency: string;
    monitoring_windows: string[];
  };
  period_activity: {
    analysis_runs: number;
    recent_analyses: Array<{
      analysis_id: string;
      created_at: string;
      analysis_type: string;
      outcome: string;
      summary: string;
    }>;
  };
  decision_policy: string;
};


export type ActivityTimelineBucket = {
  start_at: string;
  end_at: string;
  label: string;
  activity_score: number;
  activity_percent: number;
  trusted_frame_ratio: number;
  active_work_cells: number;
  trusted: boolean;
  simulated: boolean;
  source: string;
};

export type ActivityIntelligence = {
  generated_at: string;
  timezone: string;
  period: 'today' | 'yesterday' | 'last_7_days' | 'last_30_days';
  period_label: string;
  grounded: boolean;
  simulated: boolean;
  centre_id: string;
  state: 'available' | 'uncertain' | 'unavailable';
  explanation: string;
  thresholds: {
    minimum_trusted_ratio: number;
    low_activity_threshold: number;
    follow_up_minutes: number;
  };
  summary: {
    bucket_count: number;
    trusted_bucket_count: number;
    peak: {
      label: string;
      activity_score: number;
      activity_percent: number;
      active_work_cells: number;
    } | null;
    lowest: {
      label: string;
      activity_score: number;
      activity_percent: number;
      active_work_cells: number;
    } | null;
    longest_low_period: {
      label: string;
      minutes: number;
      activity_score: number;
    } | null;
  };
  timeline: ActivityTimelineBucket[];
  follow_up: {
    recommended: boolean;
    title: string;
    reason: string;
    action_label: string;
  };
  interpretation_boundary: string;
  decision_policy: string;
};


export type EvidenceReviewFact = {
  label: string;
  value: string;
  note: string;
};

export type EvidenceTemporalPoint = {
  label: string;
  state: 'ok' | 'miss' | 'uncertain';
  note: string | null;
};

export type EvidenceReviewPack = {
  prototype: boolean;
  case: CaseRecord;
  facts: EvidenceReviewFact[];
  temporal_proof: {
    points: EvidenceTemporalPoint[];
    summary: string;
    rule: string;
  };
  integrity: {
    state: 'verified' | 'review' | 'unavailable';
    retained_count: number;
    possible_duplicate_count: number;
    checks: {
      sha256_retained: boolean;
      duplicate_review_clear: boolean;
      camera_trust: 'trusted' | 'untrusted' | 'not_recorded';
    };
    items: Array<{
      evidence_id: string;
      created_at: string;
      sha256: string;
      perceptual_hash: string;
      possible_duplicate: boolean;
      duplicate_of: string | null;
      metadata: Record<string, unknown>;
    }>;
  };
  review: {
    status: string;
    terminal: boolean;
    allowed_actions: Array<{
      action: string;
      label: string;
      note_required: boolean;
    }>;
    history: Array<{
      timestamp: string;
      actor?: string | null;
      from_status: string;
      to_status: string;
      note?: string | null;
    }>;
  };
  decision_policy: string;
  privacy_note: string;
};


export type InsightState = 'verified' | 'review' | 'uncertain' | 'unavailable';

export type NetworkInsights = {
  generated_at: string;
  timezone: string;
  period: 'today' | 'yesterday' | 'last_7_days' | 'last_30_days';
  period_label: string;
  grounded: boolean;
  simulated: boolean;
  counts: {
    total: number;
    verified: number;
    review: number;
    uncertain: number;
    unavailable: number;
    analysis_runs: number;
  };
  centre_health: Array<{
    centre_id: string;
    name: string;
    short_name: string;
    state: InsightState;
  }>;
  attendance: Array<{
    centre_id: string;
    name: string;
    short_name: string;
    reported: number | null;
    observed: number | null;
    difference: number | null;
    available: boolean;
    status: InsightState;
  }>;
  activity_heatmap: {
    hours: string[];
    rows: Array<{
      centre_id: string;
      name: string;
      short_name: string;
      state: 'available' | 'uncertain' | 'unavailable';
      values: Array<number | null>;
      peak: { label: string; activity_percent: number } | null;
      lowest: { label: string; activity_percent: number } | null;
    }>;
  };
  infrastructure: Array<{
    centre_id: string;
    name: string;
    short_name: string;
    case_count: number;
    missing_units: number;
    discrepancy_items: number;
    status: InsightState;
  }>;
  camera_trust: Array<{
    centre_id: string;
    name: string;
    short_name: string;
    state: InsightState;
  }>;
  analysis_mix: {
    types: Record<string, number>;
    outcomes: Record<string, number>;
  };
  case_outcomes: Record<string, number>;
  insights: Array<{
    title: string;
    body: string;
    centre_id: string;
    href: string;
    kind: string;
  }>;
  report_centres: Array<{
    centre_id: string;
    name: string;
    state: InsightState;
  }>;
  decision_policy: string;
};
