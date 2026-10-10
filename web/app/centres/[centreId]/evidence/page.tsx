'use client';

import Link from 'next/link';
import {
  ArrowRight,
  Bot,
  Check,
  CircleAlert,
  FileSearch,
  Play,
  ShieldCheck,
} from 'lucide-react';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import AnalysisModal from '../../../components/AnalysisModal';
import CentreTabs from '../../../components/CentreTabs';
import { EvidenceFrame, StatusPill, TechnicalDetails } from '../../../components/CalmUi';
import { Button, buttonVariants } from '../../../components/ui/button';
import { API, getCases, getCentre } from '../../../lib/api';
import { FALLBACK_CENTRES, caseUiState, plainCaseType } from '../../../lib/presentation';
import type { CaseRecord, Centre } from '../../../lib/types';

const TERMINAL = new Set(['confirmed', 'false_positive', 'resolved']);

export default function EvidencePage() {
  const { centreId } = useParams<{ centreId: string }>();
  const id = String(centreId);
  const [centre, setCentre] = useState<Centre | null>(null);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [casesError, setCasesError] = useState('');
  const [centreDegraded, setCentreDegraded] = useState(false);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [selected, setSelected] = useState(0);

  async function load() {
    setLoading(true);
    setCasesError('');
    setCentreDegraded(false);
    const [centreResult, casesResult] = await Promise.allSettled([
      getCentre(id),
      getCases(),
    ]);

    if (centreResult.status === 'fulfilled') {
      setCentre(centreResult.value);
    } else {
      setCentre(FALLBACK_CENTRES.find(item => item.centre_id === id) || FALLBACK_CENTRES[0]);
      setCentreDegraded(true);
    }

    if (casesResult.status === 'fulfilled') {
      setCases(casesResult.value.filter(item => item.centre_id === id));
    } else {
      setCases([]);
      setCasesError('Case and evidence records are unavailable. No empty or healthy conclusion is being inferred.');
    }
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, [id]);

  const current = centre || FALLBACK_CENTRES.find(item => item.centre_id === id) || FALLBACK_CENTRES[0];
  const evidence = useMemo(() => cases.flatMap(item => item.evidence || []), [cases]);
  const chosen = evidence[selected] || evidence[0];
  const duplicateCount = evidence.filter(item => item.duplicate_of).length;
  const reviewCases = cases.filter(item => !TERMINAL.has(item.status));
  const integrityState = casesError ? 'unavailable' : duplicateCount ? 'review' : evidence.length ? 'verified' : 'unavailable';
  // A centre with no active camera alarm is NOT proof of a trusted stream.
  // Only an explicit blocker supports an untrusted label; otherwise abstain.
  const cameraTrust: boolean | undefined = centreDegraded ? undefined
    : ['attention', 'blocked'].includes(String(current.camera_status).toLowerCase()) ? false : undefined;
  const src = chosen?.evidence_id ? API + '/evidence/' + chosen.evidence_id + '.jpg' : undefined;
  const simulated = Boolean(chosen?.metadata?.simulated);

  return (
    <div>
      <header className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-[32px] font-semibold tracking-[-0.04em] text-[var(--kw-text)]">Evidence</h1>
          <p className="mt-1 text-[14px] text-[var(--kw-muted)]">Retained visual evidence, integrity signals, and cases that need an officer decision.</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <StatusPill state={integrityState} />
            {simulated && <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[10px] font-medium text-[#667085]">Simulated evidence</span>}
            {centreDegraded && <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[10px] font-medium text-[#667085]">Simulated centre metadata</span>}
            <span className="text-[11px] text-[#98A2B3]">
              {casesError ? 'Evidence records unavailable' : loading ? 'Loading evidence…' : evidence.length + ' retained item' + (evidence.length === 1 ? '' : 's')}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={() => window.dispatchEvent(new Event('kaushalwatch:assistant'))}>
            <Bot size={16} />
            Ask KaushalAI
          </Button>
          <Button variant="secondary" onClick={() => setAnalysisOpen(true)}>
            <Play size={16} />
            Run analysis
          </Button>
          {reviewCases[0] && (
            <Link href={'/cases/' + reviewCases[0].case_id} className={buttonVariants({ variant: 'primary' })}>
              <FileSearch size={15} />
              Review case
            </Link>
          )}
        </div>
      </header>

      <CentreTabs centreId={id} />

      {(casesError || centreDegraded) && (
        <div role="alert" className="mb-5 rounded-xl border border-[#F2D3A2] bg-[#FFFBF5] px-5 py-4 text-[13px] leading-5 text-[#8A4B12]">
          {casesError || 'Live centre metadata is unavailable. Camera trust is not being inferred from fallback metadata.'}
        </div>
      )}

      <section className="grid gap-7 lg:grid-cols-[1.15fr_.85fr]">
        <div>
          <EvidenceFrame
            src={src}
            timestamp={chosen?.created_at ? new Date(chosen.created_at).toLocaleString() : undefined}
            trusted={cameraTrust}
            emptyText={casesError ? 'Evidence records unavailable' : 'Evidence preview appears after analysis'}
          />

          {evidence.length > 1 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {evidence.slice(0, 6).map((item, index) => (
                <button
                  key={item.evidence_id}
                  type="button"
                  onClick={() => setSelected(index)}
                  className={
                    'kw-focus rounded-lg border px-3 py-2 text-[11px] font-medium ' +
                    (index === selected
                      ? 'border-[#93B4F6] bg-[#EFF6FF] text-[#1D4ED8]'
                      : 'border-[#E6EAF0] bg-white text-[#667085]')
                  }
                >
                  Evidence {index + 1}
                </button>
              ))}
            </div>
          )}

          <TechnicalDetails>
            {chosen ? (
              <>
                <p>Evidence ID: {chosen.evidence_id}</p>
                <p className="break-all">SHA-256: {chosen.sha256 || 'Not available'}</p>
                <p>Perceptual hash: {chosen.perceptual_hash || 'Not available'}</p>
                <p>Duplicate of: {chosen.duplicate_of || 'None'}</p>
              </>
            ) : (
              <p>Technical integrity details appear after retained evidence is recorded.</p>
            )}
          </TechnicalDetails>
        </div>

        <div className="space-y-5">
          <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-[16px] font-semibold text-[var(--kw-text)]">Evidence integrity</h2>
                <p className="mt-1 text-[12px] text-[#98A2B3]">Integrity is reviewed separately from the compliance finding.</p>
              </div>
              <StatusPill state={integrityState} />
            </div>

            <div className="mt-5 space-y-3">
              <IntegrityRow
                ok={Boolean(chosen?.sha256)}
                label={chosen?.sha256 ? 'SHA-256 retained' : 'SHA-256 unavailable'}
                unavailable={!chosen}
              />
              <IntegrityRow
                ok={!duplicateCount && evidence.length > 0}
                label={duplicateCount ? duplicateCount + ' possible duplicate' + (duplicateCount === 1 ? '' : 's') : evidence.length ? 'No duplicate signal' : 'Duplicate check unavailable'}
                unavailable={!evidence.length}
              />
              <IntegrityRow
                ok={false}
                label={centreDegraded ? 'Camera trust unavailable' : cameraTrust === false ? 'Camera trust needs verification' : 'Camera trust not independently verified'}
                unavailable={cameraTrust === undefined}
              />
              <IntegrityRow
                ok={true}
                label="Position tracked, not identity"
                unavailable={false}
              />
            </div>
          </section>

          <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-[16px] font-semibold text-[var(--kw-text)]">Cases requiring review</h2>
                <p className="mt-1 text-[12px] text-[#98A2B3]">Open evidence-backed decisions for this centre.</p>
              </div>
              <span className="text-[12px] font-medium text-[#667085]">{reviewCases.length}</span>
            </div>

            {reviewCases.length ? (
              <div className="mt-3 divide-y divide-[#EEF2F6]">
                {reviewCases.slice(0, 4).map(item => (
                  <Link key={item.case_id} href={'/cases/' + item.case_id} className="kw-focus flex items-start gap-3 rounded-md py-3.5">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[13px] font-semibold text-[var(--kw-text)]">{plainCaseType(item.case_type)}</span>
                        <StatusPill state={caseUiState(item)} label={item.status.replaceAll('_', ' ').toUpperCase()} />
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-[#667085]">{item.summary}</p>
                    </div>
                    <ArrowRight size={14} className="mt-1 text-[#98A2B3]" />
                  </Link>
                ))}
              </div>
            ) : (
              <div className="mt-4 rounded-xl bg-[#F8FAFC] px-4 py-5 text-[12px] text-[#667085]">
                {casesError ? 'Case records are unavailable. No empty queue conclusion is being shown.' : 'No open officer-review case for this centre.'}
              </div>
            )}
          </section>
        </div>
      </section>

      <AnalysisModal
        open={analysisOpen}
        onOpenChange={setAnalysisOpen}
        centre={current}
        onComplete={updated => {
          setCentre(updated);
          void load();
        }}
      />
    </div>
  );
}

function IntegrityRow({
  ok,
  label,
  unavailable,
}: {
  ok: boolean;
  label: string;
  unavailable: boolean;
}) {
  const Icon = unavailable ? CircleAlert : ok ? Check : ShieldCheck;
  const tone = unavailable ? 'text-[#667085]' : ok ? 'text-[#067647]' : 'text-[#B54708]';
  return (
    <div className={'flex items-center gap-2 text-[12px] ' + tone}>
      <Icon size={14} />
      <span>{label}</span>
    </div>
  );
}
