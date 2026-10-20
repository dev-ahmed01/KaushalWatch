'use client';

import Link from 'next/link';
import { ArrowRight, BarChart3, Download, ShieldCheck, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { DataRetry } from '../components/NetworkStatus';
import TrustScorecardPanel from '../components/TrustScorecardPanel';
import EvidenceCopilot from '../components/EvidenceCopilot';
import { EmptyState, PageHeader, StatTile, StatusBadge } from '../components/WorkspaceUi';
import { getNetworkInsights, reportPdfUrl } from '../lib/api';
import type { NetworkInsights } from '../lib/types';

type Range = 'today' | 'last_7_days' | 'last_30_days';
const RANGES: Array<{value: Range; label: string}> = [
  { value: 'today', label: 'Today' },
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'last_30_days', label: 'Last 1 month' },
];

export default function InsightsPage() {
  const [range, setRange] = useState<Range>('last_7_days');
  const [data, setData] = useState<NetworkInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [reportId, setReportId] = useState('');
  const [showTrust, setShowTrust] = useState(false);
  useEffect(() => {
    setReportId(new URLSearchParams(window.location.search).get('centre') || '');
  }, []);
  useEffect(() => {
    let live = true;
    setLoading(true);
    setError('');
    getNetworkInsights(range).then(payload => {
      if (live) setData(payload);
    }).catch(() => {
      if (live) {
        setData(null);
        setError('Insights are unavailable for the selected period.');
      }
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [range, retry]);

  const attendanceMax = Math.max(1, ...(data?.attendance || []).flatMap(item => [item.reported || 0, item.observed || 0]));
  const equipmentMax = Math.max(1, ...(data?.infrastructure || []).map(item => Math.max(item.missing_units, item.case_count)));
  const selected = data?.report_centres.find(item => item.centre_id === reportId) || data?.report_centres[0];
  const attendance = data?.attendance.find(item => item.centre_id === selected?.centre_id);
  const infrastructure = data?.infrastructure.find(item => item.centre_id === selected?.centre_id);
  const pdfPeriod = range === 'last_7_days' ? '7d' : range === 'last_30_days' ? '30d' : 'today';

  return <div className="space-y-4">
    <PageHeader title="Insights" description={data ? data.period_label + ' · Verified source data and recorded comparisons' : 'Recorded centre patterns'}
      action={<div className="flex items-center gap-2">
        {data?.simulated && <StatusBadge label="Simulated demo data"/>}
        <label htmlFor="insights-period" className="sr-only">Date range</label>
        <select id="insights-period" aria-label="Date range" value={range} onChange={e => setRange(e.target.value as Range)}
          className="kw-focus h-10 min-w-[135px] rounded-xl border border-[#dce5f1] bg-white px-3 text-[12px] font-semibold text-[#425570]">
          {RANGES.map(item => <option value={item.value} key={item.value}>{item.label}</option>)}
        </select>
      </div>}/>
    {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#ead9bc] bg-[#fffbf4] p-3 text-[12px] text-[#885a24]">
      {error}<DataRetry onRetry={() => setRetry(n => n+1)} disabled={loading}/></div>}
    {loading && !data && <div role="status" className="grid gap-3 sm:grid-cols-4">{Array.from({length:4},(_,i)=><div key={i} className="h-28 rounded-xl kw-skeleton"/>)}</div>}
    {data && <>
      <section aria-label="Network verification statistics" className="grid grid-cols-2 gap-2.5 xl:grid-cols-4">
        <StatTile label="Verified centres" value={data.counts.verified} tone="green" icon={<ShieldCheck size={18}/>}/>
        <StatTile label="Centres for review" value={data.counts.review} tone="amber" icon={<BarChart3 size={18}/>}/>
        <StatTile label="Camera uncertain" value={data.counts.uncertain} tone="red" icon={<ShieldCheck size={18}/>}/>
        <StatTile label="Analyses in period" value={data.counts.analysis_runs} tone="blue" icon={<BarChart3 size={18}/>}/>
      </section>
      <p className="text-[10px] text-[#8190a5]">Centre verification statuses are current recorded states; analysis totals and activity intervals use {data.period_label.toLowerCase()}. Missing data is not zero.</p>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="kw-os-card min-w-0 p-4 sm:p-5" aria-label="Attendance comparison chart">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-[15px] font-semibold">Reported vs observed attendance</h2>
            <div className="flex items-center gap-3 text-[10px] text-[#7e8ca0]">
              <span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-[#2563eb]"/>Reported</span>
              <span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-[#a9c5ec]"/>Observed</span>
            </div>
          </div>
          <p className="mt-1 text-[10px] text-[#8794a6]">Latest saved comparisons; not named attendance or shift completion</p>
          <div className="mt-4 space-y-3">
            {data.attendance.map(item => <div key={item.centre_id} className="grid min-w-0 grid-cols-[78px_minmax(0,1fr)_56px] items-center gap-3 sm:grid-cols-[94px_minmax(0,1fr)_62px]">
              <Link href={'/centres/'+encodeURIComponent(item.centre_id)} className="kw-focus truncate text-[11px] font-medium text-[#52657f] hover:text-[#2563eb]">{item.short_name}</Link>
              {item.available ? <div role="img" aria-label={item.short_name+': reported '+item.reported+', observed '+item.observed} className="space-y-1">
                <div className="h-2 overflow-hidden rounded-full bg-[#edf1f6]"><div className="h-full rounded-full bg-[#2563eb]" style={{width:((item.reported||0)/attendanceMax*100)+'%'}}/></div>
                <div className="h-2 overflow-hidden rounded-full bg-[#edf1f6]"><div className="h-full rounded-full bg-[#a9c5ec]" style={{width:((item.observed||0)/attendanceMax*100)+'%'}}/></div>
              </div> : <div className="rounded-lg bg-[#f3f5f8] px-3 py-2 text-[10px] text-[#8996a6]">Not measured</div>}
              <div className="text-right text-[11px] font-semibold text-[#50627b]">{item.available ? item.reported+' / '+item.observed : '—'}</div>
            </div>)}
            {!data.attendance.length && <EmptyState title="No attendance comparisons recorded"/>}
          </div>
        </section>
        <section className="kw-os-card min-w-0 p-4 sm:p-5" aria-label="Infrastructure exception chart">
          <h2 className="text-[15px] font-semibold">Infrastructure exceptions</h2>
          <p className="mt-1 text-[10px] text-[#8794a6]">Visible equipment gaps and saved exception cases; absence not proven</p>
          <div className="mt-4 space-y-4">
            {data.infrastructure.map(item => {
              const value=Math.max(item.missing_units,item.case_count);
              return <div key={item.centre_id} className="grid grid-cols-[78px_minmax(0,1fr)_34px] items-center gap-3 sm:grid-cols-[94px_minmax(0,1fr)_34px]">
                <Link href={'/centres/'+encodeURIComponent(item.centre_id)+'/infrastructure'} className="kw-focus truncate text-[11px] text-[#52657f] hover:text-[#2563eb]">{item.short_name}</Link>
                {item.status === 'uncertain' || item.status === 'unavailable' ?
                  <div className="rounded-lg bg-[#f3f5f8] px-3 py-1.5 text-[10px] text-[#8996a6]">{item.status}</div> :
                  <div className="h-3 overflow-hidden rounded-full bg-[#eef2f6]">
                    <div className={'h-full rounded-full '+(item.status==='review'?'bg-[#e9a64e]':'bg-[#a7d6bc]')}
                      style={{width:value?Math.max(6,value/equipmentMax*100)+'%':'0%'}}/></div>}
                <span className="text-right text-[11px] font-semibold text-[#52627b]">{item.status==='uncertain'||item.status==='unavailable'?'—':value}</span>
              </div>;
            })}
            {!data.infrastructure.length && <EmptyState title="No infrastructure evidence recorded"/>}
          </div>
        </section>
      </div>

      <section className="kw-os-card min-w-0 p-4 sm:p-5" aria-label="Source-backed insights">
        <div className="flex items-center gap-2 text-[14px] font-semibold"><Sparkles size={16} className="text-[#2563eb]"/> Evidence insights</div>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {data.insights.length ? data.insights.map(item=><Link key={item.kind} href={item.href}
            className="kw-focus min-w-0 rounded-xl border border-[#e6edf5] bg-[#fbfdff] p-3.5 hover:bg-[#f5f9ff]">
            <div className="flex justify-between gap-2"><h3 className="text-[12px] font-semibold">{item.title}</h3><ArrowRight size={14} className="shrink-0 text-[#7d8da2]"/></div>
            <p className="mt-1 line-clamp-3 text-[11px] leading-5 text-[#6c7b91]">{item.body}</p>
          </Link>) : <EmptyState title="No evidence insight in this period" detail="No trend is inferred without recorded observations."/>}
        </div>
        <p className="mt-3 text-[10px] text-[#8896a9]">Generated by the evidence rules engine; not a Gemini response.</p>
        {selected && <div className="mt-3"><EvidenceCopilot compact centreId={selected.centre_id} fallback={data.insights[0]?.body || 'No evidence-backed insight is available for this period.'}
          question={'Explain saved training-centre evidence for '+selected.name+' using the '+data.period_label+' window. Distinguish current state from records in the window and cite source IDs.'} sourceHref={'/centres/'+encodeURIComponent(selected.centre_id)}/></div>}
      </section>

      <details className="kw-os-card p-4 sm:p-5">
        <summary className="kw-focus cursor-pointer text-[13px] font-semibold">Activity across the training day</summary>
        <p className="mt-2 text-[10px] text-[#7f90a5]">Observed activity proxy, only in trusted intervals. Blank means no trusted interval.</p>
        <div role="region" aria-label="Activity heatmap, horizontally scrollable" tabIndex={0} className="kw-scrollbar mt-4 min-w-0 max-w-full overflow-x-auto overscroll-x-contain">
          <div className="grid min-w-[680px] grid-cols-[110px_repeat(7,minmax(0,1fr))] gap-2">
            <span/>{data.activity_heatmap.hours.map(hour=><span key={hour} className="text-center text-[10px] text-[#8795a7]">{hour}</span>)}
            {data.activity_heatmap.rows.flatMap(row=>[
              <Link key={row.centre_id+'-name'} href={'/centres/'+encodeURIComponent(row.centre_id)+'/practical'}
                className="kw-focus flex items-center truncate text-[11px] font-medium text-[#4c617e]">{row.short_name}</Link>,
              ...row.values.map((value,i)=><div key={row.centre_id+'-'+i} title={value===null?'No trusted reading':value+'% activity proxy'}
                className="flex h-9 items-center justify-center rounded-lg border border-[#e8eef5] text-[10px] font-semibold text-[#405675]"
                style={{backgroundColor:value===null?'#f3f5f8':`rgba(37,99,235,${0.09+Math.max(0,Math.min(100,value))/100*0.43})`}}>
                {value===null?'—':Math.round(value)}</div>)
            ])}
          </div>
        </div>
      </details>

      <section aria-label="Centre report workspace" className="kw-os-card p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-[15px] font-semibold">Centre verification reports</h2>
          <p className="mt-1 text-[10px] text-[#8090a4]">Saved evidence and officer outcomes · {data.period_label}</p></div>
          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor="centre-report-picker" className="sr-only">Report centre</label>
            <select id="centre-report-picker" aria-label="Report centre" className="kw-focus h-10 max-w-[190px] rounded-xl border border-[#dce6f2] bg-white px-3 text-[11px]"
              value={selected?.centre_id || ''} onChange={e=>setReportId(e.target.value)}>
              {data.report_centres.map(c=><option key={c.centre_id} value={c.centre_id}>{c.name}</option>)}
            </select>
            {selected&&<a href={reportPdfUrl(selected.centre_id,pdfPeriod)} target="_blank" rel="noreferrer"
              className="kw-focus inline-flex h-10 items-center gap-2 rounded-xl bg-[#2563eb] px-4 text-[11px] font-semibold text-white"><Download size={14}/> Download PDF</a>}
          </div>
        </div>
        {selected ? <div className="mt-3 grid grid-cols-2 gap-3 rounded-xl bg-[#f8fafd] p-4 sm:grid-cols-4">
          {[['Reported trainees',attendance?.available?attendance.reported??'—':'—'],
            ['Observed trainees',attendance?.available?attendance.observed??'—':'—'],
            ['Equipment gaps',infrastructure && !['uncertain','unavailable'].includes(infrastructure.status)?infrastructure.missing_units:'—'],
            ['Centre status',selected.state.replaceAll('_',' ')]].map(([name,value])=>
            <div key={String(name)} className="min-w-0"><p className="text-[10px] text-[#8494a6]">{name}</p>
              <strong className="kw-os-stat mt-1 block text-[17px] font-semibold capitalize text-[#344b68]">{value}</strong></div>)}
          <Link href={'/centres/'+encodeURIComponent(selected.centre_id)} className="kw-focus col-span-2 inline-flex items-center gap-1 text-[11px] font-semibold text-[#2563eb] sm:col-span-4">Open centre record <ArrowRight size={13}/></Link>
        </div> : <EmptyState title="No authorised centre reports"/>}
      </section>

      <details onToggle={e=>setShowTrust(e.currentTarget.open)} className="kw-os-card p-4">
        <summary className="kw-focus cursor-pointer text-[12px] font-semibold">Detailed trust and verification scorecard</summary>
        {showTrust && <TrustScorecardPanel/>}
      </details>
    </>}
  </div>;
}
