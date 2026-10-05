'use client';

import Link from 'next/link';
import { ChevronRight, Filter, ShieldAlert } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { EmptyState, PageTitle, StatusPill } from '../components/CalmUi';
import { buttonVariants } from '../components/ui/button';
import { getCases, getCentres } from '../lib/api';
import { cn } from '../lib/cn';
import { DEMO_CASES } from '../lib/demoCases';
import { FALLBACK_CENTRES, caseUiState, plainCaseType } from '../lib/presentation';
import type { CaseRecord, Centre } from '../lib/types';

export default function CasesPage() {
  const [cases, setCases] = useState<CaseRecord[]>(DEMO_CASES);
  const [centres, setCentres] = useState<Centre[]>(FALLBACK_CENTRES);
  const [tab, setTab] = useState<'review' | 'escalations'>('review');
  const [priority, setPriority] = useState<'all' | 'high' | 'medium'>('all');
  const [centreFilter, setCentreFilter] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('tab') === 'escalations') setTab('escalations');
    setCentreFilter(params.get('centre') || '');
    Promise.all([getCases().catch(() => []), getCentres().catch(() => ({ centres: FALLBACK_CENTRES, total: FALLBACK_CENTRES.length }))])
      .then(([liveCases, centrePayload]) => {
        setCases(liveCases.length ? liveCases : DEMO_CASES);
        setCentres(centrePayload.centres.length ? centrePayload.centres : FALLBACK_CENTRES);
      });
  }, []);

  const centreName = (id: string) => centres.find(c => c.centre_id === id)?.name || id;
  const activeCases = useMemo(() => cases.filter(item => !['resolved', 'false_positive', 'confirmed'].includes(item.status)), [cases]);
  const filtered = useMemo(() => {
    const rank: Record<string, number> = { high: 0, medium: 1, low: 2 };
    return activeCases
      .filter(item => (!centreFilter || item.centre_id === centreFilter) && (priority === 'all' || item.severity === priority))
      .sort((a, b) => (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3));
  }, [activeCases, centreFilter, priority]);
  const escalated = useMemo(() => centres.filter(c => c.escalation?.level > 0 && (!centreFilter || c.centre_id === centreFilter) && (priority === 'all' || (priority === 'high' ? (c.escalation?.level || 0) >= 3 : (c.escalation?.level || 0) < 3))).sort((a, b) => (b.escalation?.level || 0) - (a.escalation?.level || 0)), [centres, centreFilter, priority]);
  const highest = filtered[0];

  return (
    <div>
      <PageTitle title="Cases" description="Evidence-backed discrepancies awaiting officer decisions." action={highest ? <Link href={`/cases/${highest.case_id}`} className={buttonVariants({ variant: 'primary' })}>Open highest priority</Link> : undefined} />

      <div className="mb-10 flex flex-wrap items-center justify-between gap-4 border-b border-[#E6EAF0]">
        <div className="flex gap-1">
          <button type="button" onClick={() => setTab('review')} className={cn('kw-focus relative px-4 py-3 text-[14px] font-medium', tab === 'review' ? 'text-[#1D4ED8]' : 'text-[#667085]')}>Review Queue{tab === 'review' && <span className="absolute inset-x-3 bottom-[-1px] h-0.5 bg-[#2563EB]" />}</button>
          <button type="button" onClick={() => setTab('escalations')} className={cn('kw-focus relative px-4 py-3 text-[14px] font-medium', tab === 'escalations' ? 'text-[#1D4ED8]' : 'text-[#667085]')}>Escalations{tab === 'escalations' && <span className="absolute inset-x-3 bottom-[-1px] h-0.5 bg-[#2563EB]" />}</button>
        </div>
        <label className="mb-2 flex items-center gap-2 text-[13px] text-[#667085]"><Filter size={15} /> Priority<select value={priority} onChange={event => setPriority(event.target.value as any)} className="h-9 rounded-lg border border-[#D7DCE3] bg-white px-3 text-[13px] text-[#344054] outline-none"><option value="all">All</option><option value="high">High</option><option value="medium">Medium</option></select></label>
      </div>

      {tab === 'review' ? (
        filtered.length ? <section className="space-y-2">
          {filtered.map(record => (
            <Link href={`/cases/${record.case_id}`} key={record.case_id} className="kw-focus grid min-h-24 gap-4 rounded-2xl border border-[#E6EAF0] bg-white px-6 py-5 transition-colors hover:bg-[#FBFCFD] md:grid-cols-[1fr_180px_150px_auto] md:items-center">
              <div className="min-w-0"><div className="flex items-center gap-2"><span className="text-[15px] font-medium text-[#172033]">{plainCaseType(record.case_type)}</span>{record.case_id.startsWith('SIM-') && <span className="rounded-full bg-[#F2F4F7] px-2 py-0.5 text-[11px] text-[#667085]">Simulated</span>}</div><div className="mt-1 truncate text-[13px] text-[#667085]">{record.summary}</div></div>
              <div className="text-[13px] text-[#667085]"><div>{centreName(record.centre_id)}</div><div className="mt-0.5 text-[#98A2B3]">{record.batch_id}</div></div>
              <StatusPill state={caseUiState(record)} label={record.status.replaceAll('_', ' ').toUpperCase()} />
              <ChevronRight size={17} className="text-[#98A2B3]" />
            </Link>
          ))}
        </section> : <EmptyState title="No cases to review" body="No evidence-backed discrepancy currently needs an officer decision." />
      ) : (
        escalated.length ? <section className="space-y-2">
          {escalated.map(centre => <Link href={`/centres/${centre.centre_id}`} key={centre.centre_id} className="kw-focus flex min-h-24 items-center gap-5 rounded-2xl border border-[#E6EAF0] bg-white px-6 py-5 hover:bg-[#FBFCFD]">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FFFAEB] text-[#B54708]"><ShieldAlert size={19} /></span>
            <div className="min-w-0 flex-1"><div className="text-[15px] font-medium text-[#172033]">{centre.name}</div><div className="mt-1 truncate text-[13px] text-[#667085]">{centre.escalation?.reasons?.[0] || 'Persistent discrepancy requires review'}</div></div>
            <StatusPill state="review" label={centre.escalation?.label?.toUpperCase() || 'ESCALATED'} />
          </Link>)}
        </section> : <EmptyState title="No escalations" body="No persistent case currently meets an escalation rule." />
      )}

      <p className="mt-8 text-[13px] text-[#667085]">{activeCases.length} open review item{activeCases.length === 1 ? '' : 's'} · Escalation never confirms a compliance outcome automatically.</p>
    </div>
  );
}
