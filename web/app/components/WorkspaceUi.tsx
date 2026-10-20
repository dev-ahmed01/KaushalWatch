import type { ReactNode } from 'react';
import { cn } from '../lib/cn';

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
    <div className="min-w-0"><h1 className="text-[28px] font-semibold tracking-[-.04em] text-[var(--kw-text)]">{title}</h1>
      {description && <p className="mt-0.5 text-[12px] text-[var(--kw-muted)]">{description}</p>}</div>{action}
  </header>;
}

export function StatTile({ label, value, icon, tone = 'neutral' }: {
  label: string; value: string | number; icon?: ReactNode; tone?: 'neutral' | 'blue' | 'green' | 'amber' | 'red';
}) {
  const tones = { neutral: 'text-[#53657b]', blue: 'text-[#2563eb]', green: 'text-[#067647]', amber: 'text-[#b54708]', red: 'text-[#b42318]' };
  return <div className="kw-surface min-w-0 p-4 sm:p-5">
    {icon && <div className={cn('mb-3',tones[tone])}>{icon}</div>}
    <div className="kw-os-stat text-[27px] font-semibold leading-tight">{value}</div>
    <p className="mt-1 text-[11px] font-medium text-[#667085]">{label}</p>
  </div>;
}

export function StatusBadge({ label, tone = 'neutral' }: { label: string; tone?: 'neutral' | 'green' | 'amber' | 'red' | 'blue' }) {
  const tones = { neutral: 'bg-[#f2f4f7] text-[#475467]', green: 'bg-[#ecfdf3] text-[#067647]',
    amber: 'bg-[#fffaeb] text-[#b54708]', red: 'bg-[#fef3f2] text-[#b42318]', blue: 'bg-[#eff6ff] text-[#1d4ed8]' };
  return <span className={cn('inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold', tones[tone])}>{label}</span>;
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return <div className="rounded-xl border border-dashed border-[#d8e3f0] bg-[#fbfcfe] px-5 py-9 text-center">
    <p className="text-[13px] font-semibold">{title}</p>{detail && <p className="mt-1 text-[12px] text-[#667085]">{detail}</p>}
  </div>;
}

export function DetailWindow({ label, children }: { label: string; children: ReactNode }) {
  return <section aria-label={label} className="kw-scrollbar min-w-0 overflow-y-auto rounded-2xl border border-[#dbe6f3] bg-white shadow-[var(--kw-shadow)] lg:max-h-[calc(100vh-150px)]">{children}</section>;
}
