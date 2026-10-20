'use client';

import Link from 'next/link';
import { AlertCircle, ArrowLeft, ArrowRight, Camera, ClipboardList, Clock3, Download, FileCheck2, HardHat, MessageCircle, Search, ShieldAlert, ShieldCheck, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { DataRetry } from '../components/NetworkStatus';
import { DetailWindow, EmptyState, PageHeader, StatusBadge } from '../components/WorkspaceUi';
import EvidenceCopilot from '../components/EvidenceCopilot';
import { getActionQueue, getCases, getEvidencePack, reportPdfUrl } from '../lib/api';
import { useBriefPeriod } from '../lib/period';
import type { ActionQueue, ActionQueueItem, CaseRecord, EvidenceReviewPack } from '../lib/types';

type Tab = 'overview' | 'evidence' | 'timeline' | 'communication';
type Priority = 'all' | 'high' | 'medium' | 'low';
const ICONS = { attendance: ClipboardList, infrastructure: HardHat, camera: Camera, evidence: FileCheck2, practical: ShieldCheck } as const;
const TABS: Tab[] = ['overview', 'evidence', 'timeline', 'communication'];
const category = (kind: string) => kind.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());
const formatIst = (time?: string | null) => time ? new Date(time).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' }) + ' IST' : 'Not recorded';

export default function IssuesPage() {
  const { period } = useBriefPeriod();
  const [queue, setQueue] = useState<ActionQueue | null>(null);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [search, setSearch] = useState('');
  const [priority, setPriority] = useState<Priority>('all');
  const [kind, setKind] = useState('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focused, setFocused] = useState(false);
  const [tab, setTab] = useState<Tab>('overview');
  const [packs, setPacks] = useState<Record<string, EvidenceReviewPack>>({});
  const [loadingEvidence, setLoadingEvidence] = useState(false);
  const [evidenceError, setEvidenceError] = useState('');

  useEffect(() => {
    const sync = () => {
      const issue = new URLSearchParams(window.location.search).get('issue');
      setSelectedId(issue);
      setFocused(Boolean(issue));
    };
    sync();
    window.addEventListener('popstate', sync);
    return () => window.removeEventListener('popstate', sync);
  }, []);
  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.allSettled([getActionQueue(period), getCases()]).then(([a, c]) => {
      if (!active) return;
      setQueue(a.status === 'fulfilled' ? a.value : null);
      setCases(c.status === 'fulfilled' ? c.value : []);
      setError(a.status === 'rejected' ? 'Issues could not be loaded from the authorised source.' : '');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [period, retry]);

  const kinds = useMemo(() => [...new Set((queue?.actions || []).map(item => item.kind))], [queue]);
  const filtered = useMemo(() => (queue?.actions || []).filter(item => {
    if (priority !== 'all' && item.priority !== priority) return false;
    if (kind !== 'all' && item.kind !== kind) return false;
    const term = search.trim().toLowerCase();
    return !term || [item.title, item.centre_name, item.centre_id, item.reason, item.case_id || ''].some(value => value.toLowerCase().includes(term));
  }), [queue, priority, kind, search]);
  const selected = selectedId
    ? (queue?.actions || []).find(item => item.action_id === selectedId || item.case_id === selectedId || item.centre_id === selectedId) || null
    : filtered[0] || null;
  const relatedCase = selected ? cases.find(item => item.case_id === selected.case_id) || null : null;
  const pack = relatedCase ? packs[relatedCase.case_id] : null;

  useEffect(() => {
    const caseId = relatedCase?.case_id;
    if (tab !== 'evidence' || !caseId || packs[caseId]) return;
    let active = true;
    setLoadingEvidence(true);
    setEvidenceError('');
    getEvidencePack(caseId).then(result => {
      if (active) setPacks(previous => ({ ...previous, [caseId]: result }));
    }).catch(() => { if (active) setEvidenceError('Evidence metadata is not available. Open the saved case for more details.'); })
      .finally(() => { if (active) setLoadingEvidence(false); });
    return () => { active = false; };
  }, [tab, relatedCase?.case_id, packs]);

  function select(item: ActionQueueItem) {
    setSelectedId(item.action_id);
    setFocused(true);
    setTab('overview');
    window.history.pushState({}, '', '/issues?issue=' + encodeURIComponent(item.action_id));
  }
  function close() {
    setSelectedId(null);
    setFocused(false);
    setTab('overview');
    window.history.pushState({}, '', '/issues');
  }

  return <div>
    <PageHeader title="Issues" description={queue ? queue.counts.total + ' recorded items for officer review' : 'Officer review queue'}
      action={queue?.simulated ? <StatusBadge label="Simulated demo data"/> : undefined}/>
    {error && <div role="alert" className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-[#eedac3] bg-[#fffbf6] p-3 text-[12px]">
      {error}<DataRetry onRetry={() => setRetry(n => n + 1)} disabled={loading}/></div>}
    <div className="grid min-w-0 items-start gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <section aria-label="Issue queue" className={'min-w-0 ' + (focused ? 'hidden md:block' : '')}>
        <div className="kw-surface p-3 sm:p-4">
          <div className="relative"><Search size={15} className="pointer-events-none absolute left-3 top-3.5 text-[#8a9bae]"/>
            <label htmlFor="issues-search" className="sr-only">Search issues, centres or keywords</label>
            <input id="issues-search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search issues or centres"
              className="kw-focus h-10 w-full min-w-0 rounded-xl border border-[#dce6f2] bg-white pl-9 pr-3 text-[12px] outline-none"/></div>
          <div className="mt-2 flex gap-2">
            <label className="sr-only" htmlFor="issues-kind">Issue category</label>
            <select id="issues-kind" value={kind} onChange={e => setKind(e.target.value)} className="kw-focus h-9 min-w-0 flex-1 rounded-lg border border-[#dce6f2] bg-white px-2 text-[11px]"><option value="all">All issues</option>
              {kinds.map(value => <option value={value} key={value}>{category(value)}</option>)}</select>
            <label className="sr-only" htmlFor="issues-priority">Issue priority</label>
            <select id="issues-priority" value={priority} onChange={e => setPriority(e.target.value as Priority)} className="kw-focus h-9 min-w-0 flex-1 rounded-lg border border-[#dce6f2] bg-white px-2 text-[11px]">
              <option value="all">All priorities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
          </div>
          <div className="mt-3 text-[11px] font-semibold text-[#68788f]">{filtered.length} issue{filtered.length === 1 ? '' : 's'}</div>
          <div className="kw-scrollbar mt-2 space-y-2 md:max-h-[calc(100vh-290px)] md:overflow-y-auto">
            {filtered.map(item => {
              const Icon = ICONS[item.kind as keyof typeof ICONS] || AlertCircle;
              const active = selected?.action_id === item.action_id;
              return <button key={item.action_id} onClick={() => select(item)} aria-pressed={active} type="button"
                className={'kw-focus w-full rounded-xl border p-3.5 text-left transition-colors ' + (active ? 'border-[#9dc3ff] bg-[#f0f6ff]' : 'border-[#e6edf6] bg-white hover:bg-[#f7faff]')}>
                <div className="flex items-center gap-2">
                  <span className="rounded-lg bg-[#eaf2ff] p-2 text-[#2563eb]"><Icon size={15}/></span>
                  <span className="min-w-0 flex-1"><span className="block truncate text-[12px] font-semibold">{item.title}</span>
                    <span className="block truncate text-[10px] text-[#73839c]">{item.centre_name}</span></span>
                  <StatusBadge tone={item.priority === 'high' ? 'red' : item.priority === 'medium' ? 'amber' : 'blue'} label={item.priority}/>
                  <ArrowRight size={14} className="shrink-0 text-[#8394aa]"/>
                </div>
                <p className="mt-2 line-clamp-2 text-[11px] leading-5 text-[#667085]">{item.reason}</p>
                <div className="mt-2 flex gap-3 text-[10px] text-[#7c8ea7]">
                  <span>{category(item.kind)}</span><span>{item.case_status?.replaceAll('_', ' ') || 'Follow-up'}</span>
                </div>
              </button>;
            })}
            {loading && <p role="status" className="p-5 text-[12px] text-[#667085]">Loading authorised issues…</p>}
            {!loading && !filtered.length && <EmptyState title="No matching issues" detail={queue ? 'Try another search or filter.' : 'The issue queue is not available.'}/>}
          </div>
        </div>
      </section>
      <div className={'min-w-0 ' + (!focused ? 'hidden md:block' : '')}>
        {selected ? <DetailWindow label="Selected issue details">
          <div className="sticky top-0 z-10 border-b border-[#e7edf5] bg-white px-4 py-4 sm:px-5">
            <div className="flex items-start gap-3">
              <button type="button" onClick={close} aria-label="Back to issue list" className="kw-focus mt-0.5 rounded-lg p-1 text-[#718198] hover:bg-[#f3f7fc] md:hidden"><ArrowLeft size={18}/></button>
              <div className="min-w-0 flex-1"><h2 className="text-[18px] font-semibold leading-6">{selected.title}</h2>
                <p className="mt-0.5 truncate text-[11px] text-[#7a8798]">{selected.centre_name} · {category(selected.kind)}</p></div>
              <StatusBadge tone={selected.priority === 'high' ? 'red' : selected.priority === 'medium' ? 'amber' : 'blue'} label={selected.priority}/>
              <button type="button" onClick={close} aria-label="Close issue detail" className="kw-focus hidden rounded-lg p-1 text-[#718198] hover:bg-[#f3f7fc] md:block"><X size={17}/></button>
            </div>
            <div role="tablist" aria-label="Issue detail sections" className="kw-os-subnav mt-4 flex gap-1 overflow-x-auto">
              {TABS.map(value => <button type="button" role="tab" aria-selected={tab === value} key={value} onClick={() => setTab(value)}
                className={'kw-focus shrink-0 border-b-2 px-3 py-2 text-[11px] font-semibold ' + (tab === value ? 'border-[#2563eb] text-[#2563eb]' : 'border-transparent text-[#708098] hover:text-[#344054]')}>{category(value)}</button>)}
            </div>
          </div>
          <div className="min-w-0 space-y-4 p-4 sm:p-5">
            {tab === 'overview' && <>
              <section className="rounded-xl bg-[#f1f6ff] p-4"><div className="flex items-center gap-2 text-[12px] font-semibold text-[#2454a6]"><ShieldAlert size={16}/> Operational summary</div>
                <p className="mt-2 text-[12px] leading-6 text-[#4a607d]">{selected.reason}</p>
                <p className="mt-2 text-[11px] font-medium text-[#526b8a]">Recommended officer action: {selected.cta}. Review the saved evidence before deciding.</p></section>
              <EvidenceCopilot centreId={selected.centre_id} fallback={selected.reason}
                question={'Explain the recorded ' + selected.kind + ' issue for ' + selected.centre_name + '. Distinguish uncertainty, evidence sources and what an officer should check. Do not make an automatic decision.'}
                sourceHref={selected.href} compact/>
              {selected.kind === 'attendance' && relatedCase && <section aria-label="Attendance comparison">
                <h3 className="text-[13px] font-semibold">Reported versus observed presence</h3>
                <div className="mt-2 grid grid-cols-3 gap-2">
                  {[[ 'Reported', relatedCase.reported_attendance ], ['Observed', relatedCase.camera_trust?.trusted === false ? null : relatedCase.visual_occupancy],
                    ['Difference', typeof relatedCase.reported_attendance === 'number' && typeof relatedCase.visual_occupancy === 'number' && relatedCase.camera_trust?.trusted !== false ? Math.abs(relatedCase.reported_attendance - relatedCase.visual_occupancy) : null]].map(([name,value]) =>
                    <div key={String(name)} className="rounded-xl border border-[#e8edf5] bg-[#fcfdff] p-3"><p className="text-[10px] text-[#76859c]">{name}</p>
                      <strong className="kw-os-stat mt-1 block text-[23px]">{typeof value === 'number' ? value : '—'}</strong></div>)}
                </div><p className="mt-2 text-[11px] leading-5 text-[#667085]">Aggregate observed presence is not proof of named absence, early departure, or shift completion. Individual completion not recorded.</p></section>}
              {relatedCase?.camera_trust?.trusted === false && <div className="rounded-xl border border-[#f7dda3] bg-[#fffaeb] p-3 text-[12px] text-[#965d0b]">
                Camera trust insufficient — dependent visual conclusions are UNKNOWN, not zero.</div>}
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-[#e7edf5] p-3"><h3 className="text-[11px] font-semibold">Case status</h3><p className="mt-1 text-[12px] text-[#667085]">{relatedCase?.status?.replaceAll('_',' ') || selected.case_status?.replaceAll('_',' ') || 'Follow-up'}</p></div>
                <div className="rounded-xl border border-[#e7edf5] p-3"><h3 className="text-[11px] font-semibold">Evidence basis</h3><p className="mt-1 text-[12px] text-[#667085]">{selected.evidence_basis.slice(0,3).join(' · ') || 'Not recorded'}</p></div>
              </div>
              {selected.kind === 'infrastructure' && <p className="text-[11px] leading-5 text-[#667085]">Equipment not visible is not equivalent to proven physical absence. Review the authorised trade manifest and source record.</p>}
              {selected.kind === 'practical' && <p className="text-[11px] leading-5 text-[#667085]">Activity estimates are visual proxies, not certification of equipment performance or trainer effectiveness.</p>}
              <ActionLinks item={selected} period={period}/>
            </>}
            {tab === 'evidence' && <section>
              <h3 className="text-[13px] font-semibold">Evidence and provenance</h3>
              <p className="mt-1 text-[11px] text-[#667085]">Metadata is retrieved only after opening this tab. Camera video and snapshots are not prefetched.</p>
              {!relatedCase && <EmptyState title="No saved case evidence for this follow-up" detail="Open the source centre record to inspect available analysis."/>}
              {loadingEvidence && <p role="status" className="mt-3 text-[11px]">Loading authorised evidence metadata…</p>}
              {evidenceError && <p role="alert" className="mt-3 text-[11px] text-[#b42318]">{evidenceError}</p>}
              {pack && <div className="mt-3 space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-xl bg-[#f5f8fc] p-3"><span className="block text-[10px]">Retained evidence</span><strong className="text-[20px]">{pack.integrity.retained_count}</strong></div>
                  <div className="rounded-xl bg-[#f5f8fc] p-3"><span className="block text-[10px]">Possible duplicates</span><strong className="text-[20px]">{pack.integrity.possible_duplicate_count}</strong></div>
                </div>
                <p className="text-[11px] text-[#667085]">Integrity: {pack.integrity.state}. Possible duplicate hashes are review signals, not proof of fraud.</p>
                {pack.integrity.items.slice(0,6).map(item => <div key={item.evidence_id} className="rounded-lg border border-[#e3eaf3] p-3 text-[10px]">
                  <p className="font-semibold">{item.evidence_id}</p><p className="mt-1 break-all text-[#667085]">SHA-256: {item.sha256 || 'Not recorded'}</p>
                  {item.possible_duplicate && <p className="mt-1 text-[#b54708]">Possible duplicate — needs review</p>}</div>)}
              </div>}
              <div className="mt-4"><ActionLinks item={selected} period={period}/></div>
            </section>}
            {tab === 'timeline' && <section>
              <h3 className="text-[13px] font-semibold">Recorded timeline</h3>
              <div className="mt-3 space-y-3">
                {relatedCase?.created_at && <TimelineLine label="Case created" date={relatedCase.created_at} detail={relatedCase.summary}/>}
                {(relatedCase?.review_history || []).map((event, index) => <TimelineLine key={index} label={event.from_status + ' → ' + event.to_status} date={event.timestamp} detail={event.note || 'Recorded review transition'}/>)}
                {!relatedCase?.created_at && !relatedCase?.review_history?.length && <EmptyState title="No timeline events recorded"/>}
              </div>
              <p className="mt-3 text-[11px] text-[#76859c]">Only recorded events are shown; no invented persistence intervals.</p></section>}
            {tab === 'communication' && <section>
              <div className="rounded-xl border border-[#dbe6f3] bg-[#f7faff] p-4">
                <div className="flex items-center gap-2"><MessageCircle size={17} className="text-[#2563eb]"/><h3 className="text-[13px] font-semibold">Contact the centre</h3></div>
                <p className="mt-2 text-[11px] leading-5 text-[#667085]">Open the dedicated Chatbox with this issue context. Only authorised participants will be selectable after the messaging service is enabled.</p>
                <Link href={'/chatbox?centre=' + encodeURIComponent(selected.centre_id) + '&issue=' + encodeURIComponent(selected.action_id)}
                  className="kw-focus mt-4 inline-flex items-center gap-1 rounded-lg bg-[#2563eb] px-3 py-2 text-[11px] font-semibold text-white">Open in Chatbox <ArrowRight size={13}/></Link>
              </div></section>}
          </div>
        </DetailWindow> : <DetailWindow label="Selected issue details"><div className="p-6">
          <EmptyState title={selectedId ? 'Issue not found' : 'Select an issue'} detail="Choose a recorded issue to inspect evidence and officer actions."/>
          <button type="button" onClick={close} className="kw-focus mt-3 text-[12px] font-semibold text-[#2563eb]">Back to issues</button>
        </div></DetailWindow>}
      </div>
    </div>
  </div>;
}

function TimelineLine({ label, date, detail }: { label: string; date: string; detail: string }) {
  return <div className="border-l-2 border-[#cfe0f8] pl-3"><p className="text-[11px] font-semibold">{label}</p>
    <p className="text-[10px] text-[#8090a5]">{formatIst(date)}</p><p className="mt-1 text-[11px] text-[#667085]">{detail}</p></div>;
}
function ActionLinks({ item, period }: { item: ActionQueueItem; period: string }) {
  return <div className="flex flex-wrap gap-2">
    <Link href={item.href} className="kw-focus inline-flex items-center gap-1.5 rounded-lg bg-[#2563eb] px-3 py-2 text-[11px] font-semibold text-white">
      {item.case_id ? 'Open saved case & audit' : 'Open source analysis'} <ArrowRight size={13}/></Link>
    <a href={reportPdfUrl(item.centre_id, period === 'last_30_days' ? '30d' : period === 'last_7_days' ? '7d' : period)} target="_blank" rel="noreferrer"
      className="kw-focus inline-flex items-center gap-1.5 rounded-lg border border-[#dce6f2] px-3 py-2 text-[11px] font-semibold text-[#4f6785]"><Download size={13}/> Centre PDF</a>
  </div>;
}
