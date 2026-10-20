'use client';

import Link from 'next/link';
import { ArrowRight, CalendarDays, ClipboardList, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { getKaushalBrief } from '../lib/api';
import type { KaushalBrief } from '../lib/types';

export default function CentreDeskPage() {
  const [brief, setBrief] = useState<KaushalBrief | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let mounted = true;
    getKaushalBrief().then(data => { if (mounted) setBrief(data); }).catch(() => {
      if (mounted) setError(true);
    });
    return () => { mounted = false; };
  }, []);
  const attention = (brief?.centres || []).filter(centre => centre.state !== 'verified');

  return <div className="space-y-5">
    <header><h1 className="text-[28px] font-semibold text-[var(--kw-text)]">Centre Desk</h1>
      <p className="text-[12px] text-[var(--kw-muted)]">Daily operations for centre handlers</p></header>
    {brief?.simulated && <p className="text-[11px] text-[#667085]">Simulated demo data · centre intelligence source</p>}
    <section className="grid gap-3 sm:grid-cols-3" aria-label="Centre Desk readiness">
      <div className="kw-surface p-5"><CalendarDays size={18} className="text-[#2563eb]"/><h2 className="mt-3 text-[13px] font-semibold">Today’s batches</h2>
        <p className="mt-2 text-[12px] text-[#667085]">Schedule not yet connected</p></div>
      <div className="kw-surface p-5"><Users size={18} className="text-[#2563eb]"/><h2 className="mt-3 text-[13px] font-semibold">Trainer coverage</h2>
        <p className="mt-2 text-[12px] text-[#667085]">Roster not yet connected</p></div>
      <div className="kw-surface p-5"><ClipboardList size={18} className="text-[#2563eb]"/><h2 className="mt-3 text-[13px] font-semibold">Action needed</h2>
        <p className="mt-2 text-[12px] text-[#667085]">{brief ? attention.length + ' centres need attention in the selected briefing' : error ? 'Unable to load authorised briefing' : 'Loading authorised briefing…'}</p></div>
    </section>
    <section className="kw-surface p-5"><h2 className="text-[15px] font-semibold">Centre attention</h2>
      <p className="mt-1 text-[11px] text-[#667085]">Evidence-based centre status, not batch attendance or named staff presence.</p>
      <div className="mt-3 divide-y divide-[#edf2f8]">
        {attention.map(centre => <Link key={centre.centre_id} href={centre.href} className="kw-focus flex items-center justify-between gap-2 py-3 text-[12px] hover:text-[#2563eb]">
          <span><strong className="block font-semibold">{centre.name}</strong><span className="text-[#667085]">{centre.reason}</span></span><ArrowRight size={15} className="shrink-0"/></Link>)}
      </div>
      {brief && !attention.length && <p className="mt-3 text-[12px] text-[#667085]">No attention-required centres in this period.</p>}
    </section>
  </div>;
}
