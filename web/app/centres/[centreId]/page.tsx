'use client';

import Link from 'next/link';
import { Bot, ChevronRight, Clock3, Play, RefreshCw } from 'lucide-react';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import AnalysisModal from '../../components/AnalysisModal';
import CentreTabs from '../../components/CentreTabs';
import { EmptyState, EvidenceFrame, PageTitle, PersistenceTimeline, StatusPill, TechnicalDetails } from '../../components/CalmUi';
import { Button } from '../../components/ui/button';
import { API, getCases, getCentre } from '../../lib/api';
import { centreUiState, effectivePillarValue, FALLBACK_CENTRES, pillarState, statusReason } from '../../lib/presentation';
import { DEMO_CASES } from '../../lib/demoCases';
import type { CaseRecord, Centre } from '../../lib/types';

const FALLBACK = FALLBACK_CENTRES[0];

function nextAnalysisLabel(windows: string[]) {
  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();
  const parsed = windows
    .map(value => {
      const normalized = value.replaceAll('–', '-').trim();
      const [start, end] = normalized.split('-', 2).map(part => part.trim());
      const [hours, minutes] = start.split(':').map(Number);
      return {
        label: end ? `${start}–${end}` : start,
        minutes: hours * 60 + minutes,
      };
    })
    .filter(item => Number.isFinite(item.minutes))
    .sort((a, b) => a.minutes - b.minutes);
  const laterToday = parsed.find(item => item.minutes > currentMinutes);
  const target = laterToday || parsed[0];
  if (!target) return 'Schedule unavailable';
  return `${laterToday ? 'Today' : 'Tomorrow'} · ${target.label}`;
}

export default function CentreCockpit() {
  const { centreId } = useParams<{ centreId: string }>();
  const id = String(centreId);
  const [centre, setCentre] = useState<Centre | null>(null);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [analysisOpen, setAnalysisOpen] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [c, allCases] = await Promise.all([getCentre(id), getCases().catch(() => [])]);
      setCentre(c);
      const centreCases = allCases.filter(item => item.centre_id === id);
      const demoCases = DEMO_CASES.filter(item => item.centre_id === id);
      setCases(centreCases.length ? centreCases : demoCases);
    } catch {
      setCentre(FALLBACK_CENTRES.find(item => item.centre_id === id) || FALLBACK);
      setCases(DEMO_CASES.filter(item => item.centre_id === id));
    } finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [id]);

  const current = centre || FALLBACK_CENTRES.find(item => item.centre_id === id) || FALLBACK;
  const uiState = centreUiState(current);
  const openCases = cases.filter(item => ['open', 'under_review', 'virtual_verification'].includes(item.status));
  const priorityCase = openCases[0];
  const cameraTrusted = !['attention', 'blocked'].includes(String(effectivePillarValue(current, 'camera')).toLowerCase());
  const evidence = priorityCase?.evidence?.[0];
  const evidenceSrc = evidence?.evidence_id ? `${API}/evidence/${evidence.evidence_id}.jpg` : undefined;
  const schedule = (current.settings || {}) as any;
  const automatic = schedule.automatic_analysis !== false && schedule.frequency !== 'manual';
  const windows: string[] = Array.isArray(schedule.monitoring_windows) && schedule.monitoring_windows.length ? schedule.monitoring_windows : ['10:30', '15:30'];
  const next = automatic ? nextAnalysisLabel(windows) : 'Manual only';
  const last = current.last_analysis ? new Date(current.last_analysis).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'No trusted run yet';

  const pillars = useMemo(() => [
    ['Attendance', effectivePillarValue(current, 'attendance')],
    ['Practical Activity', effectivePillarValue(current, 'practical')],
    ['Infrastructure', effectivePillarValue(current, 'infrastructure')],
    ['Camera Integrity', effectivePillarValue(current, 'camera')],
    ['Evidence Integrity', effectivePillarValue(current, 'evidence')],
  ] as const, [current]);

  function askAssistant() {
    window.dispatchEvent(new Event('kaushalwatch:assistant'));
  }

  return (
    <div>
      <PageTitle
        title={current.name}
        description={`${current.job_role} · ${current.batch_id}`}
        action={<><Button variant="ghost" onClick={askAssistant}><Bot size={17} /> Ask assistant</Button><Button variant="primary" onClick={() => setAnalysisOpen(true)}><Play size={17} /> Run analysis now</Button></>}
      />

      <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-[13px] text-[#667085]">
        <StatusPill state={uiState} />
        <span>Last analysis · {last}</span>
        <span>Next analysis · {next}</span>
        <span className="rounded-full bg-[#F2F4F7] px-2 py-0.5 text-[11px]">Simulated records</span>
      </div>

      <CentreTabs centreId={id} />

      <section className="rounded-2xl bg-white px-2 py-1 shadow-[0_1px_2px_rgba(16,24,40,.04)] ring-1 ring-[#E6EAF0]">
        <div className="grid gap-1 lg:grid-cols-5">
          {pillars.map(([label, value]) => {
            const state = label === 'Camera Integrity' || label === 'Evidence Integrity' ? pillarState(value, true) : pillarState(value, cameraTrusted);
            return <div key={label} className="px-5 py-5">
              <div className="text-[13px] font-medium text-[#667085]">{label}</div>
              <div className="mt-3"><StatusPill state={state} /></div>
              <div className="mt-2 text-[13px] leading-5 text-[#667085]">{statusReason(label, value, current)}</div>
            </div>;
          })}
        </div>
      </section>

      <section className="mt-14">
        <div className="mb-5 flex items-end justify-between"><div><div className="text-[13px] font-medium text-[#667085]">Officer review</div><h2 className="mt-1 text-xl font-medium text-[#172033]">Needs your decision</h2></div>{loading && <RefreshCw size={17} className="animate-spin text-[#98A2B3]" />}</div>
        {priorityCase ? (
          <Link href={`/cases/${priorityCase.case_id}`} className="kw-focus block rounded-2xl border border-[#F2D3A7] bg-[#FFFCF5] p-7 transition-colors hover:bg-[#FFF9EC]">
            <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
              <div className="max-w-2xl">
                <div className="flex items-center gap-2"><StatusPill state="review" />{priorityCase.case_id.startsWith('SIM-') && <span className="rounded-full bg-white px-2 py-1 text-[11px] text-[#667085] ring-1 ring-[#E6EAF0]">Simulated</span>}</div>
                <h3 className="mt-4 text-xl font-medium text-[#172033]">{priorityCase.summary || 'Evidence needs officer review'}</h3>
                <p className="mt-2 text-[15px] leading-6 text-[#667085]">Temporal evidence persisted long enough to create a reviewable case. No automated final decision was issued.</p>
              </div>
              <span className="flex items-center gap-2 text-[14px] font-medium text-[#B54708]">Review evidence <ChevronRight size={16} /></span>
            </div>
          </Link>
        ) : uiState === 'verified' ? (
          <EmptyState title="All checks verified" body="No open evidence-backed cases for this centre." action={<Link href={`/reports?centre=${id}`} className="text-[14px] font-medium text-[#2563EB]">View previous reports</Link>} />
        ) : uiState === 'uncertain' ? (
          <EmptyState state="uncertain" title="Conclusion suspended" body="Camera trust is insufficient, so dependent conclusions remain uncertain." />
        ) : uiState === 'unavailable' ? (
          <EmptyState state="unavailable" title="Analysis unavailable" body="No trusted analysis is available for an officer decision yet." />
        ) : (
          <EmptyState state="review" title="Officer review needed" body="A discrepancy exists, but reviewable case evidence is not available yet." />
        )}
      </section>

      <section className="mt-16 grid gap-8 lg:grid-cols-[1.2fr_.8fr]">
        <EvidenceFrame
          src={evidenceSrc}
          timestamp={evidence?.created_at ? new Date(evidence.created_at).toLocaleString() : undefined}
          trusted={cameraTrusted}
          emptyText={priorityCase?.case_id.startsWith('SIM-') ? 'Simulated case · no retained frame bundled' : 'No retained evidence preview available'}
        />
        <div>
          <PersistenceTimeline
            points={uiState === 'review' ? [{ label: '09:00', state: 'ok' }, { label: '11:00', state: 'miss' }, { label: '13:00', state: 'miss' }, { label: '15:00', state: 'miss' }] : [{ label: '09:00', state: 'ok' }, { label: '11:00', state: 'ok' }, { label: '13:00', state: cameraTrusted ? 'ok' : 'uncertain' }, { label: '15:00', state: cameraTrusted ? 'ok' : 'uncertain' }]}
            summary={uiState === 'review' ? 'Discrepancy persisted across multiple periods' : uiState === 'uncertain' ? 'Conclusion suspended after camera trust changed' : 'No persistent discrepancy recorded'}
          />
          <TechnicalDetails>
            <p>Camera ID: {current.camera_id}</p>
            <p>Evidence integrity: {String(effectivePillarValue(current, 'evidence')).replaceAll('_', ' ')}</p>
            {evidence?.sha256 && <p className="break-all">SHA-256: {evidence.sha256}</p>}
          </TechnicalDetails>
        </div>
      </section>

      <div className="mt-16 flex items-center gap-2 text-[13px] text-[#667085]"><Clock3 size={15} /> Scheduled analysis is the default; manual runs are available for targeted verification.</div>

      <AnalysisModal open={analysisOpen} onOpenChange={setAnalysisOpen} centre={current} onComplete={updated => { setCentre(updated); void load(); }} />
    </div>
  );
}
