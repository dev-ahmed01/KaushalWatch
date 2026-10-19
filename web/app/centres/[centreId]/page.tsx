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
import { useEffect, useState } from 'react';
import AnalysisModal from '../../components/AnalysisModal';
import CentreTabs from '../../components/CentreTabs';
import CentreVerificationCockpit from '../../components/CentreVerificationCockpit';
import { StatusPill } from '../../components/CalmUi';
import { Button } from '../../components/ui/button';
import { getCentre, getCentreIntelligence, SECURE_PROXY } from '../../lib/api';
import { DataRetry } from '../../components/NetworkStatus';
import { useBriefPeriod } from '../../lib/period';
import { FALLBACK_CENTRES } from '../../lib/presentation';
import type { Centre, CentreEngine, CentreIntelligence } from '../../lib/types';

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
  const [identityFallback,setIdentityFallback] = useState(false);
  const [retryKey,setRetryKey] = useState(0);
  const [analysisOpen, setAnalysisOpen] = useState(false);

  useEffect(() => {
    let active=true;
    async function load(){
      setLoading(true);
      setDegraded(false);
      setIdentityFallback(false);
      setIntelligence(null);
      setCentre(null);
      // Centre identity must not be substituted just because *intelligence* failed.
      const [centreResult,intelligenceResult] = await Promise.allSettled([
        getCentre(id),getCentreIntelligence(id,period)
      ]);
      if(!active)return;
      if(centreResult.status==='fulfilled'){
        setCentre(centreResult.value);
      }else{
        setIdentityFallback(true);
        setCentre(SECURE_PROXY?null:FALLBACK_CENTRES.find(item=>item.centre_id===id)||null);
      }
      if(intelligenceResult.status==='fulfilled'){
        setIntelligence(intelligenceResult.value);
      }else{
        setDegraded(true);
      }
      setLoading(false);
    }
    void load();
    return ()=>{active=false;};
  },[id,period,retryKey]);

  const current=centre;
  const identityUnavailable=!current;
  // A protected centre with unavailable identity must never inherit the
  // Bengaluru synthetic fixture, or leak a centre the officer cannot access.
  if(identityUnavailable){
    return <div className="space-y-4">
      <Link href="/centres" className="kw-focus text-[12px] font-medium text-[#667085]">← Centres</Link>
      <h1 className="text-[26px] font-semibold text-[#233952]">{loading?'Loading centre…':'Centre record unavailable'}</h1>
      <p role="status" className="text-[12px] text-[#718198]">{loading?'Opening the permitted centre record.':'No verified centre identity or measurements have been substituted.'}</p>
      {!loading&&<DataRetry onRetry={()=>setRetryKey(key=>key+1)} disabled={loading}/>}
    </div>;
  }

  const meta = intelligence?.centre;
  const engines = intelligence?.engines || [];
  const actions = intelligence?.actions || [];
  const recent = intelligence?.period_activity.recent_analyses || [];

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
            {(intelligence?.simulated || identityFallback) && (
              <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[10px] font-medium text-[#667085]">
                {identityFallback ? 'Simulated centre metadata' : 'Simulated demo data'}
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
      <section aria-label="Source and connectivity" className="mb-5 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-[#E6ECF4] bg-white px-4 py-3 text-[11px] text-[#61738C]">
        <span className="font-semibold text-[#405876]">{current.connectivity_mode==='low_bandwidth'?'Low-bandwidth centre':'Standard connectivity'}</span>
        <span>{current.last_analysis?'Last analysis: '+new Date(current.last_analysis).toLocaleString():'No analysis recorded'}</span>
        <span className="text-[#8796A9]">Recorded summaries · not a live video or sync indicator</span>
      </section>

      <div className="mt-5 mb-7">
        <CentreVerificationCockpit centreId={id} verification={intelligence?.verification||null}
          action={actions[0]||null} loading={loading}/>
      </div>

      {degraded && (
        <div role="alert" className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#F2D3A2] bg-[#FFFBF5] px-5 py-4 text-[13px] leading-5 text-[#8A4B12]">
          <span>Live centre intelligence is unavailable. Verification states, recommendations and recent analysis are not being inferred.</span>
          <DataRetry onRetry={()=>setRetryKey(key=>key+1)} disabled={loading}/>
        </div>
      )}
      {!loading && !intelligence && (
        <div className="mb-5 flex flex-col gap-1 rounded-xl border border-[#E4EAF2] bg-[#F9FBFE] px-4 py-3 text-[11px] text-[#667085]">
          <span>Recommendations are unavailable until centre intelligence responds.</span>
          <span>Recent analysis is unavailable until centre intelligence responds.</span>
        </div>
      )}

      <section className="kw-os-hero relative overflow-hidden rounded-[22px] border border-[var(--kw-border)] px-7 py-7 shadow-[var(--kw-shadow)]">
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
          <div className="mt-4 space-y-2">
            {(intelligence?.brief.bullets || [loading ? 'Centre intelligence is loading from the latest trusted evidence.' : 'No verification conclusion is shown while the intelligence service is unavailable.']).slice(0, 2).map(line => (
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
        <div className="pointer-events-none absolute -right-10 -top-10 h-56 w-56 rounded-full bg-[#F1F6FD]/50" />
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

      <details className="mt-6 rounded-2xl border border-[#E6EAF0] bg-white px-5 py-4 shadow-[var(--kw-shadow)]">
        <summary className="kw-focus flex cursor-pointer list-none items-center justify-between gap-3 text-[13px] font-semibold text-[#314763]">
          <span>Analysis history</span>
          <span className="text-[11px] font-normal text-[#8291A6]">{intelligence?.period_activity.analysis_runs ?? 0} runs · {intelligence?.period_label || 'Current'}</span>
        </summary>
        {recent.length ? (
          <div className="mt-4 divide-y divide-[#EEF2F6] border-t border-[#EEF2F6]">
            {recent.slice(0, 5).map(row => (
              <div key={row.analysis_id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div className="min-w-0 flex-1">
                  <div className="text-[12px] font-semibold capitalize text-[#314763]">{row.analysis_type.replaceAll('_', ' ')}</div>
                  <div className="mt-1 truncate text-[11px] text-[#78899F]">{row.summary}</div>
                  <time className="mt-1 block text-[10px] text-[#A1AEC0]" dateTime={row.created_at}>{new Date(row.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}</time>
                </div>
                <StatusPill state={analysisState(row.outcome)} />
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 border-t border-[#EEF2F6] pt-4 text-[12px] text-[#8291A6]">{intelligence ? 'No analysis recorded in this period.' : 'Analysis history unavailable.'}</p>
        )}
      </details>

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
