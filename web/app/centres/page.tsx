'use client';

import Link from 'next/link';
import { ArrowRight, Building2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { StatusPill } from '../components/CalmUi';
import { buttonVariants } from '../components/ui/button';
import { getCentres } from '../lib/api';
import { aiFirstCentres, centreReason, centreUiState, FALLBACK_CENTRES } from '../lib/presentation';
import type { Centre } from '../lib/types';

export default function CentresPage() {
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

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-[34px] font-medium tracking-[-0.035em] text-[#152238]">Centres</h1>
        <p className="mt-1 text-[15px] text-[#667085]">Five monitored centres, summarised by KaushalAI.</p>
      </div>

      <section className="mb-6 grid gap-3 md:grid-cols-3">
        <Summary value={counts.verified} label="Verified" tone="green" />
        <Summary value={counts.review} label="Need review" tone="amber" />
        <Summary value={counts.uncertain} label="Uncertain" tone="blue" />
      </section>

      <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <section className="rounded-[18px] border border-[#E3EAF3] bg-white px-6 py-5 shadow-[0_1px_3px_rgba(16,24,40,.04)]">
          <div className="mb-2 text-[18px] font-medium text-[#152238]">Centres ({centres.length})</div>
          <div className="divide-y divide-[#EEF2F6]">
            {centres.map(centre => (
              <div key={centre.centre_id} className="grid gap-4 py-4 md:grid-cols-[44px_1fr_auto] md:items-center">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#F5F8FD] text-[#6C86B4]"><Building2 size={19} /></span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[14px] font-medium text-[#152238]">{centre.name}</span>
                    <StatusPill state={centreUiState(centre)} />
                  </div>
                  <div className="mt-1 text-[12px] text-[#98A2B3]">{centre.location} · Construction Electrician-LV</div>
                  <div className="mt-1 truncate text-[13px] text-[#667085]">{centreReason(centre)}</div>
                </div>
                <Link href={`/centres/${centre.centre_id}`} className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
                  View centre <ArrowRight size={15} />
                </Link>
              </div>
            ))}
          </div>
        </section>

        <aside className="rounded-[18px] border border-[#E3EAF3] bg-white px-5 py-5 shadow-[0_1px_3px_rgba(16,24,40,.04)]">
          <h2 className="text-[18px] font-medium text-[#152238]">Attention first</h2>
          <div className="mt-3 space-y-1">
            {centres.filter(item => centreUiState(item) !== 'verified').slice(0, 3).map((centre, index) => (
              <Link href={`/centres/${centre.centre_id}`} key={centre.centre_id} className="kw-focus flex items-start gap-3 rounded-xl px-2 py-3 hover:bg-[#F8FAFC]">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#FFF4E5] text-[12px] font-medium text-[#B54708]">{index + 1}</span>
                <div>
                  <div className="text-[14px] font-medium text-[#152238]">{centre.name}</div>
                  <div className="mt-1 text-[12px] leading-5 text-[#667085]">{centreReason(centre)}</div>
                </div>
              </Link>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Summary({ value, label, tone }: { value: number; label: string; tone: 'green' | 'amber' | 'blue' }) {
  const tones = {
    green: 'bg-[#ECFDF3] text-[#067647]',
    amber: 'bg-[#FFF7E8] text-[#B54708]',
    blue: 'bg-[#EFF6FF] text-[#41658F]',
  };
  return (
    <div className="rounded-[16px] border border-[#E3EAF3] bg-white px-5 py-4 shadow-[0_1px_2px_rgba(16,24,40,.03)]">
      <div className="flex items-center gap-3">
        <span className={`flex h-9 w-9 items-center justify-center rounded-full text-[15px] font-medium ${tones[tone]}`}>{value}</span>
        <div><div className="text-[14px] font-medium text-[#152238]">{label}</div><div className="text-[12px] text-[#98A2B3]">centres</div></div>
      </div>
    </div>
  );
}
