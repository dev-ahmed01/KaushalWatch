'use client';

import Link from 'next/link';
import { Check, CircleAlert, CircleHelp, CircleX, Clock3, FileCheck2, ShieldCheck } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '../lib/cn';

export type UiState = 'verified' | 'review' | 'uncertain' | 'officer' | 'unavailable' | 'resolved';

const stateStyles: Record<UiState, string> = {
  verified: 'bg-[#ECFDF3] text-[#067647]',
  review: 'bg-[#FFFAEB] text-[#B54708]',
  uncertain: 'bg-[#F2F4F7] text-[#475467]',
  officer: 'bg-[#EFF6FF] text-[#1D4ED8]',
  unavailable: 'bg-[#F2F4F7] text-[#475467]',
  resolved: 'bg-[#ECFDF3] text-[#067647]',
};

const stateIcons: Record<UiState, ReactNode> = {
  verified: <Check size={13} strokeWidth={2} />,
  review: <CircleAlert size={13} strokeWidth={2} />,
  uncertain: <CircleHelp size={13} strokeWidth={2} />,
  officer: <Clock3 size={13} strokeWidth={2} />,
  unavailable: <CircleX size={13} strokeWidth={2} />,
  resolved: <ShieldCheck size={13} strokeWidth={2} />,
};

const defaultLabels: Record<UiState, string> = {
  verified: 'VERIFIED',
  review: 'NEEDS REVIEW',
  uncertain: 'UNCERTAIN',
  officer: 'OFFICER REVIEW',
  unavailable: 'ANALYSIS UNAVAILABLE',
  resolved: 'RESOLVED',
};

export function StatusPill({ state, label, className }: { state: UiState; label?: string; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium tracking-[0.02em]', stateStyles[state], className)}>
      {stateIcons[state]}
      {label || defaultLabels[state]}
    </span>
  );
}

export function PageTitle({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <header className="mb-12 flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
      <div className="max-w-2xl">
        <h1 className="text-[28px] font-medium leading-[1.25] tracking-[-0.02em] text-[#172033]">{title}</h1>
        {description && <p className="mt-2 text-[15px] leading-6 text-[#667085]">{description}</p>}
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </header>
  );
}

export function QuietFact({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[14px] font-medium text-[#667085]">{label}</div>
      <div className="mt-2 text-[28px] font-medium leading-none tracking-[-0.03em] text-[#172033]">{value}</div>
      {note && <div className="mt-2 text-[14px] text-[#667085]">{note}</div>}
    </div>
  );
}

export function EmptyState({ title, body, action, state = 'verified' }: { title: string; body: string; action?: ReactNode; state?: UiState }) {
  const tone = state === 'verified' || state === 'resolved' ? 'bg-[#ECFDF3] text-[#067647]' : state === 'review' ? 'bg-[#FFFAEB] text-[#B54708]' : 'bg-[#F2F4F7] text-[#475467]';
  const Icon = state === 'verified' || state === 'resolved' ? FileCheck2 : state === 'review' ? CircleAlert : CircleHelp;
  return (
    <div className="flex min-h-56 flex-col items-center justify-center rounded-2xl bg-white px-8 text-center shadow-[0_1px_2px_rgba(16,24,40,.04)] ring-1 ring-[#E6EAF0]">
      <div className={cn('flex h-10 w-10 items-center justify-center rounded-full', tone)}><Icon size={20} /></div>
      <h2 className="mt-5 text-xl font-medium text-[#172033]">{title}</h2>
      <p className="mt-2 max-w-md text-[15px] text-[#667085]">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function TechnicalDetails({ children }: { children: ReactNode }) {
  return (
    <details className="mt-6 border-t border-[#EEF1F4] pt-5 text-[14px] text-[#667085]">
      <summary className="kw-focus w-fit cursor-pointer list-none rounded-lg font-medium text-[#475467] hover:text-[#172033]">Technical details</summary>
      <div className="mt-4 space-y-2 leading-6">{children}</div>
    </details>
  );
}

export function PersistenceTimeline({ points, summary }: { points: { label: string; state: 'ok' | 'miss' | 'uncertain' }[]; summary: string }) {
  const tone = (state: string) => state === 'ok' ? 'bg-[#067647]' : state === 'miss' ? 'bg-[#B54708]' : 'bg-[#98A2B3]';
  const stateLabel = (state: string) => state === 'ok' ? 'Aligned' : state === 'miss' ? 'Discrepancy' : 'Uncertain';
  return (
    <div className="rounded-2xl bg-[#FBFCFD] p-6">
      <div className="text-[14px] font-medium text-[#475467]">Temporal Proof</div>
      <div className="mt-5 flex items-start">
        {points.map((point, index) => (
          <div className="flex flex-1 items-start" key={`${point.label}-${index}`}>
            <div className="flex min-w-0 flex-1 flex-col items-center text-center">
              <span aria-hidden="true" className={cn('h-3 w-3 rounded-full ring-4 ring-white', tone(point.state))} />
              <span className="mt-2 text-xs text-[#667085]">{point.label}</span>
              <span className="mt-0.5 text-[10px] font-medium text-[#667085]">{stateLabel(point.state)}</span>
            </div>
            {index < points.length - 1 && <span className="mt-[5px] h-px flex-1 bg-[#D7DCE3]" />}
          </div>
        ))}
      </div>
      <p className="mt-5 text-[15px] font-medium text-[#172033]">{summary}</p>
      <p className="mt-1 text-[13px] text-[#667085]">A single frame never creates a case.</p>
    </div>
  );
}

export function EvidenceFrame({ src, timestamp, trusted, anonymized = true, alt = 'Retained compliance evidence', emptyText = 'Evidence preview appears after analysis' }: { src?: string; timestamp?: string; trusted?: boolean; anonymized?: boolean; alt?: string; emptyText?: string }) {
  return (
    <div className="overflow-hidden rounded-2xl bg-[#111827] text-white shadow-[0_1px_2px_rgba(16,24,40,.06)]">
      <div className="relative aspect-video min-h-0 bg-[#111827] sm:min-h-64">
        {src ? <img src={src} alt={alt} className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center px-6 text-center text-sm text-[#D0D5DD]">{emptyText}</div>}
        <div className="absolute inset-x-0 bottom-0 flex flex-wrap items-center justify-between gap-2 bg-black/45 px-4 py-3 text-xs">
          <span>{timestamp || 'Latest retained frame'}</span>
          <span>{trusted === false ? 'Camera untrusted' : 'Camera trusted'}</span>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-xs text-[#D0D5DD]">
        <span>{anonymized ? 'Position tracked. Identity not collected.' : 'Evidence retained for review.'}</span>
        <span>No face recognition</span>
      </div>
    </div>
  );
}

export function InlineLink({ href, children }: { href: string; children: ReactNode }) {
  return <Link href={href} className="kw-focus rounded-md text-[14px] font-medium text-[#2563EB] hover:text-[#1D4ED8]">{children}</Link>;
}
