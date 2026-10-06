'use client';

import Link from 'next/link';
import { ArrowRight, Building2, Camera, FileSearch, Phone, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { getCentres } from './lib/api';
import { aiFirstCentres, centreReason, centreUiState, FALLBACK_CENTRES } from './lib/presentation';
import type { Centre } from './lib/types';
import { StatusPill } from './components/CalmUi';
import { buttonVariants } from './components/ui/button';

export default function KaushalAIHome() {
  const [centres, setCentres] = useState<Centre[]>(aiFirstCentres(FALLBACK_CENTRES));

  useEffect(() => {
    getCentres()
      .then(payload => setCentres(aiFirstCentres(payload.centres.length ? payload.centres : FALLBACK_CENTRES)))
      .catch(() => setCentres(aiFirstCentres(FALLBACK_CENTRES)));
  }, []);

  const counts = useMemo(() => ({
    verified: centres.filter(item => centreUiState(item) === 'verified').length,
    review: centres.filter(item => centreUiState(item) === 'review').length,
    uncertain: centres.filter(item => centreUiState(item) === 'uncertain').length,
  }), [centres]);

  const attention = centres.filter(item => centreUiState(item) !== 'verified').slice(0, 3);
  const priority = attention[0] || centres[0];

  return (
    <div>
      <div className="mb-8">
        <div className="flex items-center gap-2 text-[13px] font-medium text-[#155EEF]">
          <Sparkles size={15} />
          Daily intelligence
        </div>
        <h1 className="mt-2 text-[34px] font-medium tracking-[-0.035em] text-[#152238]">KaushalAI</h1>
        <p className="mt-1 text-[15px] text-[#667085]">AI-powered compliance intelligence for PMKVY centres.</p>
      </div>

      <section className="relative overflow-hidden rounded-[18px] border border-[#E3EAF3] bg-white px-8 py-8 shadow-[0_1px_3px_rgba(16,24,40,.04)]">
        <div className="max-w-[720px]">
          <div className="text-[12px] font-medium uppercase tracking-[0.15em] text-[#7C8AA5]">Yesterday</div>
          <h2 className="mt-3 text-[30px] font-medium leading-[1.2] tracking-[-0.03em] text-[#152238]">
            {counts.verified} of {centres.length} centres were verified.
          </h2>
          <div className="mt-6 space-y-3 text-[15px] text-[#475467]">
            <p>{counts.review} centres need officer review based on persistent evidence.</p>
            <p>{counts.uncertain} centre has an uncertain conclusion because camera trust dropped.</p>
            <p>KaushalAI recommends reviewing {priority?.name || 'the highest-priority centre'} first.</p>
          </div>
          {priority && (
            <Link href={`/centres/${priority.centre_id}`} className={buttonVariants({ variant: 'primary', className: 'mt-7' })}>
              Review {priority.name}
              <ArrowRight size={16} />
            </Link>
          )}
        </div>
        <div className="pointer-events-none absolute -right-16 -top-20 h-72 w-72 rounded-full bg-[#EEF5FF]" />
        <div className="pointer-events-none absolute right-12 top-14 flex h-28 w-28 items-center justify-center rounded-full border border-[#DCE8FA] bg-[#F7FAFF] text-[#93B4E8]">
          <Building2 size={44} strokeWidth={1.2} />
        </div>
      </section>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_330px]">
        <section className="rounded-[18px] border border-[#E3EAF3] bg-white px-6 py-5 shadow-[0_1px_3px_rgba(16,24,40,.04)]">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-[18px] font-medium text-[#152238]">Centres at a glance</h2>
              <p className="mt-0.5 text-[13px] text-[#98A2B3]">Five centres · one-line context</p>
            </div>
            <Link href="/centres" className="text-[13px] font-medium text-[#155EEF]">View all</Link>
          </div>

          <div className="divide-y divide-[#EEF2F6]">
            {centres.map(centre => (
              <Link
                href={`/centres/${centre.centre_id}`}
                key={centre.centre_id}
                className="kw-focus grid gap-2 py-4 transition-colors hover:bg-[#FBFCFE] md:grid-cols-[180px_1fr_auto] md:items-center"
              >
                <div>
                  <div className="text-[14px] font-medium text-[#152238]">{centre.name}</div>
                  <div className="mt-0.5 text-[12px] text-[#98A2B3]">{centre.district}</div>
                </div>
                <div className="truncate text-[13px] text-[#667085]">{centreReason(centre)}</div>
                <StatusPill state={centreUiState(centre)} />
              </Link>
            ))}
          </div>
        </section>

        <aside className="rounded-[18px] border border-[#E3EAF3] bg-white px-5 py-5 shadow-[0_1px_3px_rgba(16,24,40,.04)]">
          <h2 className="text-[18px] font-medium text-[#152238]">Attention first</h2>
          <div className="mt-3 divide-y divide-[#EEF2F6]">
            {attention.map((centre, index) => (
              <Link href={`/centres/${centre.centre_id}`} key={centre.centre_id} className="kw-focus flex items-start gap-3 py-4">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#FFF4E5] text-[13px] font-medium text-[#B54708]">{index + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-[14px] font-medium text-[#152238]">{centre.name}</div>
                  <div className="mt-1 text-[12px] leading-5 text-[#667085]">{centreReason(centre)}</div>
                </div>
              </Link>
            ))}
          </div>
        </aside>
      </div>

      <section className="mt-6 grid gap-3 rounded-[18px] border border-[#E3EAF3] bg-white p-4 shadow-[0_1px_3px_rgba(16,24,40,.04)] md:grid-cols-3">
        <QuickAction icon={FileSearch} title="Review evidence" body="Open the highest-priority case." href="/actions" />
        <QuickAction icon={Phone} title="Contact centre head" body="Follow up where context is needed." href="/actions" />
        <QuickAction icon={Camera} title="Verify camera issue" body="Resolve uncertain evidence first." href="/actions" />
      </section>
    </div>
  );
}

function QuickAction({ icon: Icon, title, body, href }: { icon: typeof FileSearch; title: string; body: string; href: string }) {
  return (
    <Link href={href} className="kw-focus flex items-center gap-3 rounded-xl px-3 py-3 transition-colors hover:bg-[#F8FAFC]">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#EFF6FF] text-[#155EEF]"><Icon size={17} /></span>
      <div className="min-w-0">
        <div className="text-[14px] font-medium text-[#152238]">{title}</div>
        <div className="mt-0.5 truncate text-[12px] text-[#667085]">{body}</div>
      </div>
    </Link>
  );
}
