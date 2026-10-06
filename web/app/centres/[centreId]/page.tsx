'use client';

import Link from 'next/link';
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Bot,
  Building2,
  Camera,
  CheckCircle2,
  FileCheck2,
  Gauge,
  HardHat,
  Play,
  Users,
} from 'lucide-react';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import AnalysisModal from '../../components/AnalysisModal';
import CentreTabs from '../../components/CentreTabs';
import { StatusPill } from '../../components/CalmUi';
import { Button } from '../../components/ui/button';
import { getCentre, getCentreIntelligence } from '../../lib/api';
import { useBriefPeriod } from '../../lib/period';
import { FALLBACK_CENTRES } from '../../lib/presentation';
import type { Centre, CentreEngine, CentreIntelligence } from '../../lib/types';

const FALLBACK = FALLBACK_CENTRES[0];

const ENGINE_ICONS: Record<string, typeof Users> = {
  attendance: Users,
  practical_activity: Activity,
  infrastructure: HardHat,
  camera_integrity: Camera,
  evidence_integrity: FileCheck2,
  apparent_operability: Gauge,
};

export default function CentreOverview() {
  const { centreId } = useParams<{ centreId: string }>();
  const id = String(centreId);
  const { period } = useBriefPeriod();
  const [centre, setCentre] = useState<Centre | null>(null);
  const [intelligence, setIntelligence] = useState<CentreIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [degraded, setDegraded] = useState(false);
  const [analysisOpen, setAnalysisOpen] = useState(false);

  async function load() {
    setLoading(true);
    setDegraded(false);
    try {
      const [current, currentIntelligence] = await Promise.all([
        getCentre(id),
        getCentreIntelligence(id, period),
      ]);
      setCentre(current);
      setIntelligence(currentIntelligence);
    } catch {
      setCentre(FALLBACK_CENTRES.find(item => item.centre_id === id) || FALLBACK);
      setIntelligence(null);
      setDegraded(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [id, period]);

  const current = centre || FALLBACK_CENTRES.find(item => item.centre_id === id) || FALLBACK;
  const meta = intelligence?.centre;
  const engines = intelligence?.engines || [];
  const actions = intelligence?.actions || [];
  const recent = intelligence?.period_activity.recent_analyses || [];

  const fallbackHeadline = useMemo(() => {
    if (current.camera_status === 'attention' || current.camera_status === 'blocked') {
      return "Camera trust is limiting this centre's conclusions.";
    }
    if (current.pending_cases > 0) return 'This centre needs officer attention.';
    if (current.status === 'compliant') return 'Latest trusted checks are aligned.';
    return 'Some centre checks do not yet have a trusted conclusion.';
  }, [current]);

  function askAssistant() {
    window.dispatchEvent(new Event('kaushalwatch:assistant'));
  }

  return (
    <div>
      <Link href="/centres" className="kw-focus mb-5 inline-flex items-center gap-1.5 rounded-md text-[12px] font-medium text-[#667085] hover:text-[#344054]">
        <ArrowLeft size={14} />
        Centres
      </Link>

      <header className="mb-6 flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[32px] font-semibold tracking-[-0.04em] text-[var(--kw-text)]">{meta?.name || current.name}</h1>
            {(intelligence?.simulated || degraded) && (
              <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[10px] font-medium text-[#667085]">
                {degraded ? 'Simulated centre metadata' : 'Simulated demo data'}
              </span>
            )}
          </div>
          <p className="mt-1 text-[14px] text-[var(--kw-muted)]">{meta?.job_role || current.job_role} · {meta?.batch_id || current.batch_id}</p>
          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[12px] text-[#98A2B3]">
            <span>{meta?.location || current.location}</span>
            <span>Camera {meta?.camera_id || current.camera_id}</span>
            <span>{intelligence?.period_label || 'Current'} view</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={askAssistant}><Bot size={16} /> Ask KaushalAI</Button>
          <Button variant="primary" onClick={() => setAnalysisOpen(true)}><Play size={16} /> Run analysis</Button>
        </div>
      </header>

      <CentreTabs centreId={id} />

      {degraded && (
        <div role="alert" className="mb-5 rounded-xl border border-[#F2D3A2] bg-[#FFFBF5] px-5 py-4 text-[13px] leading-5 text-[#8A4B12]">
          Live centre intelligence is unavailable. Centre identity metadata is simulated fallback data; verification states, recommendations and recent analysis are not being inferred.
        </div>
      )}

      <section className="relative overflow-hidden rounded-[18px] border border-[var(--kw-border)] bg-white px-7 py-7 shadow-[var(--kw-shadow)]">
        <div className="relative z-10 max-w-[760px]">
          <div className="flex items-center gap-2 text-[12px] font-medium text-[var(--kw-accent-strong)]">
            <Bot size={14} />
            KaushalAI centre brief
          </div>
          <h2 className="mt-3 text-[26px] font-semibold leading-[1.25] tracking-[-0.03em] text-[var(--kw-text)]">
            {loading
              ? 'Refreshing centre intelligence…'
              : intelligence?.brief.headline || 'Live centre intelligence is unavailable.'}
          </h2>
          <div className="mt-5 space-y-2.5">
            {(intelligence?.brief.bullets || [loading ? 'Centre intelligence is loading from the latest trusted evidence.' : 'No verification conclusion is shown while the intelligence service is unavailable.']).slice(0, 4).map(line => (
              <div key={line} className="flex items-start gap-3 text-[13px] leading-5 text-[#475467]">
                <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-[#6B8AB5]" />
                <span>{line}</span>
              </div>
            ))}
          </div>
          <div className="mt-5 text-[11px] text-[#98A2B3]">
            {loading
              ? 'Refreshing centre intelligence…'
              : intelligence
                ? 'Grounded in ' + intelligence.period_activity.analysis_runs + ' analysis runs for ' + intelligence.period_label.toLowerCase() + '.'
                : 'Live centre intelligence is unavailable; showing centre metadata only.'}
          </div>
        </div>
        <div className="pointer-events-none absolute -right-10 -top-10 h-56 w-56 rounded-full bg-[#F1F6FD]" />
        <div className="pointer-events-none absolute right-10 top-1/2 flex h-20 w-20 -translate-y-1/2 items-center justify-center rounded-full border border-[#DCE8FA] bg-[#F9FBFF] text-[#9CB5D7]">
          <Building2 size={32} strokeWidth={1.2} />
        </div>
      </section>

      <section className="mt-7">
        <div className="mb-3">
          <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Verification engines</h2>
          <p className="mt-0.5 text-[12px] text-[#98A2B3]">Status, reason, then drill down only when needed.</p>
        </div>

        {engines.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {engines.map(engine => <EngineCard key={engine.key} engine={engine} centreId={id} />)}
          </div>
        ) : (
          <div className="rounded-[18px] border border-[var(--kw-border)] bg-white px-6 py-8 text-[13px] text-[#667085]">
            Engine summaries are unavailable until the centre intelligence service responds.
          </div>
        )}
      </section>

      <div className="mt-7 grid gap-7 lg:grid-cols-[1fr_340px]">
        <section className="rounded-[18px] border border-[var(--kw-border)] bg-white px-6 py-5 shadow-[var(--kw-shadow)]">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Recent analysis</h2>
              <p className="mt-0.5 text-[12px] text-[#98A2B3]">{intelligence?.period_label || 'Selected period'} · latest recorded runs</p>
            </div>
            <span className="text-[12px] text-[#98A2B3]">{intelligence?.period_activity.analysis_runs || 0} runs</span>
          </div>

          {recent.length ? (
            <div className="mt-3 divide-y divide-[#EEF2F6]">
              {recent.slice(0, 4).map(row => (
                <div key={row.analysis_id} className="grid gap-2 py-4 md:grid-cols-[130px_1fr_auto] md:items-center">
                  <div>
                    <div className="text-[12px] font-semibold capitalize text-[var(--kw-text)]">{row.analysis_type.replaceAll('_', ' ')}</div>
                    <div className="mt-0.5 text-[10px] text-[#98A2B3]">{new Date(row.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}</div>
                  </div>
                  <div className="truncate text-[12px] text-[var(--kw-muted)]">{row.summary}</div>
                  <StatusPill state={analysisState(row.outcome)} />
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-5 rounded-xl bg-[#F8FAFC] px-5 py-6 text-[13px] text-[#667085]">
              {intelligence ? 'No new analysis runs were recorded in this period.' : 'Recent analysis is unavailable until centre intelligence responds.'}
            </div>
          )}
        </section>

        <aside className="space-y-4">
          <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]">
            <h2 className="text-[16px] font-semibold text-[var(--kw-text)]">Recommended next</h2>
            {actions.length ? (
              <div className="mt-3 divide-y divide-[#EEF2F6]">
                {actions.map((action, index) => (
                  <Link href={action.href} key={action.title} className="kw-focus flex items-start gap-3 rounded-md py-3.5">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#EFF6FF] text-[11px] font-semibold text-[var(--kw-accent-strong)]">{index + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] font-semibold text-[var(--kw-text)]">{action.title}</div>
                      <div className="mt-1 text-[11px] leading-5 text-[var(--kw-muted)]">{action.reason}</div>
                    </div>
                    <ArrowRight size={14} className="mt-1 text-[#98A2B3]" />
                  </Link>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-[12px] leading-5 text-[#667085]">
                {intelligence ? 'No immediate officer action is recommended.' : 'Recommendations are unavailable until centre intelligence responds.'}
              </p>
            )}
          </section>

          <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]">
            <h2 className="text-[16px] font-semibold text-[var(--kw-text)]">Centre contact</h2>
            <div className="mt-3 text-[13px] font-medium text-[#475467]">{intelligence?.contact.role || 'Centre Head'}</div>
            <p className="mt-1 text-[12px] leading-5 text-[#98A2B3]">{intelligence?.contact.note || 'Contact details are not connected in this prototype.'}</p>
            <button type="button" disabled className="mt-4 h-9 cursor-not-allowed rounded-lg border border-[#E4E7EC] px-3 text-[12px] font-medium text-[#98A2B3]">
              Contact unavailable
            </button>
          </section>
        </aside>
      </div>

      <AnalysisModal open={analysisOpen} onOpenChange={setAnalysisOpen} centre={current} onComplete={updated => { setCentre(updated); void load(); }} />
    </div>
  );
}

function EngineCard({ engine, centreId }: { engine: CentreEngine; centreId: string }) {
  const Icon = ENGINE_ICONS[engine.key] || Activity;
  return (
    <Link href={'/centres/' + centreId + engine.href_suffix} className="kw-focus group rounded-[16px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)] transition-colors hover:border-[#CFD9E8]">
      <div className="flex items-start justify-between gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#F5F8FD] text-[#5E7DA8]"><Icon size={17} /></span>
        <StatusPill state={engine.state} label={engine.label || undefined} />
      </div>
      <div className="mt-4 text-[14px] font-semibold text-[var(--kw-text)]">{engine.name}</div>
      <p className="mt-1.5 min-h-10 text-[12px] leading-5 text-[var(--kw-muted)]">{engine.summary}</p>
      <div className="mt-3 flex items-center gap-1 text-[11px] font-medium text-[#98A2B3] group-hover:text-[var(--kw-accent-strong)]">View detail <ArrowRight size={12} /></div>
    </Link>
  );
}

function analysisState(outcome: string): 'verified' | 'review' | 'uncertain' | 'unavailable' {
  const value = String(outcome || '').toLowerCase();
  if (value === 'compliant') return 'verified';
  if (value === 'attention') return 'review';
  if (value === 'blocked') return 'uncertain';
  return 'unavailable';
}
