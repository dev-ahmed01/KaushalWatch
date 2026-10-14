'use client';

import Link from 'next/link';
import {
  ArrowRight,
  Bot,
  Camera,
  Clock3,
  FileSearch,
  HardHat,
  ListChecks,
  Sparkles,
  TrendingDown,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { buttonVariants } from '../components/ui/button';
import { getActionQueue } from '../lib/api';
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

  useEffect(() => {
    let active = true;
    setLoading(true);
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
  }, [period]);

  const grouped = useMemo(() => {
    const result: Record<ActionPriority, ActionQueueItem[]> = {
      high: [],
      medium: [],
      low: [],
    };
    for (const item of queue?.actions || []) result[item.priority].push(item);
    return result;
  }, [queue]);

  return (
    <div>
      <header className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-[12px] font-medium text-[var(--kw-accent-strong)]">
            <ListChecks size={14} />
            Officer work queue
          </div>
          <h1 className="mt-2 text-[34px] font-semibold tracking-[-0.04em] text-[var(--kw-text)]">Actions</h1>
          <p className="mt-1 text-[14px] text-[var(--kw-muted)]">Evidence-ranked next steps across the five monitored centres.</p>
        </div>

        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event('kaushalwatch:assistant'))}
          className="kw-focus inline-flex h-9 items-center gap-2 self-start rounded-lg border border-[#DCE3EC] bg-white px-3 text-[12px] font-medium text-[#475467] hover:border-[#BFCBDC] hover:text-[var(--kw-accent-strong)]"
        >
          <Bot size={15} />
          Ask KaushalAI
        </button>
      </header>

      {queue ? (
        <>
          <section className="relative overflow-hidden rounded-[18px] border border-[var(--kw-border)] bg-white px-7 py-7 shadow-[var(--kw-shadow)]">
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
              <p className="mt-2 max-w-2xl text-[13px] leading-6 text-[#667085]">{queue.summary}</p>

              {queue.top_action && (
                <div className="mt-6 flex flex-wrap items-center gap-3">
                  <Link href={queue.top_action.href} className={buttonVariants({ variant: 'primary' })}>
                    {queue.top_action.cta}
                    <ArrowRight size={14} />
                  </Link>
                  <span className="text-[11px] text-[#98A2B3]">
                    Ranked from {queue.top_action.evidence_basis.join(' · ')}
                  </span>
                </div>
              )}

              <div className="mt-5 border-t border-[#EEF2F6] pt-4 text-[11px] text-[#98A2B3]">
                {queue.scope_note}
              </div>
            </div>

            <div className="pointer-events-none absolute -right-10 -top-14 h-56 w-56 rounded-full bg-[#F1F6FD]" />
          </section>

          <div className="mt-7 grid gap-7 lg:grid-cols-[1fr_300px]">
            <section className="rounded-[18px] border border-[var(--kw-border)] bg-white px-6 py-5 shadow-[var(--kw-shadow)]">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Action queue</h2>
                  <p className="mt-1 text-[12px] text-[#98A2B3]">Current unresolved cases plus {label.toLowerCase()} activity follow-ups.</p>
                </div>
                <span className="text-[12px] font-medium text-[#667085]">{queue.counts.total} actions</span>
              </div>

              {queue.actions.length ? (
                <div className="mt-3 divide-y divide-[#EEF2F6]">
                  {queue.actions.map((item, index) => (
                    <ActionRow key={item.action_id} item={item} rank={index + 1} />
                  ))}
                </div>
              ) : (
                <div className="mt-5 rounded-xl bg-[#F8FAFC] px-5 py-8 text-center">
                  <div className="text-[13px] font-medium text-[#475467]">No officer action is queued.</div>
                  <p className="mt-1 text-[12px] text-[#98A2B3]">Latest trusted evidence does not require follow-up.</p>
                </div>
              )}
            </section>

            <aside className="space-y-4">
              <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]">
                <h2 className="text-[15px] font-semibold text-[var(--kw-text)]">Priority mix</h2>
                <div className="mt-4 space-y-3">
                  <PriorityBar label="High" value={queue.counts.high} total={queue.counts.total} tone="high" />
                  <PriorityBar label="Medium" value={queue.counts.medium} total={queue.counts.total} tone="medium" />
                  <PriorityBar label="Low" value={queue.counts.low} total={queue.counts.total} tone="low" />
                </div>
              </section>

              <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]">
                <h2 className="text-[15px] font-semibold text-[var(--kw-text)]">Queue state</h2>
                <div className="mt-4 space-y-3 text-[12px]">
                  <QueueFact label="Centres needing action" value={queue.counts.centres} />
                  <QueueFact label="Camera blockers" value={queue.counts.camera_blockers} />
                  <QueueFact label="Selected period" value={label} />
                </div>
              </section>

              {grouped.high.length > 0 && (
                <section className="rounded-[18px] border border-[#F4D7AF] bg-[#FFFBF5] p-5">
                  <div className="flex items-center gap-2 text-[12px] font-semibold text-[#B54708]">
                    <Clock3 size={14} />
                    Why these are first
                  </div>
                  <div className="mt-3 space-y-3">
                    {grouped.high.slice(0, 2).map(item => (
                      <div key={item.action_id}>
                        <div className="text-[12px] font-semibold text-[#475467]">{item.centre_name}</div>
                        <div className="mt-1 text-[11px] leading-5 text-[#667085]">{item.evidence_basis.join(' · ')}</div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </aside>
          </div>
        </>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[1fr_300px]">
          <div className="h-96 rounded-[18px] kw-skeleton" />
          <div className="h-64 rounded-[18px] kw-skeleton" />
          {!loading && (
            <div className="lg:col-span-2 rounded-xl border border-[#E4EAF2] bg-white px-5 py-4 text-[13px] text-[#667085]">
              The grounded action queue is temporarily unavailable.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ActionRow({ item, rank }: { item: ActionQueueItem; rank: number }) {
  const Icon = KIND_ICONS[item.kind] || ListChecks;
  return (
    <div className="grid gap-4 py-4 md:grid-cols-[36px_1fr_auto] md:items-center">
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
          {item.evidence_basis.slice(0, 4).map(basis => (
            <span key={basis} className="rounded-full bg-[#F8FAFC] px-2 py-1 text-[10px] text-[#667085]">{basis}</span>
          ))}
        </div>
      </div>

      <Link
        href={item.href}
        className={buttonVariants({
          variant: rank === 1 ? 'primary' : 'secondary',
          size: 'sm',
        })}
      >
        {item.cta}
        <ArrowRight size={13} />
      </Link>
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
        <span className="font-semibold text-[#475467]">{value}</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[#F2F4F7]">
        <div className={'h-full rounded-full ' + bar} style={{ width: width + '%' }} />
      </div>
    </div>
  );
}

function QueueFact({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[#667085]">{label}</span>
      <span className="font-semibold text-[#475467]">{value}</span>
    </div>
  );
}
