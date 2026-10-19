'use client';

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
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

  const topAction = recommendations[0] || null;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[.15em] text-[#8B9AB2]">Operational overview</p>
          <h1 className="mt-1 text-[34px] font-bold tracking-[-.04em] text-[var(--kw-text)]">KaushalAI</h1>
        </div>
        <Link href="/actions" className="kw-focus inline-flex items-center gap-2 rounded-xl border border-[#D8E4F3] bg-white px-4 py-2 text-[12px] font-semibold text-[#365578] hover:bg-[#F5F9FF]">
          Review queue <ArrowRight size={15}/>
        </Link>
      </header>

      {error && !loading && <div role="alert" className="rounded-xl border border-[#F0DAB7] bg-[#FFFBF5] px-4 py-3 text-[12px] text-[#88591D]">{error}</div>}

      <section className="kw-os-hero rounded-[22px] border border-[#DFE8F5] px-6 py-7 shadow-[var(--kw-shadow)] sm:px-8 sm:py-9">
        <div className="relative z-10 max-w-[760px]">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-[.14em] text-[#647E9F]">{periodLabel}</span>
            {(brief?.simulated || usingFallback) && <span className="rounded-full bg-white/75 px-2 py-1 text-[10px] font-medium text-[#6B7890]">{usingFallback ? 'Simulated fallback' : 'Simulated demo data'}</span>}
          </div>
          <h2 className="mt-4 max-w-[610px] text-[clamp(25px,3.3vw,38px)] font-bold leading-[1.18] text-[#1F3958]">
            {brief?.headline || counts.verified + ' of ' + counts.total + ' centres are verified.'}
          </h2>
          <p className="mt-3 max-w-[630px] text-[13px] leading-6 text-[#526B87]">
            {bullets[1] || 'Evidence-backed discrepancies appear here for officer follow-up.'}
          </p>
          {priority&&<div className="mt-6 flex flex-wrap items-center gap-3">
            <Link href={priority.href} className={buttonVariants({variant:'primary'})}>
              {priority.label} <ArrowRight size={14}/>
            </Link>
            <span className="text-[12px] font-medium text-[#647B96]">{priority.centre_name}</span>
          </div>}
          {brief&&<p className="mt-4 text-[10px] font-medium text-[#8B9BB1]">
            Grounded in {brief.source_counts.analysis_rows_in_period} analysis runs
          </p>}
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Network verification statistics">
        {[
          ['Monitored sites',counts.total,'/centres'],
          ['Need review',counts.review,'/actions'],
          ['Uncertain',counts.uncertain,'/centres'],
          ['Verified',counts.verified,'/insights'],
        ].map(([label,value,href])=><Link href={String(href)} key={String(label)}
          className="kw-focus kw-os-card px-4 py-4 transition-colors hover:bg-[#FBFDFF] sm:px-5">
          <div className="text-[11px] font-medium text-[#76879D]">{label}</div>
          <div className="kw-os-stat mt-2 text-[32px] font-semibold tabular-nums text-[#243B55]">{value}</div>
        </Link>)}
      </section>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(270px,.75fr)]">
        <section className="kw-os-card min-w-0 p-5 sm:p-6">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div><h2 className="text-[18px] font-semibold">Centres at a glance</h2>
              <p className="mt-0.5 text-[11px] text-[#8190A4]">{counts.total} monitored centres</p></div>
            <Link href="/centres" className="kw-focus text-[12px] font-semibold text-[#1E61C9]">View all</Link>
          </div>
          <div className="divide-y divide-[#EDF1F6]">
            {centres.map(item=><Link href={item.href} key={item.centre_id}
              className="kw-focus flex min-w-0 items-center justify-between gap-3 rounded-lg py-3.5 transition hover:bg-[#FAFCFF]">
              <div className="min-w-0">
                <p className="truncate text-[13px] font-semibold text-[#233950]">{item.name}</p>
                <p className="mt-0.5 truncate text-[11px] text-[#7A8BA2]">{item.reason}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <StatusPill state={item.state}/>
                <ArrowRight size={14} className="hidden text-[#9BAFC3] sm:block"/>
              </div>
            </Link>)}
            {!centres.length&&!loading&&<p className="py-5 text-[13px] text-[#7C8BA0]">No centre records available.</p>}
          </div>
        </section>
        <aside className="kw-os-card min-w-0 p-5 sm:p-6">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-[18px] font-semibold">Needs attention</h2>
            <span className="text-[11px] font-medium text-[#8190A4]">{recommendations.length}</span>
          </div>
          <div className="divide-y divide-[#EEF2F6]">
            {recommendations.slice(0,4).map((item,index)=><Link href={item.href} key={item.centre_id}
              className="kw-focus flex gap-3 py-3.5">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#EFF5FF] text-[11px] font-semibold text-[#3164A1]">{index+1}</span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12px] font-semibold text-[#243B55]">{item.centre_name}</div>
                <div className="mt-1 line-clamp-2 text-[11px] leading-5 text-[#718199]">{item.reason}</div>
              </div>
              <ArrowRight size={14} className="mt-1 shrink-0 text-[#8EA3B8]"/>
            </Link>)}
            {!recommendations.length&&<p className="py-5 text-[12px] text-[#718199]">No follow-ups queued.</p>}
          </div>
          {topAction&&<Link href="/actions" className="kw-focus mt-3 inline-flex items-center gap-2 text-[12px] font-semibold text-[#2563EB]" >Open review queue <ArrowRight size={14}/></Link>}
        </aside>
      </div>
    </div>
  );

}

