'use client';

import { Bot, Play } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import AnalysisModal from './AnalysisModal';
import CentreTabs from './CentreTabs';
import { EvidenceFrame, PageTitle, PersistenceTimeline, StatusPill, TechnicalDetails } from './CalmUi';
import { Button } from './ui/button';
import { API, getCases, getCentre, getHistory } from '../lib/api';
import { effectivePillarValue, FALLBACK_CENTRES, pillarState, simulatedFacts } from '../lib/presentation';
import type { AnalysisRow, CaseRecord, Centre } from '../lib/types';

type Kind = 'attendance' | 'practical' | 'infrastructure';

const copy: Record<Kind, { title: string; description: string; analysisType: string; caseMatch: (type: string) => boolean }> = {
  attendance: { title: 'Attendance', description: 'Reported presence compared with sustained visual evidence.', analysisType: 'attendance', caseMatch: type => type === 'attendance_discrepancy' },
  practical: { title: 'Practical', description: 'Visible activity evidence without identity tracking.', analysisType: 'practical_work', caseMatch: type => type.startsWith('practical_activity') },
  infrastructure: { title: 'Infrastructure', description: 'Required assets compared with camera-verifiable evidence.', analysisType: 'infrastructure', caseMatch: type => type === 'infrastructure_compliance' },
};

export default function CentreEvidenceTabPage({ centreId, kind }: { centreId: string; kind: Kind }) {
  const meta = copy[kind];
  const [centre, setCentre] = useState<Centre | null>(null);
  const [history, setHistory] = useState<AnalysisRow[]>([]);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [historyError, setHistoryError] = useState(false);
  const [casesError, setCasesError] = useState(false);
  const [centreDegraded, setCentreDegraded] = useState(false);
  const [analysisOpen, setAnalysisOpen] = useState(false);

  async function load() {
    setLoading(true);
    setHistoryError(false);
    setCasesError(false);
    setCentreDegraded(false);

    const [centreResult, historyResult, casesResult] = await Promise.allSettled([
      getCentre(centreId),
      getHistory(centreId, 50),
      getCases(),
    ]);

    if (centreResult.status === 'fulfilled') {
      setCentre(centreResult.value);
    } else {
      setCentre(FALLBACK_CENTRES.find(item => item.centre_id === centreId) || FALLBACK_CENTRES[0]);
      setCentreDegraded(true);
    }

    if (historyResult.status === 'fulfilled') {
      setHistory(historyResult.value.rows);
    } else {
      setHistory([]);
      setHistoryError(true);
    }

    if (casesResult.status === 'fulfilled') {
      setCases(casesResult.value.filter(item => item.centre_id === centreId));
    } else {
      setCases([]);
      setCasesError(true);
    }

    setLoading(false);
  }

  useEffect(() => { void load(); }, [centreId, kind]);
  const current = centre || FALLBACK_CENTRES.find(item => item.centre_id === centreId) || FALLBACK_CENTRES[0];
  const latest = useMemo(() => history.find(row => row.analysis_type === meta.analysisType) || current.recent_analyses?.find(row => row.analysis_type === meta.analysisType), [history, current, meta.analysisType]);
  const relevantCase = useMemo(() => cases.find(item => meta.caseMatch(item.case_type) && !['resolved', 'false_positive'].includes(item.status)), [cases, meta]);
  const evidence = relevantCase?.evidence?.[0];
  const sourceUnavailable = centreDegraded || historyError || casesError;
  const cameraTrusted = centreDegraded ? undefined : !['attention', 'blocked'].includes(String(current.camera_status).toLowerCase());
  const pillarValue = effectivePillarValue(current, kind === 'attendance' ? 'attendance' : kind === 'practical' ? 'practical' : 'infrastructure');
  const state = sourceUnavailable ? 'unavailable' : cameraTrusted === false ? 'uncertain' : pillarState(pillarValue, true);
  const seed = simulatedFacts(centreId);
  const usingSimulatedPreview = !sourceUnavailable && !latest && !relevantCase;

  const facts = useMemo(() => {
    if (sourceUnavailable) {
      return { reported: 'Unavailable', observed: 'Unavailable', observedNote: 'Evidence services unavailable' };
    }
    if (kind === 'attendance') {
      const reported = relevantCase?.reported_attendance ?? Number(seed.reportedValue || current.trainees);
      const observed = relevantCase?.visual_occupancy ?? (seed.observedValue === 'Unavailable' ? 'Unavailable' : Number(seed.observedValue));
      return { reported: String(reported), observed: String(observed), observedNote: cameraTrusted ? 'Sustained visual presence' : 'Camera trust insufficient' };
    }
    if (kind === 'practical') {
      return { reported: 'Scheduled', observed: state === 'verified' ? 'APPARENTLY ACTIVE' : state === 'review' ? 'APPARENTLY INACTIVE' : 'UNCERTAIN', observedNote: state === 'verified' ? 'Visible work-cell interaction' : 'Officer verification required' };
    }
    return { reported: '12 panels', observed: centreId === 'DEMO-KA-303' ? '9 PRESENT' : '12 PRESENT', observedNote: state === 'verified' ? 'Required items visible' : state === 'review' ? 'Manifest gap persisted' : 'Camera trust insufficient' };
  }, [sourceUnavailable, kind, relevantCase, seed, current.trainees, cameraTrusted, state, centreId]);

  const detail = latest?.details || relevantCase?.details || {};
  const evidenceSrc = evidence?.evidence_id ? `${API}/evidence/${evidence.evidence_id}.jpg` : undefined;

  return (
    <div>
      <PageTitle title={meta.title} description={meta.description} action={<><Button variant="ghost" onClick={() => window.dispatchEvent(new Event('kaushalwatch:assistant'))}><Bot size={17} /> Ask assistant</Button><Button variant="primary" onClick={() => setAnalysisOpen(true)}><Play size={17} /> Run analysis now</Button></>} />
      <CentreTabs centreId={centreId} />

      {sourceUnavailable && !loading && (
        <div role="alert" className="mb-5 rounded-xl border border-[#F2D3A2] bg-[#FFFBF5] px-5 py-4 text-[13px] leading-5 text-[#8A4B12]">
          Evidence services are partially unavailable. Reported/observed facts and Temporal Proof are withheld rather than replaced with demo values.
        </div>
      )}
      {usingSimulatedPreview && (
        <div className="mb-5 rounded-xl border border-[#E4EAF2] bg-[#F8FAFC] px-5 py-4 text-[12px] leading-5 text-[#667085]">
          Simulated preview: no recorded {meta.title.toLowerCase()} analysis or open case is available for this centre, so the preview values below are deterministic demo data.
        </div>
      )}

      <section className="grid gap-8 lg:grid-cols-[1.25fr_.75fr]">
        <EvidenceFrame
          src={evidenceSrc}
          timestamp={evidence?.created_at ? new Date(evidence.created_at).toLocaleString() : latest?.created_at ? new Date(latest.created_at).toLocaleString() : undefined}
          trusted={cameraTrusted}
          emptyText={sourceUnavailable ? 'Evidence records unavailable' : usingSimulatedPreview ? 'Simulated preview · no retained frame' : 'Evidence preview appears after analysis'}
        />

        <div className="kw-surface divide-y divide-[#EEF1F4] px-6">
          <Fact label="Reported" value={facts.reported} reason={sourceUnavailable ? 'Source unavailable' : usingSimulatedPreview ? 'Centre record · Simulated' : 'Centre record'} />
          <Fact label="Observed" value={facts.observed} reason={`${facts.observedNote}${usingSimulatedPreview ? ' · Simulated' : ''}`} />
          <div className="py-6">
            <div className="text-[13px] font-medium text-[#667085]">Status</div>
            <div className="mt-3"><StatusPill state={state} /></div>
            <div className="mt-2 text-[13px] text-[#667085]">{state === 'uncertain' ? 'Conclusion suspended; never guessed.' : state === 'review' ? 'Persistent discrepancy needs officer review.' : state === 'verified' ? 'Recorded evidence supports the required state.' : 'No trusted analysis is available.'}</div>
          </div>
        </div>
      </section>

      <section className="mt-12 grid gap-8 lg:grid-cols-[1.25fr_.75fr]">
        {sourceUnavailable ? (
          <div className="rounded-2xl bg-[#F8FAFC] p-6">
            <div className="text-[14px] font-medium text-[#475467]">Temporal Proof</div>
            <p className="mt-3 text-[13px] leading-5 text-[#667085]">Unavailable while required evidence services are unavailable. No temporal pattern is inferred.</p>
          </div>
        ) : (
          <PersistenceTimeline
            points={state === 'review' ? [{ label: '09:00', state: 'ok' }, { label: '11:00', state: 'miss' }, { label: '13:00', state: 'miss' }, { label: '15:00', state: 'miss' }] : state === 'uncertain' ? [{ label: '09:00', state: 'ok' }, { label: '11:00', state: 'ok' }, { label: '13:00', state: 'uncertain' }, { label: '15:00', state: 'uncertain' }] : [{ label: '09:00', state: 'ok' }, { label: '11:00', state: 'ok' }, { label: '13:00', state: 'ok' }, { label: '15:00', state: 'ok' }]}
            summary={state === 'review' ? 'Discrepancy persisted across multiple analysis periods' : state === 'uncertain' ? 'Temporal conclusion paused when camera trust failed' : 'No persistent discrepancy recorded'}
          />
        )}
        <TechnicalDetails>
          <p>Analysis: {sourceUnavailable ? 'Unavailable' : latest?.analysis_id || 'Simulated preview until a live run is recorded'}</p>
          <p>Camera: {current.camera_id}</p>
          {Object.entries(detail).slice(0, 5).map(([key, value]) => <p key={key}>{key.replaceAll('_', ' ')}: {typeof value === 'object' ? JSON.stringify(value) : String(value)}</p>)}
          {evidence?.sha256 && <p className="break-all">SHA-256: {evidence.sha256}</p>}
        </TechnicalDetails>
      </section>

      <AnalysisModal open={analysisOpen} onOpenChange={setAnalysisOpen} centre={current} onComplete={updated => { setCentre(updated); void load(); }} />
    </div>
  );
}

function Fact({ label, value, reason }: { label: string; value: string; reason: string }) {
  return <div className="py-6"><div className="text-[13px] font-medium text-[#667085]">{label}</div><div className="mt-2 text-[28px] font-medium leading-none tracking-[-0.03em] text-[#172033]">{value}</div><div className="mt-2 text-[13px] text-[#667085]">{reason}</div></div>;
}
