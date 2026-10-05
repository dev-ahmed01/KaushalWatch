'use client';

import Link from 'next/link';
import { List, Map as MapIcon, MapPin, RotateCcw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { buttonVariants } from './components/ui/button';
import { Button } from './components/ui/button';
import { PageTitle, StatusPill } from './components/CalmUi';
import { getCentres } from './lib/api';
import { cn } from './lib/cn';
import { centreReason, centreUiState, FALLBACK_CENTRES, NETWORK_SEED, simulatedFacts } from './lib/presentation';
import type { Centre } from './lib/types';

export default function NetworkPage() {
  const [centres, setCentres] = useState<Centre[]>(FALLBACK_CENTRES);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [view, setView] = useState<'map' | 'list'>('map');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const payload = await getCentres();
      setCentres(payload.centres.length ? payload.centres : FALLBACK_CENTRES);
    } catch (err) {
      setCentres(FALLBACK_CENTRES);
      setError('Live centre summaries are unavailable. Showing simulated demo states.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const ordered = useMemo(() => [...centres].sort((a, b) => {
    const rank = { review: 0, uncertain: 1, unavailable: 2, verified: 3 } as const;
    return rank[centreUiState(a) as keyof typeof rank] - rank[centreUiState(b) as keyof typeof rank];
  }), [centres]);
  const needsAttention = ordered.filter(c => centreUiState(c) !== 'verified').slice(0, 3);
  const counts = useMemo(() => ({
    verified: centres.filter(c => centreUiState(c) === 'verified').length,
    review: centres.filter(c => centreUiState(c) === 'review').length,
    uncertain: centres.filter(c => centreUiState(c) === 'uncertain').length,
    unavailable: centres.filter(c => centreUiState(c) === 'unavailable').length,
  }), [centres]);
  const priority = ordered[0] || FALLBACK_CENTRES[0];

  return (
    <div>
      <PageTitle
        title="Network"
        description="Exceptions first across Karnataka training centres."
        action={<Link href={`/centres/${priority.centre_id}`} className={buttonVariants({ variant: 'primary' })}>Open priority centre</Link>}
      />

      <section className="kw-surface overflow-hidden">
        <div className="flex items-center justify-between border-b border-[#EEF1F4] px-6 py-5">
          <div>
            <div className="text-[14px] font-medium text-[#172033]">Karnataka network</div>
            <div className="mt-1 text-[13px] text-[#667085]">{centres.length} centres · Simulated prototype data</div>
          </div>
          <div className="flex rounded-xl bg-[#F2F4F7] p-1" aria-label="Network view">
            <button type="button" onClick={() => setView('map')} className={cn('kw-focus flex h-9 items-center gap-2 rounded-lg px-3 text-[13px] font-medium', view === 'map' ? 'bg-white text-[#172033] shadow-sm' : 'text-[#667085]')}><MapIcon size={15} /> Map</button>
            <button type="button" onClick={() => setView('list')} className={cn('kw-focus flex h-9 items-center gap-2 rounded-lg px-3 text-[13px] font-medium', view === 'list' ? 'bg-white text-[#172033] shadow-sm' : 'text-[#667085]')}><List size={15} /> List</button>
          </div>
        </div>

        {view === 'map' ? (
          <div className="relative min-h-[480px] overflow-hidden bg-[#FBFCFD]">
            <svg className="absolute left-1/2 top-1/2 h-[390px] w-[540px] -translate-x-1/2 -translate-y-1/2 text-[#D8DEE7]" viewBox="0 0 500 360" aria-hidden="true">
              <path d="M156 24 L238 35 L289 63 L315 103 L353 124 L340 166 L371 208 L350 254 L316 276 L296 328 L242 338 L198 310 L169 275 L132 252 L112 211 L128 169 L106 131 L123 89 Z" fill="#F3F5F8" stroke="currentColor" strokeWidth="1.5" />
            </svg>
            <div className="absolute left-8 top-7 text-[13px] text-[#667085]"><b className="font-medium text-[#344054]">Karnataka</b><br />Approximate centre positions</div>
            {centres.map(centre => {
              const seed = NETWORK_SEED[centre.centre_id] || NETWORK_SEED['DEMO-KA-104'];
              const state = centreUiState(centre);
              const dot = state === 'verified' ? 'bg-[#067647]' : state === 'review' ? 'bg-[#B54708]' : state === 'uncertain' ? 'bg-[#98A2B3]' : 'bg-[#667085]';
              return (
                <Link
                  key={centre.centre_id}
                  href={`/centres/${centre.centre_id}`}
                  style={{ left: seed.map.left, top: seed.map.top }}
                  aria-label={`${centre.name}: ${centreReason(centre)}`}
                  className="group absolute -translate-x-1/2 -translate-y-1/2 text-center"
                >
                  <span className={cn('mx-auto block h-3.5 w-3.5 rounded-full border-[3px] border-white shadow-[0_0_0_1px_rgba(17,24,39,.12)] transition-transform duration-150 group-hover:scale-110', dot)} />
                  <span className="mt-2 block whitespace-nowrap rounded-full bg-white/95 px-2.5 py-1 text-[11px] font-medium text-[#475467] shadow-[0_1px_2px_rgba(16,24,40,.04)] ring-1 ring-[#E6EAF0]">
                    {centre.name.replace(/ TC-.+$/, '')}
                  </span>
                </Link>
              );
            })}
            {loading && <div className="absolute inset-x-8 bottom-7 h-2 overflow-hidden rounded-full bg-[#EEF1F4]"><div className="h-full w-1/3 animate-pulse rounded-full bg-[#CBD5E1]" /></div>}
          </div>
        ) : (
          <div className="divide-y divide-[#EEF1F4] px-6">
            {ordered.map(centre => {
              const seed = simulatedFacts(centre.centre_id);
              return <Link href={`/centres/${centre.centre_id}`} key={centre.centre_id} className="kw-focus grid min-h-20 grid-cols-[1fr_auto] items-center gap-4 py-4 hover:bg-[#FBFCFD]">
                <div className="min-w-0"><div className="flex items-center gap-2"><span className="font-medium text-[#172033]">{centre.name}</span><span className="rounded-full bg-[#F2F4F7] px-2 py-0.5 text-[11px] text-[#667085]">Simulated</span></div><div className="mt-1 text-[13px] text-[#667085]">{centre.district} · {centreReason(centre)}</div></div>
                <div className="flex items-center gap-6"><div className="hidden text-right text-xs text-[#667085] md:block"><div>{seed.reportedLabel}</div><b className="font-medium text-[#344054]">{seed.reportedValue} reported · {seed.observedValue} observed</b></div><StatusPill state={centreUiState(centre)} /></div>
              </Link>;
            })}
          </div>
        )}
      </section>

      <div className="mt-12 grid gap-12 lg:grid-cols-[1fr_320px]">
        <section>
          <div className="mb-5 flex items-center justify-between"><h2 className="text-xl font-medium text-[#172033]">Needs attention</h2>{error && <Button variant="ghost" size="sm" onClick={() => void load()}><RotateCcw size={15} /> Retry live data</Button>}</div>
          <div className="space-y-2">
            {needsAttention.map(centre => (
              <Link href={`/centres/${centre.centre_id}`} key={centre.centre_id} className="kw-focus flex items-center gap-4 rounded-2xl bg-white px-5 py-4 shadow-[0_1px_2px_rgba(16,24,40,.04)] ring-1 ring-[#E6EAF0] transition-colors hover:bg-[#FBFCFD]">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#F8FAFC] text-[#667085]"><MapPin size={17} /></span>
                <div className="min-w-0 flex-1"><div className="truncate text-[15px] font-medium text-[#172033]">{centre.name}</div><div className="mt-0.5 truncate text-[13px] text-[#667085]">{centreReason(centre)}</div></div>
                <StatusPill state={centreUiState(centre)} />
              </Link>
            ))}
          </div>
          {error && <p className="mt-4 text-[13px] text-[#667085]">{error}</p>}
        </section>

        <aside className="pt-1 text-[14px] leading-7 text-[#667085]">
          <div className="font-medium text-[#344054]">Network summary</div>
          <p className="mt-2">{counts.verified} verified · {counts.review} need review · {counts.uncertain} uncertain · {counts.unavailable} unavailable</p>
          <p className="mt-3 text-xs text-[#98A2B3]">Camera trust suspends dependent conclusions when evidence is unreliable.</p>
        </aside>
      </div>
    </div>
  );
}
