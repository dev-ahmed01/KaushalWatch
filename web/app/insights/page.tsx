'use client';

import Link from 'next/link';
import {
  ArrowRight,
  BarChart3,
  Camera,
  Download,
  Sparkles,
} from 'lucide-react';
import type { CSSProperties } from 'react';
import { useEffect, useState } from 'react';
import { Button } from '../components/ui/button';
import { getNetworkInsights, reportPdfUrl } from '../lib/api';
import { useBriefPeriod } from '../lib/period';
import type { InsightState, NetworkInsights } from '../lib/types';

export default function InsightsPage() {
  const { period } = useBriefPeriod();
  const [data, setData] = useState<NetworkInsights | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getNetworkInsights(period)
      .then(payload => {
        if (active) setData(payload);
      })
      .catch(() => {
        if (active) setData(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [period]);

  if (!data) {
    return (
      <div>
        <Header periodLabel="Selected period" simulated={false} />
        <div className="grid gap-5 md:grid-cols-3">
          <div className="h-72 rounded-[18px] kw-skeleton" />
          <div className="h-72 rounded-[18px] kw-skeleton md:col-span-2" />
        </div>
        {!loading && (
          <div className="mt-5 rounded-xl border border-[#E4EAF2] bg-white px-5 py-4 text-[13px] text-[#667085]">
            Grounded insights are temporarily unavailable.
          </div>
        )}
      </div>
    );
  }

  const reportPeriod = data.period === 'last_7_days'
    ? '7d'
    : data.period === 'last_30_days'
      ? '30d'
      : data.period;
  const attendanceMax = Math.max(
    1,
    ...data.attendance.flatMap(item => [item.reported || 0, item.observed || 0]),
  );

  return (
    <div>
      <Header periodLabel={data.period_label} simulated={data.simulated} />

      <section className="grid gap-5 xl:grid-cols-[300px_1fr_300px]">
        <HealthRing data={data} />

        <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-6 shadow-[var(--kw-shadow)]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Reported vs observed attendance</h2>
              <p className="mt-1 text-[12px] text-[#98A2B3]">Trusted comparisons only.</p>
            </div>
            <div className="flex items-center gap-4 text-[10px] text-[#667085]">
              <Legend swatch="bg-[#2563EB]" label="Reported" />
              <Legend swatch="bg-[#AFC8EC]" label="Observed" />
            </div>
          </div>

          <div className="mt-7 grid h-[230px] grid-cols-5 items-end gap-4">
            {data.attendance.map(item => (
              <div key={item.centre_id} className="flex min-w-0 flex-col items-center">
                <div className="mb-2 h-5 text-[10px] font-medium text-[#667085]">
                  {item.available && item.difference ? 'Δ ' + item.difference : item.status === 'uncertain' ? 'UNCERTAIN' : ''}
                </div>
                <div className="flex h-[160px] items-end gap-1.5">
                  {item.available ? (
                    <>
                      <div
                        className="w-5 rounded-t-md bg-[#2563EB]"
                        style={{ height: Math.max(8, ((item.reported || 0) / attendanceMax) * 100) + '%' }}
                        title={'Reported ' + item.reported}
                      />
                      <div
                        className="w-5 rounded-t-md bg-[#AFC8EC]"
                        style={{ height: Math.max(8, ((item.observed || 0) / attendanceMax) * 100) + '%' }}
                        title={'Observed ' + item.observed}
                      />
                    </>
                  ) : (
                    <div className="flex h-full w-12 items-center justify-center rounded-lg border border-dashed border-[#D0D5DD] bg-[#F8FAFC] text-[10px] text-[#98A2B3]">—</div>
                  )}
                </div>
                <div className="mt-2 truncate text-center text-[10px] text-[#667085]">{item.short_name}</div>
              </div>
            ))}
          </div>
        </section>

        <aside className="rounded-[18px] border border-[var(--kw-border)] bg-white p-5 shadow-[var(--kw-shadow)]">
          <div className="flex items-center gap-2 text-[14px] font-semibold text-[var(--kw-accent-strong)]">
            <Sparkles size={15} />
            KaushalAI insights
          </div>
          <div className="mt-4 divide-y divide-[#EEF2F6]">
            {data.insights.length ? data.insights.map((item, index) => (
              <Link key={item.kind} href={item.href} className="kw-focus flex gap-3 rounded-md py-4">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#EFF6FF] text-[11px] font-semibold text-[var(--kw-accent-strong)]">{index + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-[12px] font-semibold text-[var(--kw-text)]">{item.title}</div>
                  <p className="mt-1 text-[11px] leading-5 text-[#667085]">{item.body}</p>
                </div>
                <ArrowRight size={13} className="mt-1 shrink-0 text-[#98A2B3]" />
              </Link>
            )) : (
              <div className="py-5 text-[12px] leading-5 text-[#667085]">No evidence-backed priority insight is available for this period.</div>
            )}
          </div>
        </aside>
      </section>

      <section className="mt-5 rounded-[18px] border border-[var(--kw-border)] bg-white p-6 shadow-[var(--kw-shadow)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Activity across the training day</h2>
            <p className="mt-1 text-[12px] text-[#98A2B3]">Trusted practical-activity signal · darker cells mean stronger visual activity.</p>
          </div>
          <div className="text-[11px] text-[#98A2B3]">{data.counts.analysis_runs} analyses in {data.period_label.toLowerCase()}</div>
        </div>

        <div className="mt-6 overflow-x-auto">
          <div className="min-w-[760px]">
            <div className="grid grid-cols-[120px_repeat(7,1fr)] gap-2">
              <div />
              {data.activity_heatmap.hours.map(hour => (
                <div key={hour} className="text-center text-[10px] text-[#98A2B3]">{hour}</div>
              ))}

              {data.activity_heatmap.rows.flatMap(row => [
                <div key={row.centre_id + '-name'} className="flex items-center text-[11px] font-medium text-[#475467]">{row.short_name}</div>,
                ...row.values.map((value, index) => (
                  <div
                    key={row.centre_id + '-' + index}
                    className="flex h-10 items-center justify-center rounded-lg border border-[#EEF2F6] text-[10px] font-medium"
                    style={heatStyle(value)}
                    title={value == null ? 'No trusted activity value' : value + '% activity proxy'}
                  >
                    {value == null ? '—' : Math.round(value)}
                  </div>
                )),
              ])}
            </div>
          </div>
        </div>
      </section>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <InfrastructureChart data={data} />
        <TrustAndOutcomes data={data} />
      </div>

      <section className="mt-5 rounded-[18px] border border-[var(--kw-border)] bg-white px-5 py-4 shadow-[var(--kw-shadow)]">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-[14px] font-semibold text-[var(--kw-text)]">Centre verification reports</div>
            <div className="mt-0.5 text-[11px] text-[#98A2B3]">Auditable PDF · same selected reporting window where supported.</div>
          </div>
          <div className="flex flex-wrap gap-2">
            {data.report_centres.map(centre => (
              <a
                key={centre.centre_id}
                href={reportPdfUrl(centre.centre_id, reportPeriod)}
                target="_blank"
                rel="noreferrer"
                className="kw-focus inline-flex h-9 items-center gap-2 rounded-lg border border-[#DCE3EC] bg-white px-3 text-[11px] font-medium text-[#475467] hover:border-[#BFCBDC] hover:text-[var(--kw-accent-strong)]"
              >
                <Download size={13} />
                {centre.name.split(' TC-')[0]}
              </a>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function Header({ periodLabel, simulated }: { periodLabel: string; simulated: boolean }) {
  return (
    <header className="mb-7 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <div className="flex items-center gap-2 text-[12px] font-medium text-[var(--kw-accent-strong)]">
          <BarChart3 size={14} />
          Visual intelligence
        </div>
        <h1 className="mt-2 text-[34px] font-semibold tracking-[-0.04em] text-[var(--kw-text)]">Insights</h1>
        <p className="mt-1 text-[14px] text-[var(--kw-muted)]">Performance and verification patterns across five centres.</p>
      </div>
      <div className="flex items-center gap-2">
        {simulated && <span className="rounded-full bg-[#F2F4F7] px-2.5 py-1 text-[10px] font-medium text-[#667085]">Simulated demo data</span>}
        <span className="text-[11px] text-[#98A2B3]">{periodLabel}</span>
        <Button variant="ghost" onClick={() => window.dispatchEvent(new Event('kaushalwatch:assistant'))}>
          <Sparkles size={15} />
          Ask KaushalAI
        </Button>
      </div>
    </header>
  );
}

function HealthRing({ data }: { data: NetworkInsights }) {
  const total = Math.max(1, data.counts.total);
  const verified = (data.counts.verified / total) * 100;
  const review = (data.counts.review / total) * 100;
  const uncertain = (data.counts.uncertain / total) * 100;
  const reviewEnd = verified + review;
  const uncertainEnd = reviewEnd + uncertain;
  const background = 'conic-gradient(#12B76A 0 ' + verified + '%, #F79009 ' + verified + '% ' + reviewEnd + '%, #8CA7CC ' + reviewEnd + '% ' + uncertainEnd + '%, #D0D5DD ' + uncertainEnd + '% 100%)';

  return (
    <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-6 shadow-[var(--kw-shadow)]">
      <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Centre health</h2>
      <div className="mt-5 flex justify-center">
        <div className="relative h-40 w-40 rounded-full" style={{ background }}>
          <div className="absolute inset-7 flex flex-col items-center justify-center rounded-full bg-white">
            <span className="text-[30px] font-semibold tracking-[-0.04em] text-[var(--kw-text)]">{data.counts.total}</span>
            <span className="text-[11px] text-[#98A2B3]">centres</span>
          </div>
        </div>
      </div>
      <div className="mt-6 grid grid-cols-3 gap-2 text-center">
        <HealthCount value={data.counts.verified} label="Verified" />
        <HealthCount value={data.counts.review} label="Review" />
        <HealthCount value={data.counts.uncertain} label="Uncertain" />
      </div>
    </section>
  );
}

function InfrastructureChart({ data }: { data: NetworkInsights }) {
  const max = Math.max(1, ...data.infrastructure.map(item => Math.max(item.missing_units, item.case_count)));
  return (
    <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-6 shadow-[var(--kw-shadow)]">
      <div>
        <h2 className="text-[17px] font-semibold text-[var(--kw-text)]">Infrastructure exceptions</h2>
        <p className="mt-1 text-[12px] text-[#98A2B3]">Current evidence-backed gaps by centre.</p>
      </div>
      <div className="mt-6 space-y-4">
        {data.infrastructure.map(item => {
          const magnitude = Math.max(item.missing_units, item.case_count);
          return (
            <div key={item.centre_id} className="grid grid-cols-[90px_1fr_42px] items-center gap-3">
              <span className="truncate text-[11px] text-[#667085]">{item.short_name}</span>
              <div className="h-2.5 overflow-hidden rounded-full bg-[#F2F4F7]">
                <div
                  className={item.status === 'review' ? 'h-full rounded-full bg-[#F4A340]' : item.status === 'uncertain' ? 'h-full rounded-full bg-[#9CB3D2]' : 'h-full rounded-full bg-[#B7DFC7]'}
                  style={{ width: magnitude ? Math.max(8, (magnitude / max) * 100) + '%' : '0%' }}
                />
              </div>
              <span className="text-right text-[11px] font-medium text-[#475467]">{item.missing_units || item.case_count || '—'}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function TrustAndOutcomes({ data }: { data: NetworkInsights }) {
  const outcomes = Object.entries(data.case_outcomes).filter(([, value]) => value > 0);
  const totalOutcomes = Math.max(1, outcomes.reduce((sum, [, value]) => sum + value, 0));
  return (
    <section className="rounded-[18px] border border-[var(--kw-border)] bg-white p-6 shadow-[var(--kw-shadow)]">
      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <div className="flex items-center gap-2 text-[14px] font-semibold text-[var(--kw-text)]"><Camera size={15} /> Camera trust</div>
          <div className="mt-5 flex gap-2">
            {data.camera_trust.map(item => (
              <div key={item.centre_id} className="min-w-0 flex-1 text-center">
                <div className={'mx-auto h-10 w-full rounded-lg ' + stateBlock(item.state)} title={item.name + ' · ' + item.state} />
                <div className="mt-1.5 truncate text-[9px] text-[#98A2B3]">{item.short_name}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="border-t border-[#EEF2F6] pt-5 sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0">
          <div className="text-[14px] font-semibold text-[var(--kw-text)]">Case outcomes</div>
          <div className="mt-5 flex h-4 overflow-hidden rounded-full bg-[#F2F4F7]">
            {outcomes.map(([status, value]) => (
              <div
                key={status}
                className={outcomeBlock(status)}
                style={{ width: (value / totalOutcomes) * 100 + '%' }}
                title={status.replaceAll('_', ' ') + ' · ' + value}
              />
            ))}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-x-3 gap-y-2">
            {outcomes.map(([status, value]) => (
              <div key={status} className="flex items-center justify-between gap-2 text-[10px]">
                <span className="truncate capitalize text-[#667085]">{status.replaceAll('_', ' ')}</span>
                <span className="font-semibold text-[#475467]">{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function HealthCount({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="text-[18px] font-semibold text-[var(--kw-text)]">{value}</div>
      <div className="text-[9px] text-[#98A2B3]">{label}</div>
    </div>
  );
}

function Legend({ swatch, label }: { swatch: string; label: string }) {
  return <span className="inline-flex items-center gap-1.5"><span className={'h-2 w-2 rounded-sm ' + swatch} />{label}</span>;
}

function heatStyle(value: number | null): CSSProperties {
  if (value == null) return { background: '#F8FAFC', color: '#98A2B3' };
  const alpha = 0.12 + (Math.min(100, Math.max(0, value)) / 100) * 0.7;
  return {
    backgroundColor: 'rgba(37, 99, 235, ' + alpha.toFixed(2) + ')',
    color: value >= 60 ? '#FFFFFF' : '#36516F',
  };
}

function stateBlock(state: InsightState) {
  if (state === 'verified') return 'bg-[#B7DFC7]';
  if (state === 'review') return 'bg-[#F4B866]';
  if (state === 'uncertain') return 'bg-[#AFC3DE]';
  return 'bg-[#E4E7EC]';
}

function outcomeBlock(status: string) {
  if (status === 'confirmed') return 'bg-[#D96C5F]';
  if (status === 'false_positive' || status === 'resolved') return 'bg-[#7DC49A]';
  if (status === 'virtual_verification') return 'bg-[#89A8D0]';
  if (status === 'under_review') return 'bg-[#F2B35D]';
  return 'bg-[#C8D2DF]';
}
