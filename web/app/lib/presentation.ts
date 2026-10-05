import type { AnalysisRow, CaseRecord, Centre } from './types';
import type { UiState } from '../components/CalmUi';

export type NetworkSeed = {
  uiState: UiState;
  reason: string;
  reportedLabel: string;
  reportedValue: string;
  observedValue: string;
  simulated: boolean;
  map: { left: string; top: string };
};

export const NETWORK_SEED: Record<string, NetworkSeed> = {
  'DEMO-KA-104': { uiState: 'review', reason: 'Attendance gap persisted', reportedLabel: 'Attendance', reportedValue: '28', observedValue: '19', simulated: true, map: { left: '70%', top: '78%' } },
  'DEMO-KA-112': { uiState: 'verified', reason: 'Checks aligned', reportedLabel: 'Attendance', reportedValue: '24', observedValue: '24', simulated: true, map: { left: '47%', top: '78%' } },
  'DEMO-KA-207': { uiState: 'uncertain', reason: 'Camera view obstructed', reportedLabel: 'Attendance', reportedValue: '21', observedValue: 'Unavailable', simulated: true, map: { left: '58%', top: '61%' } },
  'DEMO-KA-303': { uiState: 'review', reason: 'Panels below manifest', reportedLabel: 'Training panels', reportedValue: '12', observedValue: '9', simulated: true, map: { left: '41%', top: '31%' } },
  'DEMO-KA-509': { uiState: 'verified', reason: 'Evidence aligned', reportedLabel: 'Attendance', reportedValue: '18', observedValue: '18', simulated: true, map: { left: '27%', top: '18%' } },
  'DEMO-KA-601': { uiState: 'unavailable', reason: 'No trusted analysis', reportedLabel: 'Attendance', reportedValue: '16', observedValue: 'Unavailable', simulated: true, map: { left: '21%', top: '65%' } },
};

export const FALLBACK_CENTRES: Centre[] = [
  ['DEMO-KA-104','Bengaluru TC-04','Bengaluru, Karnataka','Bengaluru Urban','ELEC-2026-08','Construction Electrician - LV','LAB-CAM-01','low_bandwidth'],
  ['DEMO-KA-112','Mysuru TC-12','Mysuru, Karnataka','Mysuru','ELEC-2026-07','Construction Electrician - LV','LAB-CAM-02','normal'],
  ['DEMO-KA-207','Tumakuru TC-07','Tumakuru, Karnataka','Tumakuru','ELEC-2026-09','Construction Electrician - LV','WORKSHOP-CAM-01','low_bandwidth'],
  ['DEMO-KA-303','Hubballi TC-03','Hubballi, Karnataka','Dharwad','ELEC-2026-06','Construction Electrician - LV','LAB-CAM-03','normal'],
  ['DEMO-KA-509','Belagavi TC-09','Belagavi, Karnataka','Belagavi','ELEC-2026-10','Construction Electrician - LV','LAB-CAM-01','low_bandwidth'],
  ['DEMO-KA-601','Mangaluru TC-01','Mangaluru, Karnataka','Dakshina Kannada','ELEC-2026-05','Construction Electrician - LV','WORKSHOP-CAM-02','normal'],
].map(([centre_id,name,location,district,batch_id,job_role,camera_id,connectivity_mode], index) => ({
  centre_id, name, location, district, state: 'Karnataka', batch_id, job_role, trainees: [28,24,21,26,18,16][index], camera_id, connectivity_mode,
  status: (index === 1 || index === 4 ? 'compliant' : index === 5 ? 'incomplete' : 'attention') as Centre['status'],
  pending_cases: index === 0 || index === 3 ? 1 : 0,
  attendance_status: index === 0 ? 'attention' : index === 2 ? 'blocked' : index === 5 ? 'pending' : 'compliant',
  practical_status: index === 5 ? 'pending' : 'compliant',
  infrastructure_status: index === 3 ? 'attention' : index === 5 ? 'pending' : 'compliant',
  camera_status: index === 2 ? 'attention' : index === 5 ? 'pending' : 'nominal',
  evidence_integrity_status: index === 5 ? 'pending' : 'clear',
  verification_complete: index !== 2 && index !== 5,
  escalation: { level: index === 3 ? 3 : index === 0 ? 1 : 0, label: index === 3 ? 'High priority' : index === 0 ? 'Centre review' : 'Normal', reasons: [NETWORK_SEED[centre_id].reason] },
  last_analysis: index === 5 ? null : '2026-10-05T14:30:00+05:30',
  recent_analyses: [],
})) as Centre[];

export function centreUiState(centre: Centre): UiState {
  if (centre.analysis_count || centre.recent_analyses?.length || centre.pending_cases || centre.confirmed_cases) {
    if (centre.camera_status === 'blocked' || centre.camera_status === 'attention') return 'uncertain';
    if (centre.pending_cases > 0 || centre.status === 'attention' || centre.status === 'high_priority') return 'review';
    if (centre.status === 'compliant') return 'verified';
    return 'unavailable';
  }
  return NETWORK_SEED[centre.centre_id]?.uiState || 'unavailable';
}

export function centreReason(centre: Centre): string {
  if (centre.analysis_count || centre.recent_analyses?.length || centre.pending_cases || centre.confirmed_cases) {
    if (centre.camera_status === 'blocked' || centre.camera_status === 'attention') return 'Camera trust insufficient';
    if (centre.pending_cases > 0) return centre.escalation?.reasons?.[0] || 'Officer decision required';
    if (centre.status === 'compliant') return 'Checks aligned';
  }
  return NETWORK_SEED[centre.centre_id]?.reason || 'No trusted conclusion';
}

export function pillarState(value: string | undefined, cameraTrusted = true): UiState {
  const normalized = String(value || '').toLowerCase();
  if (!cameraTrusted && !['camera','nominal','clear'].includes(normalized)) return 'uncertain';
  if (['compliant','nominal','clear','verified'].includes(normalized)) return 'verified';
  if (['attention','high_priority','review'].includes(normalized)) return 'review';
  if (['blocked','uncertain'].includes(normalized)) return 'uncertain';
  return 'unavailable';
}

export function statusReason(label: string, value: string | undefined, centre: Centre): string {
  const normalized = String(value || '').toLowerCase();
  if (!['Camera Integrity', 'Evidence Integrity'].includes(label) && ['attention','blocked'].includes(String(centre.camera_status).toLowerCase())) return 'Camera trust insufficient';
  if (normalized === 'compliant') return 'Evidence aligned';
  if (normalized === 'nominal') return 'Clear view during analysis';
  if (normalized === 'clear') return 'Original evidence retained';
  if (normalized === 'attention') return label === 'Attendance' ? 'Presence mismatch persisted' : label === 'Infrastructure' ? 'Manifest mismatch persisted' : 'Evidence needs review';
  if (normalized === 'blocked') return 'Trusted conclusion suspended';
  return 'No trusted analysis yet';
}

export function latestAnalysis(centre: Centre, type: string): AnalysisRow | undefined {
  return (centre.recent_analyses || []).find(row => row.analysis_type === type);
}

export function plainCaseType(caseType: string) {
  if (caseType === 'attendance_discrepancy') return 'Attendance discrepancy';
  if (caseType === 'infrastructure_compliance') return 'Infrastructure discrepancy';
  if (caseType.startsWith('practical_activity')) return 'Practical activity review';
  if (caseType === 'camera_integrity') return 'Camera integrity review';
  return caseType.replaceAll('_', ' ');
}

export function caseUiState(record: CaseRecord): UiState {
  if (record.status === 'resolved' || record.status === 'false_positive') return 'resolved';
  if (record.status === 'under_review' || record.status === 'virtual_verification') return 'officer';
  return 'review';
}

export function simulatedFacts(centreId: string) {
  return NETWORK_SEED[centreId] || NETWORK_SEED['DEMO-KA-104'];
}


export type PillarKey = 'attendance' | 'practical' | 'infrastructure' | 'camera' | 'evidence';

const SEED_PILLARS: Record<string, Record<PillarKey, string>> = {
  'DEMO-KA-104': { attendance: 'attention', practical: 'compliant', infrastructure: 'compliant', camera: 'nominal', evidence: 'clear' },
  'DEMO-KA-112': { attendance: 'compliant', practical: 'compliant', infrastructure: 'compliant', camera: 'nominal', evidence: 'clear' },
  'DEMO-KA-207': { attendance: 'blocked', practical: 'blocked', infrastructure: 'blocked', camera: 'attention', evidence: 'clear' },
  'DEMO-KA-303': { attendance: 'compliant', practical: 'compliant', infrastructure: 'attention', camera: 'nominal', evidence: 'clear' },
  'DEMO-KA-509': { attendance: 'compliant', practical: 'compliant', infrastructure: 'compliant', camera: 'nominal', evidence: 'clear' },
  'DEMO-KA-601': { attendance: 'pending', practical: 'pending', infrastructure: 'pending', camera: 'pending', evidence: 'pending' },
};

export function hasRecordedVerification(centre: Centre) {
  return Boolean(
    centre.analysis_count
    || centre.recent_analyses?.length
    || centre.pending_cases
    || centre.confirmed_cases,
  );
}

export function effectivePillarValue(centre: Centre, pillar: PillarKey) {
  if (!hasRecordedVerification(centre)) {
    return SEED_PILLARS[centre.centre_id]?.[pillar] || 'pending';
  }
  if (pillar === 'attendance') return centre.attendance_status;
  if (pillar === 'practical') return centre.practical_status;
  if (pillar === 'infrastructure') return centre.infrastructure_status;
  if (pillar === 'camera') return centre.camera_status;
  return centre.evidence_integrity_status || 'pending';
}
