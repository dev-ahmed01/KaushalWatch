'use client';

import Link from 'next/link';
import { ArrowRight, Building2, CheckCircle2, CircleAlert, CircleHelp, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { StatusPill } from './components/CalmUi';
import { buttonVariants } from './components/ui/button';
import { getCentres } from './lib/api';
import { aiFirstCentres, centreReason, centreUiState, FALLBACK_CENTRES } from './lib/presentation';
import type { Centre } from './lib/types';

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
      <header className="mb-7">
        <div className="flex items-center gap-2 text-[12px] font-medium text-[var(--kw-accent-strong)]">
          <Sparkles size={14} />
          Daily intelligence
        </div>
        <h1 className="mt-2 text-[34px] font-semibold tracking-[-0.04em] text-[var(--kw-text)]">KaushalAI</h1>
        <p className="mt-1 text-[14px] text-[var(--kw-muted)]">What changed, what needs attention, and what to do next.</p>
      </header>

      <section className="relative overflow-hidden rounded-[18px] border border-[var(--kw-border)] bg-white px-8 py-8 shadow-[var(--kw-shadow)]">
        <div className="relative z-10 max-w-[700px]">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#7C8AA5]">Yesterday</div>
          <h2 className="mt-3 text-[30px] font-semibold leading-[1.18] tracking-[-0.035em] text-[var(--kw-text)]">
            {counts.verified} of {centres.length} centres were verified.
          </h2>

          <div className="mt-6 space-y-3">
            <BriefLine
              icon={CheckCircle2}
              tone="verified"
              text={counts.verified + ' centres had no persistent discrepancy requiring action.'}
            />
            <BriefLine
              icon={CircleAlert}
              tone="review"
              text={counts.review + ' centres need officer review based on persistent evidence.'}
            />
            <BriefLine
              icon={CircleHelp}
              tone="uncertain"
              text={counts.uncertain + ' centre has an uncertain conclusion because camera trust dropped.'}
            />
          </div>

          {priority && (
            <div className="mt-7 flex items-center gap-4">
              <Link href={'/centres/' + priority.centre_id} className={buttonVariants({ variant: 'primary' })}>
                Review {priority.name}
                <ArrowRight size={15} />
              </Link>
              <span className="text-[12px] text-[#98A2B3]">Recommended first action</span>
            </div>
          )}
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
              <p className="mt-0.5 text-[12px] text-[#98A2B3]">Five centres · one line of context each</p>
            </div>
            <Link href="/centres" className="kw-focus rounded-md text-[12px] font-medium text-[var(--kw-accent-strong)]">View all</Link>
          </div>

          <div className="divide-y divide-[#EEF2F6]">
            {centres.map(centre => (
              <Link
                href={'/centres/' + centre.centre_id}
                key={centre.centre_id}
                className="kw-focus grid gap-2 rounded-md py-4 transition-colors hover:bg-[#FBFCFE] md:grid-cols-[170px_1fr_auto] md:items-center"
              >
                <div>
                  <div className="text-[13px] font-semibold text-[var(--kw-text)]">{centre.name}</div>
                  <div className="mt-0.5 text-[11px] text-[#98A2B3]">{centre.district}</div>
                </div>
                <div className="truncate text-[12px] text-[var(--kw-muted)]">{centreReason(centre)}</div>
                <StatusPill state={centreUiState(centre)} />
              </Link>
            ))}
          </div>
        </section>

        <aside className="rounded-[18px] border border-[var(--kw-border)] bg-white px-5 py-5 shadow-[var(--kw-shadow)]">
          <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Attention first</h2>
          <p className="mt-1 text-[12px] text-[#98A2B3]">Only items requiring a human next step.</p>

          <div className="mt-3 divide-y divide-[#EEF2F6]">
            {attention.map((centre, index) => (
              <Link href={'/centres/' + centre.centre_id} key={centre.centre_id} className="kw-focus flex items-start gap-3 rounded-md py-4">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#FFF4E5] text-[12px] font-semibold text-[#B54708]">{index + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-semibold text-[var(--kw-text)]">{centre.name}</div>
                  <div className="mt-1 text-[12px] leading-5 text-[var(--kw-muted)]">{centreReason(centre)}</div>
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
