'use client';

import Link from 'next/link';
import {
  ArrowRight,
  Camera,
  Clock3,
  Search,
  Download,
  FileSearch,
  HardHat,
  ListChecks,
  Sparkles,
  TrendingDown,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { buttonVariants } from '../components/ui/button';
import { DataRetry } from '../components/NetworkStatus';
import { getActionQueue, reportPdfUrl } from '../lib/api';
import { useBriefPeriod } from '../lib/period';
import type { ActionPriority, ActionQueue, ActionQueueItem } from '../lib/types';

const KIND_ICONS: Record<string, typeof FileSearch> = {
  attendance: FileSearch,
  infrastructure: HardHat,
  camera: Camera,
  activity_follow_up: TrendingDown,
  practical: ListChecks,
  evidence: FileSearch,
  case: ListChecks,
};

export default function ActionsPage() {
  const { period, label } = useBriefPeriod();
  const [queue, setQueue] = useState<ActionQueue | null>(null);
  const [loading, setLoading] = useState(true);
  const [retryKey,setRetryKey] = useState(0);
  const [priorityFilter,setPriorityFilter] = useState<'all'|ActionPriority>('all');
  const [statusFilter,setStatusFilter] = useState<'all'|'open'|'under_review'|'virtual_verification'|'follow_up'>('all');
  const [search,setSearch] = useState('');
  const [selectedId,setSelectedId] = useState<string|null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setQueue(null);
    getActionQueue(period)
      .then(payload => {
        if (active) setQueue(payload);
      })
      .catch(() => {
        if (active) setQueue(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [period,retryKey]);

  const grouped = useMemo(() => {
    const result: Record<ActionPriority, ActionQueueItem[]> = {
      high: [],
      medium: [],
      low: [],
    };
    for (const item of queue?.actions || []) result[item.priority].push(item);
    return result;
  }, [queue]);

  const visibleActions=useMemo(()=> (queue?.actions||[]).filter(item=>{
    if(priorityFilter!=='all'&&item.priority!==priorityFilter)return false;
    if(statusFilter==='follow_up'&&item.source!=='activity')return false;
    if(statusFilter!=='all'&&statusFilter!=='follow_up'&&item.case_status!==statusFilter)return false;
    const q=search.trim().toLocaleLowerCase();
    return !q||[item.centre_name,item.title,item.reason,item.case_id||'',item.centre_id]
      .some(value=>value.toLocaleLowerCase().includes(q));
  }),[queue,priorityFilter,statusFilter,search]);
  const selected=visibleActions.find(item=>item.action_id===selectedId)||visibleActions[0]||null;

  return (
    <div>
      <header className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[12px] font-medium text-[var(--kw-accent-strong)]">
            <ListChecks size={14} />
            Officer work queue
          </div>
          <h1 className="mt-2 text-[34px] font-semibold tracking-[-0.04em] text-[var(--kw-text)]">Actions</h1>
          <p className="mt-1 text-[13px] text-[var(--kw-muted)]">Cases and follow-ups for officer review</p>
        </div>

      </header>

      {queue ? (
        <>
          <section className="kw-os-hero relative overflow-hidden rounded-[22px] border border-[var(--kw-border)] px-6 py-6 shadow-[var(--kw-shadow)]">
            <div className="relative z-10 max-w-[780px]">
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-2 text-[12px] font-medium text-[var(--kw-accent-strong)]">
                  <Sparkles size={14} />
                  KaushalAI priority
                </div>
                {queue.simulated && (
                  <span className="rounded-full bg-[#F2F4F7] px-2 py-0.5 text-[10px] font-medium text-[#667085]">Simulated demo data</span>
                )}
              </div>

              <h2 className="mt-3 text-[27px] font-semibold leading-[1.22] tracking-[-0.03em] text-[var(--kw-text)]">
                {queue.headline}
              </h2>
              <p className="mt-2 max-w-2xl text-[12px] leading-6 text-[#667085]">{queue.summary}</p>

              {queue.top_action && (
                <div className="mt-6 flex flex-wrap items-center gap-3">
                  <Link href={queue.top_action.href} className={buttonVariants({ variant: 'primary' })}>
                    {queue.top_action.cta}
                    <ArrowRight size={14} />
                  </Link>
                  <span className="text-[11px] text-[#8291A7]">{queue.top_action.centre_name}</span>
                </div>
              )}

              <div className="mt-5 border-t border-[#EEF2F6] pt-3 text-[11px] text-[#98A2B3]">{queue.scope_note}</div>
            </div>

            <div className="pointer-events-none absolute -right-10 -top-14 h-56 w-56 rounded-full bg-[#F1F6FD]" />
          </section>

          <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
            <section className="rounded-[18px] border border-[var(--kw-border)] bg-white px-6 py-5 shadow-[var(--kw-shadow)]">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Action queue</h2>
                  <p className="mt-1 text-[11px] text-[#98A2B3]">{queue.counts.total} actions · {label.toLowerCase()}</p>
                </div>
                <span className="text-[11px] text-[#667085]">{visibleActions.length} shown</span>
              </div>
              <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                <label className="relative min-w-0 flex-1 sm:min-w-[170px]">
                  <span className="sr-only">Search work queue</span>
                  <Search size={15} aria-hidden="true" className="pointer-events-none absolute left-3 top-3 text-[#97A5B8]"/>
                  <input value={search} onChange={event=>setSearch(event.target.value)}
                    placeholder="Search centre, case or task"
                    className="kw-focus h-10 w-full min-w-0 rounded-xl border border-[#DCE5F0] bg-white pl-9 pr-3 text-[12px] outline-none placeholder:text-[#9AA8BA]"/>
                </label>
                <select value={priorityFilter} onChange={event=>setPriorityFilter(event.target.value as typeof priorityFilter)}
                  aria-label="Priority filter" className="kw-focus h-10 rounded-xl border border-[#DCE5F0] bg-white px-3 text-[12px] text-[#475467]">
                  <option value="all">All priorities</option><option value="high">High</option>
                  <option value="medium">Medium</option><option value="low">Low</option>
                </select>
                <select value={statusFilter} onChange={event=>setStatusFilter(event.target.value as typeof statusFilter)}
                  aria-label="Case status filter" className="kw-focus h-10 rounded-xl border border-[#DCE5F0] bg-white px-3 text-[12px] text-[#475467]">
                  <option value="all">All stages</option><option value="open">Open</option>
                  <option value="under_review">Under review</option>
                  <option value="virtual_verification">Virtual verification</option>
                  <option value="follow_up">Activity follow-up</option>
                </select>
              </div>

              {visibleActions.length ? (
                <div className="mt-3 divide-y divide-[#EEF2F6]">
                  {visibleActions.map((item, index) => (
                    <ActionRow key={item.action_id} item={item} rank={index + 1} selected={selected?.action_id===item.action_id} onInspect={()=>setSelectedId(item.action_id)}/>
                  ))}
                </div>
              ) : (
                <div className="mt-5 rounded-xl bg-[#F8FAFC] px-5 py-8 text-center">
                  <div className="text-[13px] font-medium text-[#475467]">{queue.counts.total?'No matching work items.':'No actions are queued.'}</div>
                  <p className="mt-1 text-[12px] text-[#98A2B3]">{queue.counts.total?'Change the search or filters.':'No current officer follow-up was returned.'}</p>
                  {queue.counts.total>0&&<button type="button" className="kw-focus mt-3 text-[12px] font-semibold text-[#2563EB]" onClick={()=>{setSearch('');setPriorityFilter('all');setStatusFilter('all');}}>Clear filters</button>}
                </div>
              )}
            </section>

            <aside className="min-w-0 space-y-4">
              <section aria-label="Selected work item" className="sticky top-[92px] rounded-[20px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-[15px] font-semibold text-[#223955]">Case at a glance</h2>
                  {selected&&<PriorityPill priority={selected.priority}/>}
                </div>
                {selected ? <>
                  <div className="mt-5 text-[11px] font-semibold uppercase tracking-[.12em] text-[#98A5B6]">Centre record</div>
                  <Link href={'/centres/'+encodeURIComponent(selected.centre_id)}
                    className="kw-focus mt-1 inline-flex max-w-full items-center gap-2 text-[14px] font-semibold text-[#245B9F] hover:underline">
                    <span className="truncate">{selected.centre_name}</span><ArrowRight size={13}/>
                  </Link>
                  <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-[#F7FAFE] p-3">
                    <QueueFact label="Stage" value={(selected.case_status||'Follow-up').replaceAll('_',' ')}/>
                    <QueueFact label="Age" value={selected.source==='case'?selected.age_days+'d':'—'}/>
                    <QueueFact label="Source" value={selected.source==='case'?'Recorded case':'Activity analysis'}/>
                    <QueueFact label="Escalation" value={selected.escalation_level?selected.escalation_label:'Normal'}/>
                  </div>
                  <p className="mt-4 text-[12px] leading-5 text-[#61738B]">{selected.reason}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {selected.evidence_basis.map(basis=><span key={basis} className="rounded-full bg-[#F1F5FB] px-2.5 py-1 text-[10px] text-[#60738B]">{basis}</span>)}
                  </div>
                  {selected.simulated&&<span className="mt-3 inline-block text-[10px] font-medium text-[#8D9BAC]">Simulated records</span>}
                  <div className="mt-5 grid gap-2">
                    <Link href={selected.href} className={buttonVariants({variant:'primary',size:'sm'})}>
                      {selected.source==='case'?'Open case & audit':'Open activity details'}<ArrowRight size={14}/>
                    </Link>
                    <div className="grid grid-cols-2 gap-2">
                      <Link href={'/centres/'+encodeURIComponent(selected.centre_id)+'/evidence'}
                        className="kw-focus flex items-center justify-center rounded-xl border border-[#DDE6F1] px-2 py-2.5 text-[11px] font-semibold text-[#47617E] hover:bg-[#F7FAFE]">Evidence</Link>
                      <a href={reportPdfUrl(selected.centre_id,queue.period==='last_30_days'?'30d':queue.period==='last_7_days'?'7d':queue.period)}
                        target="_blank" rel="noreferrer"
                        className="kw-focus inline-flex items-center justify-center gap-1.5 rounded-xl border border-[#DDE6F1] px-2 py-2.5 text-[11px] font-semibold text-[#47617E] hover:bg-[#F7FAFE]"><Download size={13}/> Centre PDF</a>
                    </div>
                  </div>
                </>:<p className="mt-4 text-[12px] text-[#718198]">Select a work item to inspect its centre, evidence, and audit links.</p>}
              </section>
              <details className="rounded-[18px] border border-[#E6EAF0] bg-[#FCFDFE] p-4">
                <summary className="kw-focus cursor-pointer text-[12px] font-semibold text-[#475467]">Queue breakdown · {queue.counts.total}</summary>
                <div className="mt-4 space-y-3">
                  <PriorityBar label="High" value={queue.counts.high} total={queue.counts.total} tone="high" />
                  <PriorityBar label="Medium" value={queue.counts.medium} total={queue.counts.total} tone="medium" />
                  <PriorityBar label="Low" value={queue.counts.low} total={queue.counts.total} tone="low" />
                  <div className="border-t border-[#EEF2F6] pt-3 text-[11px] text-[#718198]">{queue.counts.centres} centres · {queue.counts.camera_blockers} camera blockers</div>
                </div>
              </details>
            </aside>
          </div>
        </>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[1fr_300px]">
          {loading&&<><div className="h-96 rounded-[18px] kw-skeleton" /><div className="h-64 rounded-[18px] kw-skeleton" /></>}
          {!loading && (
            <div className="lg:col-span-2 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E4EAF2] bg-white px-5 py-4 text-[13px] text-[#667085]">
              <span>The grounded action queue is temporarily unavailable.</span>
              <DataRetry onRetry={()=>setRetryKey(k=>k+1)} disabled={loading}/>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ActionRow({ item, rank, selected, onInspect }: { item: ActionQueueItem; rank: number; selected: boolean; onInspect: ()=>void }) {
  const Icon = KIND_ICONS[item.kind] || ListChecks;
  return (
    <div className={'grid gap-3 py-4 md:grid-cols-[32px_minmax(0,1fr)_auto] md:items-center '+(selected?'rounded-xl bg-[#F8FBFF]':'')}>
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#F5F8FD] text-[12px] font-semibold text-[#456A9B]">{rank}</span>

      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Icon size={15} className="text-[var(--kw-accent-strong)]" />
          <span className="text-[14px] font-semibold text-[var(--kw-text)]">{item.title}</span>
          <PriorityPill priority={item.priority} />
          {item.case_status && (
            <span className="text-[10px] font-medium uppercase tracking-[0.05em] text-[#98A2B3]">{item.case_status.replaceAll('_', ' ')}</span>
          )}
        </div>
        <div className="mt-1 text-[11px] text-[#98A2B3]">{item.centre_name}</div>
        <p className="mt-1.5 text-[12px] leading-5 text-[#667085]">{item.reason}</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {item.evidence_basis.filter(basis=>basis==='Regional escalation'||basis==='Blocks dependent visual conclusions')
            .map(basis=><span key={basis} className="rounded-full bg-[#F3F7FC] px-2 py-1 text-[10px] text-[#62748F]">{basis}</span>)}
        </div>
        <details className="mt-2 text-[11px] text-[#8291A7]">
          <summary className="kw-focus w-fit cursor-pointer">Evidence basis</summary>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {item.evidence_basis.slice(0,4).map(basis=><span key={basis} className="rounded-full bg-[#F5F8FC] px-2 py-1">{basis}</span>)}
          </div>
        </details>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={onInspect} aria-pressed={selected}
          aria-label={'Inspect '+item.centre_name+' '+item.title}
          className={'kw-focus rounded-xl border px-3 py-2 text-[11px] font-semibold '+(selected?'border-[#AFC8EC] bg-[#ECF4FF] text-[#225DA8]':'border-[#DCE5F0] bg-white text-[#6D819B] hover:bg-[#F7FAFE]')}>
          Inspect
        </button>
        <Link href={item.href} className={buttonVariants({variant:rank===1?'primary':'secondary',size:'sm'})}>
          {item.cta}<ArrowRight size={13}/>
        </Link>
      </div>
    </div>
  );
}

function PriorityPill({ priority }: { priority: ActionPriority }) {
  const tone = priority === 'high'
    ? 'bg-[#FEF3F2] text-[#B42318]'
    : priority === 'medium'
      ? 'bg-[#FFFAEB] text-[#B54708]'
      : 'bg-[#F2F4F7] text-[#667085]';
  return (
    <span className={'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.05em] ' + tone}>
      {priority}
    </span>
  );
}

function PriorityBar({
  label,
  value,
  total,
  tone,
}: {
  label: string;
  value: number;
  total: number;
  tone: ActionPriority;
}) {
  const width = total ? (value / total) * 100 : 0;
  const bar = tone === 'high'
    ? 'bg-[#D96C5F]'
    : tone === 'medium'
      ? 'bg-[#E9A64E]'
      : 'bg-[#AFC3DE]';
  return (
    <div>
      <div className="flex items-center justify-between text-[11px] text-[#667085]">
        <span>{label}</span>
        <span className="font-semibold text-[#475467]">{value} / {total}</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[#F2F4F7]">
        <div className={'h-full rounded-full ' + bar} style={{ width: width + '%' }} />
      </div>
    </div>
  );
}

function QueueFact({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="text-[10px] text-[#667085]">{label}</span>
      <span className="min-w-0 break-words text-[11px] font-semibold leading-4 text-[#475467]">{value}</span>
    </div>
  );
}
