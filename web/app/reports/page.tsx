'use client';

import { CalendarDays, Download, History, LineChart } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { EmptyState, PageTitle, StatusPill } from '../components/CalmUi';
import { buttonVariants } from '../components/ui/button';
import { getCentres, reportPdfUrl, reportUrl } from '../lib/api';
import { cn } from '../lib/cn';
import { FALLBACK_CENTRES, centreUiState, effectivePillarValue, pillarState } from '../lib/presentation';
import type { Centre } from '../lib/types';

type Period = 'today' | '7d' | '30d' | 'custom';

export default function ReportsPage() {
  const [centres, setCentres] = useState<Centre[]>(FALLBACK_CENTRES);
  const [centreId, setCentreId] = useState('DEMO-KA-104');
  const [period, setPeriod] = useState<Period>('7d');
  const [tab, setTab] = useState<'history' | 'analytics'>('history');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('centre')) setCentreId(params.get('centre')!);
    if (params.get('tab') === 'analytics') setTab('analytics');
    getCentres().then(payload => setCentres(payload.centres.length ? payload.centres : FALLBACK_CENTRES)).catch(() => setCentres(FALLBACK_CENTRES));
  }, []);

  const rangeReady = period !== 'custom' || Boolean(startDate && endDate);
  useEffect(() => {
    if (!rangeReady) return;
    setError('');
    fetch(reportUrl(centreId, period, startDate || undefined, endDate || undefined), { cache: 'no-store' })
      .then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.detail || 'Report unavailable'); setReport(body); })
      .catch(err => { setReport(null); setError(err instanceof Error ? err.message : 'Report unavailable'); });
  }, [centreId, period, startDate, endDate, rangeReady]);

  const current = centres.find(item => item.centre_id === centreId) || FALLBACK_CENTRES[0];
  const pdf = reportPdfUrl(centreId, period, startDate || undefined, endDate || undefined);
  const analyses = report?.analyses || [];
  const patterns = useMemo(() => {
    const attention = analyses.filter((row: any) => row.outcome === 'attention').length;
    const blocked = analyses.filter((row: any) => row.outcome === 'blocked').length;
    const compliant = analyses.filter((row: any) => row.outcome === 'compliant').length;
    return [
      ['Verified analyses', compliant, 'Recorded checks without unresolved discrepancy'],
      ['Review analyses', attention, 'Evidence-backed discrepancy required review'],
      ['Unavailable analyses', blocked, 'Conclusion suspended or unavailable'],
    ] as const;
  }, [analyses]);

  return (
    <div>
      <PageTitle title="Reports" description="Auditable centre verification across a selected date range." action={<a href={rangeReady ? pdf : undefined} aria-disabled={!rangeReady} className={cn(buttonVariants({ variant: 'primary' }), !rangeReady && 'pointer-events-none opacity-45')}><Download size={17} /> Download PDF</a>} />

      <div className="mb-9 flex flex-col gap-5 border-b border-[#E6EAF0] pb-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex gap-1">
          <button type="button" onClick={() => setTab('history')} className={cn('kw-focus flex h-10 items-center gap-2 rounded-xl px-3 text-[14px] font-medium', tab === 'history' ? 'bg-[#EFF6FF] text-[#1D4ED8]' : 'text-[#667085]')}><History size={16} /> History</button>
          <button type="button" onClick={() => setTab('analytics')} className={cn('kw-focus flex h-10 items-center gap-2 rounded-xl px-3 text-[14px] font-medium', tab === 'analytics' ? 'bg-[#EFF6FF] text-[#1D4ED8]' : 'text-[#667085]')}><LineChart size={16} /> Analytics</button>
        </div>
        <select aria-label="Centre" value={centreId} onChange={event => setCentreId(event.target.value)} className="h-10 rounded-xl border border-[#D7DCE3] bg-white px-3 text-[13px] text-[#344054] outline-none focus:border-[#93B4F6]">{centres.map(centre => <option key={centre.centre_id} value={centre.centre_id}>{centre.name}</option>)}</select>
      </div>

      <div className="mb-10 flex flex-wrap items-center gap-2">
        <CalendarDays size={16} className="mr-1 text-[#667085]" />
        {([['today','Today'],['7d','7 days'],['30d','30 days'],['custom','Custom']] as const).map(([value,label]) => <button key={value} type="button" onClick={() => setPeriod(value)} className={cn('kw-focus h-9 rounded-full border px-3 text-[13px] font-medium', period === value ? 'border-[#93B4F6] bg-[#EFF6FF] text-[#1D4ED8]' : 'border-[#E6EAF0] bg-white text-[#667085]')}>{label}</button>)}
        {period === 'custom' && <><input aria-label="Start date" type="date" value={startDate} onChange={event => setStartDate(event.target.value)} className="h-9 rounded-lg border border-[#D7DCE3] bg-white px-2 text-[13px]" /><input aria-label="End date" type="date" value={endDate} onChange={event => setEndDate(event.target.value)} className="h-9 rounded-lg border border-[#D7DCE3] bg-white px-2 text-[13px]" /></>}
      </div>

      {tab === 'history' ? (
        <section className="kw-surface mx-auto max-w-4xl overflow-hidden">
          <div className="flex flex-col gap-4 border-b border-[#EEF1F4] px-8 py-7 md:flex-row md:items-start md:justify-between">
            <div><div className="flex items-center gap-2"><div className="text-[12px] font-medium tracking-[0.12em] text-[#667085]">KAUSHALWATCH</div>{report?.simulated && <span className="rounded-full bg-[#F2F4F7] px-2 py-0.5 text-[11px] text-[#667085]">Simulated</span>}</div><h2 className="mt-2 text-xl font-medium text-[#172033]">Centre Verification Report</h2><p className="mt-1 text-[14px] text-[#667085]">{current.name} · {report?.period_label || (period === '7d' ? 'Last 7 days' : period === '30d' ? 'Last 30 days' : period === 'today' ? 'Today' : 'Custom range')}</p></div>
            <StatusPill state={centreUiState(current)} label={current.pending_cases ? 'OFFICER REVIEW' : undefined} />
          </div>
          <div className="px-8 py-8">
            <div className="grid gap-6 md:grid-cols-3">
              <ReportFact label="Analysis runs" value={report ? String(analyses.length) : 'Not available'} reason={report ? 'Recorded in selected range' : 'Live report data not loaded'} />
              <ReportFact label="Open cases" value={String(report?.summary?.pending_cases ?? current.pending_cases ?? 0)} reason="Awaiting officer outcome" />
              <ReportFact label="Evidence integrity" value={String(effectivePillarValue(current, 'evidence')).replaceAll('_',' ').toUpperCase()} reason="SHA-256 + duplicate signal" />
            </div>
            <div className="mt-10 border-t border-[#EEF1F4] pt-8">
              <h3 className="text-[15px] font-medium text-[#172033]">Verification pillars</h3>
              <div className="mt-4 divide-y divide-[#EEF1F4]">
                {[
                  ['Attendance', effectivePillarValue(current, 'attendance')], ['Practical Activity', effectivePillarValue(current, 'practical')], ['Infrastructure', effectivePillarValue(current, 'infrastructure')], ['Camera Integrity', effectivePillarValue(current, 'camera')], ['Evidence Integrity', effectivePillarValue(current, 'evidence')],
                ].map(([label,value]) => <div key={label} className="flex items-center justify-between py-3.5"><span className="text-[14px] text-[#475467]">{label}</span><StatusPill state={pillarState(value, label === 'Camera Integrity' || label === 'Evidence Integrity' || !['attention','blocked'].includes(String(effectivePillarValue(current, 'camera'))))} /></div>)}
              </div>
            </div>
            {error && <div className="mt-8 rounded-2xl bg-[#F8FAFC] px-5 py-4 text-[13px] text-[#667085]">Live report history is unavailable. Showing the centre-state preview instead.</div>}
            <div className="mt-9 rounded-2xl bg-[#F8FAFC] p-5 text-[13px] leading-6 text-[#667085]"><b className="font-medium text-[#344054]">Audit note.</b> AI-generated evidence supports human review only. Missing or untrusted evidence never becomes a verified conclusion.</div>
          </div>
        </section>
      ) : (
        <section className="mx-auto max-w-4xl">
          <div className="mb-5"><h2 className="text-xl font-medium text-[#172033]">Recorded patterns</h2><p className="mt-1 text-[14px] text-[#667085]">Simple evidence counts, not performance scoring.</p></div>
          {analyses.length ? (
            <div className="kw-surface divide-y divide-[#EEF1F4] px-6">
              {patterns.map(([label,value,reason]) => <div key={label} className="grid gap-2 py-6 md:grid-cols-[1fr_80px_1.2fr] md:items-center"><span className="text-[14px] font-medium text-[#344054]">{label}</span><span className="text-[28px] font-medium leading-none text-[#172033]">{value}</span><span className="text-[13px] text-[#667085]">{reason}</span></div>)}
            </div>
          ) : (
            <EmptyState state="unavailable" title="No recorded analysis" body={error || 'No trusted analysis falls inside this date range.'} />
          )}
        </section>
      )}
    </div>
  );
}

function ReportFact({ label, value, reason }: { label: string; value: string; reason: string }) {
  return <div><div className="text-[13px] font-medium text-[#667085]">{label}</div><div className="mt-2 text-[24px] font-medium tracking-[-0.02em] text-[#172033]">{value}</div><div className="mt-1 text-[12px] text-[#98A2B3]">{reason}</div></div>;
}
