'use client';

import {
  Bot,
  Clock3,
  Info,
  Play,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import AnalysisModal from '../../../components/AnalysisModal';
import CentreTabs from '../../../components/CentreTabs';
import { StatusPill } from '../../../components/CalmUi';
import { Button } from '../../../components/ui/button';
import { getActivityIntelligence, getCentre } from '../../../lib/api';
import { useBriefPeriod } from '../../../lib/period';
import { FALLBACK_CENTRES } from '../../../lib/presentation';
import type { ActivityIntelligence, Centre } from '../../../lib/types';

export default function ActivityPage() {
  const { centreId } = useParams<{ centreId: string }>();
  const id = String(centreId);
  const { period } = useBriefPeriod();
  const [centre, setCentre] = useState<Centre | null>(null);
  const [activity, setActivity] = useState<ActivityIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysisOpen, setAnalysisOpen] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [current, intelligence] = await Promise.all([
        getCentre(id),
        getActivityIntelligence(id, period),
      ]);
      setCentre(current);
      setActivity(intelligence);
    } catch {
      setCentre(FALLBACK_CENTRES.find(item => item.centre_id === id) || FALLBACK_CENTRES[0]);
      setActivity(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [id, period]);

  const current = centre || FALLBACK_CENTRES.find(item => item.centre_id === id) || FALLBACK_CENTRES[0];
  const timeline = activity?.timeline || [];
  const maxScore = useMemo(
    () => Math.max(1, ...timeline.map(item => item.activity_percent)),
    [timeline],
  );
  const peakLabel = activity?.summary.peak?.label;
  const lowLabel = activity?.summary.lowest?.label;
  const uiState = activity?.state === 'available'
    ? 'verified'
    : activity?.state === 'uncertain'
      ? 'uncertain'
      : 'unavailable';

  return (
    <div>
      <header className="mb-6 flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-[32px] font-semibold tracking-[-0.04em] text-[var(--kw-text)]">Activity</h1>
          <p className="mt-1 text-[14px] text-[var(--kw-muted)]">When practical work was most and least active, using trusted scheduled evidence.</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <StatusPill state={uiState} label={activity?.state === 'available' ? 'ACTIVITY AVAILABLE' : undefined} />
            {activity?.simulated && <span className="rounded-full bg-[#F2F4F7] px-2 py-1 text-[10px] font-medium text-[#667085]">Simulated demo data</span>}
            <span className="text-[11px] text-[#98A2B3]">{activity?.period_label || 'Selected period'}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => window.dispatchEvent(new Event('kaushalwatch:assistant'))}>
            <Bot size={16} />
            Ask KaushalAI
          </Button>
          <Button variant="primary" onClick={() => setAnalysisOpen(true)}>
            <Play size={16} />
            Run analysis
          </Button>
        </div>
      </header>

      <CentreTabs centreId={id} />

      <div className="grid gap-7 lg:grid-cols-[1fr_320px]">
        <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-6 shadow-[var(--kw-shadow)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Daily activity pattern</h2>
              <p className="mt-1 text-[12px] text-[#98A2B3]">Trusted practical-analysis buckets only.</p>
            </div>
            <div className="text-right text-[11px] text-[#98A2B3]">
              {loading
                ? 'Refreshing…'
                : activity
                  ? activity.summary.trusted_bucket_count + ' trusted of ' + activity.summary.bucket_count + ' buckets'
                  : 'Activity service unavailable'}
            </div>
          </div>

          {timeline.length ? (
            <>
              <div className="mt-8 flex h-[250px] items-end gap-3 border-b border-[#E9EEF5] px-1 pb-0">
                {timeline.map(bucket => {
                  const relative = Math.max(6, (bucket.activity_percent / maxScore) * 100);
                  const isPeak = bucket.label === peakLabel;
                  const isLow = bucket.label === lowLabel;
                  return (
                    <div key={bucket.start_at} className="group flex min-w-0 flex-1 flex-col items-center justify-end self-stretch">
                      <div className="mb-2 min-h-8 text-center text-[10px] font-medium text-[#667085]">
                        {isPeak ? 'Peak' : isLow ? 'Lowest' : ''}
                      </div>
                      <div className="flex w-full flex-1 items-end justify-center">
                        <div
                          title={bucket.label + ' · ' + bucket.activity_percent + '% activity'}
                          className={
                            'w-full max-w-[54px] rounded-t-md transition-opacity group-hover:opacity-80 ' +
                            (!bucket.trusted
                              ? 'bg-[#D0D5DD]'
                              : isLow
                                ? 'bg-[#F4B866]'
                                : isPeak
                                  ? 'bg-[#2563EB]'
                                  : 'bg-[#AFC8EC]')
                          }
                          style={{ height: relative + '%' }}
                        />
                      </div>
                      <div className="mt-2 truncate text-center text-[10px] text-[#667085]">{bucket.label.split('–')[0]}</div>
                    </div>
                  );
                })}
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <ActivityFact
                  icon={TrendingUp}
                  label="Peak activity"
                  value={activity?.summary.peak?.label || 'Unavailable'}
                  note={activity?.summary.peak ? activity.summary.peak.activity_percent + '% activity proxy' : 'No trusted peak'}
                />
                <ActivityFact
                  icon={TrendingDown}
                  label="Lowest activity"
                  value={activity?.summary.lowest?.label || 'Unavailable'}
                  note={activity?.summary.lowest ? activity.summary.lowest.activity_percent + '% activity proxy' : 'No trusted low'}
                />
              </div>
            </>
          ) : (
            <div className="mt-7 flex min-h-[250px] items-center justify-center rounded-xl bg-[#F8FAFC] px-8 text-center">
              <div className="max-w-md">
                <Clock3 size={20} className="mx-auto text-[#98A2B3]" />
                <div className="mt-3 text-[14px] font-medium text-[#475467]">{activity?.explanation || 'No time-bucketed activity evidence is available for this period.'}</div>
                <p className="mt-1 text-[12px] leading-5 text-[#98A2B3]">Scheduled practical checks will build this pattern over time.</p>
              </div>
            </div>
          )}
        </section>

        <aside className="rounded-[18px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]">
          <div className="flex items-center gap-2 text-[13px] font-semibold text-[var(--kw-accent-strong)]">
            <Bot size={15} />
            KaushalAI insight
          </div>

          <div className="mt-5 space-y-5">
            <Insight
              number="1"
              title="Most active"
              body={
                activity?.summary.peak
                  ? activity.summary.peak.label + ' had the strongest trusted activity signal.'
                  : 'No trusted peak is available for this period.'
              }
            />
            <Insight
              number="2"
              title="Least active"
              body={
                activity?.summary.lowest
                  ? activity.summary.lowest.label + ' had the lowest trusted activity signal.'
                  : 'No trusted low period is available for this period.'
              }
            />
          </div>

          <div className="mt-6 rounded-xl bg-[#F8FAFC] p-4">
            <div className="text-[12px] font-semibold text-[var(--kw-text)]">{activity?.follow_up.title || 'Collect activity evidence first'}</div>
            <p className="mt-2 text-[11px] leading-5 text-[#667085]">{activity?.follow_up.reason || 'No grounded follow-up is available yet.'}</p>
            {activity?.follow_up.recommended ? (
              <button type="button" disabled className="mt-4 h-9 cursor-not-allowed rounded-lg border border-[#E4E7EC] bg-white px-3 text-[12px] font-medium text-[#98A2B3]">
                Contact details unavailable
              </button>
            ) : activity?.state === 'uncertain' ? (
              <a href={'/centres/' + id + '/evidence'} className="kw-focus mt-4 inline-flex h-9 items-center rounded-lg border border-[#D8E3F2] bg-white px-3 text-[12px] font-medium text-[var(--kw-accent-strong)]">
                Verify camera evidence
              </a>
            ) : null}
          </div>
        </aside>
      </div>

      <section className="mt-5 flex items-start gap-3 rounded-[16px] border border-[#E4EAF2] bg-[#FBFCFE] px-5 py-4">
        <Info size={16} className="mt-0.5 shrink-0 text-[#7C8AA5]" />
        <div>
          <div className="text-[12px] font-semibold text-[#475467]">Interpretation boundary</div>
          <p className="mt-1 text-[11px] leading-5 text-[#667085]">
            {activity?.interpretation_boundary || 'Activity is a visual proxy and never measures individual productivity or training quality.'}
          </p>
        </div>
      </section>

      <AnalysisModal
        open={analysisOpen}
        onOpenChange={setAnalysisOpen}
        centre={current}
        onComplete={updated => {
          setCentre(updated);
          void load();
        }}
      />
    </div>
  );
}

function ActivityFact({
  icon: Icon,
  label,
  value,
  note,
}: {
  icon: typeof TrendingUp;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="rounded-xl bg-[#F8FAFC] px-4 py-4">
      <div className="flex items-center gap-2 text-[11px] font-medium text-[#667085]"><Icon size={14} />{label}</div>
      <div className="mt-2 text-[16px] font-semibold text-[var(--kw-text)]">{value}</div>
      <div className="mt-1 text-[11px] text-[#98A2B3]">{note}</div>
    </div>
  );
}

function Insight({ number, title, body }: { number: string; title: string; body: string }) {
  return (
    <div className="flex gap-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#EFF6FF] text-[11px] font-semibold text-[var(--kw-accent-strong)]">{number}</span>
      <div>
        <div className="text-[12px] font-semibold text-[var(--kw-text)]">{title}</div>
        <p className="mt-1 text-[11px] leading-5 text-[#667085]">{body}</p>
      </div>
    </div>
  );
}
