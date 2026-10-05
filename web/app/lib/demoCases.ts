import type { CaseRecord } from './types';

export const DEMO_CASES: CaseRecord[] = [
  {
    case_id: 'SIM-KA-104-ATT', centre_id: 'DEMO-KA-104', batch_id: 'ELEC-2026-08', case_type: 'attendance_discrepancy', status: 'open', severity: 'medium',
    summary: 'Reported 28 trainees; sustained visual evidence showed 19.', created_at: '2026-10-05T13:10:00+05:30',
    details: { simulated: true, temporal_proof: 'Persisted across 3 analysis periods', camera_trust: 'trusted' },
    review_history: [], evidence: [],
  },
  {
    case_id: 'SIM-KA-303-INF', centre_id: 'DEMO-KA-303', batch_id: 'ELEC-2026-06', case_type: 'infrastructure_compliance', status: 'open', severity: 'high',
    summary: 'Required training panels remained below the reported manifest quantity.', created_at: '2026-10-05T11:40:00+05:30',
    details: { simulated: true, reported_quantity: 12, observed_quantity: 9, temporal_proof: 'Observed in 3 review periods' },
    review_history: [], evidence: [],
  },
];
