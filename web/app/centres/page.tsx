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
  const [centres, setCentres] = useState<Centre[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getCentres()
      .then(payload => {
        if (active) setCentres(aiFirstCentres(payload.centres, false));
      })
      .catch(() => {
        if (!active) return;
        setCentres(aiFirstCentres(FALLBACK_CENTRES));
        setError('Live centre records are unavailable. Showing clearly marked simulated demo fallback data.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const counts = useMemo(() => ({
    verified: centres.filter(item => centreUiState(item) === 'verified').length,
    review: centres.filter(item => centreUiState(item) === 'review').length,
    uncertain: centres.filter(item => centreUiState(item) === 'uncertain').length,
  }), [centres]);

  const attention = centres.filter(item => centreUiState(item) !== 'verified').slice(0, 3);

  return (
    <div>
      <header className="mb-7">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-[34px] font-semibold tracking-[-0.04em] text-[var(--kw-text)]">Centres</h1>
          {error && <span className="rounded-full bg-[#F2F4F7] px-2.5 py-1 text-[10px] font-medium text-[#667085]">Simulated fallback</span>}
        </div>
        <p className="mt-1 text-[14px] text-[var(--kw-muted)]">Five monitored centres, summarised by KaushalAI.</p>
      </header>

      {error && (
        <div role="alert" className="mb-5 rounded-xl border border-[#F2D3A2] bg-[#FFFBF5] px-5 py-4 text-[13px] leading-5 text-[#8A4B12]">
          {error}
        </div>
      )}

      {loading && centres.length === 0 ? (
        <div aria-live="polite" aria-busy="true" className="mb-6 grid gap-4 md:grid-cols-3">
          <div className="h-20 rounded-[18px] kw-skeleton" />
          <div className="h-20 rounded-[18px] kw-skeleton" />
          <div className="h-20 rounded-[18px] kw-skeleton" />
        </div>
      ) : (
      <section className="mb-6 grid divide-y divide-[#EEF2F6] rounded-[18px] border border-[var(--kw-border)] bg-white shadow-[var(--kw-shadow)] md:grid-cols-3 md:divide-x md:divide-y-0">
        <Summary value={counts.verified} label="Verified" note="No officer action" tone="green" />
        <Summary value={counts.review} label="Need review" note="Evidence requires attention" tone="amber" />
        <Summary value={counts.uncertain} label="Uncertain" note="Trust gate applied" tone="blue" />
      </section>
      )}

      <div className="grid gap-7 lg:grid-cols-[1fr_300px]">
        <section className="rounded-[18px] border border-[var(--kw-border)] bg-white px-6 py-5 shadow-[var(--kw-shadow)]">
          <div className="mb-2 text-[17px] font-semibold text-[var(--kw-text)]">Centres ({centres.length})</div>

          <div className="divide-y divide-[#EEF2F6]">
            {!loading && !error && centres.length === 0 && (
              <div className="py-10 text-center">
                <div className="text-[13px] font-medium text-[#475467]">No monitored centre records are available.</div>
                <p className="mt-1 text-[12px] text-[#98A2B3]">No demo values have been substituted for an empty live response.</p>
              </div>
            )}
            {centres.map(centre => (
              <div key={centre.centre_id} className="grid gap-4 py-4 md:grid-cols-[40px_1fr_auto] md:items-center">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#F5F8FD] text-[#6C86B4]">
                  <Building2 size={18} />
                </span>

                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[13px] font-semibold text-[var(--kw-text)]">{centre.name}</span>
                    <StatusPill state={centreUiState(centre)} />
                  </div>
                  <div className="mt-1 text-[11px] text-[#98A2B3]">{centre.location} · Construction Electrician-LV</div>
                  <div className="mt-1 truncate text-[12px] text-[var(--kw-muted)]">{centreReason(centre)}</div>
                </div>

                <Link href={'/centres/' + centre.centre_id} className={buttonVariants({ variant: 'secondary', size: 'sm' })}>
                  View
                  <ArrowRight size={14} />
                </Link>
              </div>
            ))}
          </div>
        </section>

        <aside className="rounded-[18px] border border-[var(--kw-border)] bg-white px-5 py-5 shadow-[var(--kw-shadow)]">
          <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Attention first</h2>
          <p className="mt-1 text-[12px] text-[#98A2B3]">Prioritised by evidence state.</p>

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

function Summary({
  value,
  label,
  note,
  tone,
}: {
  value: number;
  label: string;
  note: string;
  tone: 'green' | 'amber' | 'blue';
}) {
  const tones = {
    green: 'bg-[#ECFDF3] text-[#067647]',
    amber: 'bg-[#FFF7E8] text-[#B54708]',
    blue: 'bg-[#EFF6FF] text-[#41658F]',
  };

  return (
    <div className="flex items-center gap-3 px-5 py-4">
      <span className={'flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[14px] font-semibold ' + tones[tone]}>{value}</span>
      <div>
        <div className="text-[13px] font-semibold text-[var(--kw-text)]">{label}</div>
        <div className="mt-0.5 text-[11px] text-[#98A2B3]">{note}</div>
      </div>
    </div>
  );
}
