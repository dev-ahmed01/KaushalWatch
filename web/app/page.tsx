'use client';

import Link from 'next/link';
import { ArrowRight, Building2, CheckCircle2, CircleAlert, CircleHelp, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { StatusPill } from './components/CalmUi';
import { buttonVariants } from './components/ui/button';
import { getKaushalBrief } from './lib/api';
import { aiFirstCentres, centreReason, centreUiState, FALLBACK_CENTRES } from './lib/presentation';
import { useBriefPeriod } from './lib/period';
import type { KaushalBrief, KaushalBriefCentre } from './lib/types';

type BriefState = 'verified' | 'review' | 'uncertain' | 'unavailable';

export default function KaushalAIHome() {
  const { period, label: selectedPeriodLabel } = useBriefPeriod();
  const [brief, setBrief] = useState<KaushalBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getKaushalBrief(period)
      .then(payload => {
        if (active) setBrief(payload);
      })
      .catch(() => {
        if (!active) return;
        setBrief(null);
        setError('Live grounded briefing is unavailable. The values below are clearly marked simulated demo fallback data.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [period]);

  const fallbackCentres = useMemo(() => aiFirstCentres(FALLBACK_CENTRES), []);

  const centres: KaushalBriefCentre[] = useMemo(() => {
    if (brief?.centres?.length) return brief.centres;
    return fallbackCentres.map(centre => ({
      centre_id: centre.centre_id,
      name: centre.name,
      location: centre.location,
      district: centre.district,
      job_role: centre.job_role,
      state: centreUiState(centre) as BriefState,
      reason: centreReason(centre),
      period_analysis_count: 0,
      period_attention_count: 0,
      analysis_types: {},
      open_case_count: centre.pending_cases || 0,
      escalation_level: centre.escalation?.level || 0,
      recommended_action: {
        label: 'View centre',
        href: '/centres/' + centre.centre_id,
      },
      simulated: true,
      href: '/centres/' + centre.centre_id,
    }));
  }, [brief, fallbackCentres]);

  const fallbackCounts = useMemo(() => ({
    total: centres.length,
    verified: centres.filter(item => item.state === 'verified').length,
    review: centres.filter(item => item.state === 'review').length,
    uncertain: centres.filter(item => item.state === 'uncertain').length,
    unavailable: centres.filter(item => item.state === 'unavailable').length,
  }), [centres]);

  const counts = brief?.counts || fallbackCounts;
  const usingFallback = !brief;
  const fallbackAttention = centres
    .filter(item => item.state !== 'verified')
    .slice(0, 3)
    .map(item => ({
      centre_id: item.centre_id,
      centre_name: item.name,
      state: item.state,
      reason: item.reason,
      label: item.recommended_action.label,
      href: item.recommended_action.href,
    }));
  const recommendations = brief?.recommendations?.length ? brief.recommendations : fallbackAttention;
  const priority = brief?.priority || recommendations[0] || null;
  const periodLabel = brief?.period_label || selectedPeriodLabel;
  const bullets = brief?.bullets?.length
    ? brief.bullets.slice(0, 3)
    : [
        counts.verified + ' centres had no persistent discrepancy requiring action.',
        counts.review + ' centres need officer review based on persistent evidence.',
        counts.uncertain + ' centre has an uncertain conclusion because camera trust dropped.',
      ];

  return (
    <div>
      <header className="mb-7">
        <div className="flex items-center gap-2 text-[12px] font-medium text-[var(--kw-accent-strong)]">
          <Sparkles size={14} />
          Grounded daily intelligence
        </div>
        <h1 className="mt-2 text-[34px] font-semibold tracking-[-0.04em] text-[var(--kw-text)]">KaushalAI</h1>
        <p className="mt-1 text-[14px] text-[var(--kw-muted)]">What changed, what needs attention, and what to do next.</p>
      </header>

      {error && !loading && (
        <div role="alert" className="mb-5 rounded-xl border border-[#F2D3A2] bg-[#FFFBF5] px-5 py-4 text-[13px] leading-5 text-[#8A4B12]">
          {error}
        </div>
      )}

      <section className="relative overflow-hidden rounded-[18px] border border-[var(--kw-border)] bg-white px-8 py-8 shadow-[var(--kw-shadow)]">
        <div className="relative z-10 max-w-[720px]">
          <div className="flex items-center gap-2">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#7C8AA5]">{periodLabel}</div>
            {(brief?.simulated || usingFallback) && (
              <span className="rounded-full bg-[#F2F4F7] px-2 py-0.5 text-[10px] font-medium text-[#667085]">
                {usingFallback ? 'Simulated fallback' : 'Simulated demo data'}
              </span>
            )}
          </div>

          <h2 className="mt-3 text-[30px] font-semibold leading-[1.18] tracking-[-0.035em] text-[var(--kw-text)]">
            {brief?.headline || counts.verified + ' of ' + counts.total + ' centres are verified.'}
          </h2>

          <div className="mt-6 space-y-3">
            {bullets.map((text, index) => (
              <BriefLine
                key={text}
                icon={index === 0 ? CheckCircle2 : index === 1 ? CircleAlert : CircleHelp}
                tone={index === 0 ? 'verified' : index === 1 ? 'review' : 'uncertain'}
                text={text}
              />
            ))}
          </div>

          {priority && (
            <div className="mt-7 flex items-center gap-4">
              <Link href={priority.href} className={buttonVariants({ variant: 'primary' })}>
                {priority.label}
                <ArrowRight size={15} />
              </Link>
              <span className="text-[12px] text-[#98A2B3]">{priority.centre_name} · recommended first</span>
            </div>
          )}

          <div className="mt-6 border-t border-[#EEF2F6] pt-4 text-[11px] text-[#98A2B3]">
            {loading ? (
              <span>Refreshing grounded evidence…</span>
            ) : brief ? (
              <span>
                Grounded in {brief.source_counts.analysis_rows_in_period} analysis runs in this period · {brief.source_counts.unresolved_or_confirmed_cases} active or confirmed cases
              </span>
            ) : (
              <span>{error}</span>
            )}
          </div>
        </div>

        <div className="pointer-events-none absolute -right-14 -top-16 h-72 w-72 rounded-full bg-[#F1F6FD]" />
        <div className="pointer-events-none absolute right-12 top-1/2 flex h-24 w-24 -translate-y-1/2 items-center justify-center rounded-full border border-[#DCE8FA] bg-[#F8FBFF] text-[#94AED2]">
          <Building2 size={38} strokeWidth={1.2} />
        </div>
      </section>

      <div className="mt-7 grid gap-7 lg:grid-cols-[1fr_300px]">
        <section className="rounded-[18px] border border-[var(--kw-border)] bg-white px-6 py-5 shadow-[var(--kw-shadow)]">
          <div className="mb-2 flex items-start justify-between">
            <div>
              <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Centres at a glance</h2>
              <p className="mt-0.5 text-[12px] text-[#98A2B3]">Current state · selected-period context</p>
            </div>
            <Link href="/centres" className="kw-focus rounded-md text-[12px] font-medium text-[var(--kw-accent-strong)]">View all</Link>
          </div>

          <div className="divide-y divide-[#EEF2F6]">
            {centres.map(centre => (
              <Link
                href={centre.href}
                key={centre.centre_id}
                className="kw-focus grid gap-2 rounded-md py-4 transition-colors hover:bg-[#FBFCFE] md:grid-cols-[170px_1fr_auto] md:items-center"
              >
                <div>
                  <div className="text-[13px] font-semibold text-[var(--kw-text)]">{centre.name}</div>
                  <div className="mt-0.5 text-[11px] text-[#98A2B3]">{centre.district}</div>
                </div>
                <div className="min-w-0">
                  <div className="truncate text-[12px] text-[var(--kw-muted)]">{centre.reason}</div>
                  {centre.period_analysis_count > 0 && (
                    <div className="mt-0.5 text-[10px] text-[#98A2B3]">{centre.period_analysis_count} analysis runs in {periodLabel.toLowerCase()}</div>
                  )}
                </div>
                <StatusPill state={centre.state} />
              </Link>
            ))}
          </div>
        </section>

        <aside className="rounded-[18px] border border-[var(--kw-border)] bg-white px-5 py-5 shadow-[var(--kw-shadow)]">
          <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Recommended next</h2>
          <p className="mt-1 text-[12px] text-[#98A2B3]">Ranked from current evidence and escalation state.</p>

          <div className="mt-3 divide-y divide-[#EEF2F6]">
            {recommendations.map((item, index) => (
              <Link href={item.href} key={item.centre_id} className="kw-focus flex items-start gap-3 rounded-md py-4">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#FFF4E5] text-[12px] font-semibold text-[#B54708]">{index + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-semibold text-[var(--kw-text)]">{item.centre_name}</div>
                  <div className="mt-1 text-[12px] leading-5 text-[var(--kw-muted)]">{item.reason}</div>
                  <div className="mt-1.5 text-[11px] font-medium text-[var(--kw-accent-strong)]">{item.label}</div>
                </div>
                <ArrowRight size={14} className="mt-1 text-[#98A2B3]" />
              </Link>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}

function BriefLine({
  icon: Icon,
  tone,
  text,
}: {
  icon: typeof CheckCircle2;
  tone: 'verified' | 'review' | 'uncertain';
  text: string;
}) {
  const tones = {
    verified: 'bg-[var(--kw-verified-bg)] text-[var(--kw-verified)]',
    review: 'bg-[var(--kw-review-bg)] text-[var(--kw-review)]',
    uncertain: 'bg-[var(--kw-neutral-bg)] text-[var(--kw-neutral)]',
  };

  return (
    <div className="flex items-center gap-3">
      <span className={'flex h-8 w-8 shrink-0 items-center justify-center rounded-full ' + tones[tone]}>
        <Icon size={16} />
      </span>
      <span className="text-[14px] text-[#475467]">{text}</span>
    </div>
  );
}
