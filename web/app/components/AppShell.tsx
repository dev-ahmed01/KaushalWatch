'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BarChart3,
  Building2,
  CheckSquare2,
  Home,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { cn } from '../lib/cn';
import { PeriodProvider, useBriefPeriod } from '../lib/period';
import AssistantDrawer from './AssistantDrawer';
import { Button } from './ui/button';

const NAV = [
  { href: '/', label: 'KaushalAI', icon: Home },
  { href: '/centres', label: 'Centres', icon: Building2 },
  { href: '/insights', label: 'Insights', icon: BarChart3 },
  { href: '/actions', label: 'Actions', icon: CheckSquare2 },
] as const;

function primarySection(pathname: string) {
  if (pathname.startsWith('/centres')) return '/centres';
  if (pathname.startsWith('/insights') || pathname.startsWith('/reports') || pathname.startsWith('/analytics')) return '/insights';
  if (pathname.startsWith('/actions') || pathname.startsWith('/cases') || pathname.startsWith('/escalations')) return '/actions';
  return '/';
}

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <PeriodProvider>
      <AppShellContent>{children}</AppShellContent>
    </PeriodProvider>
  );
}

function AppShellContent({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const { period, setPeriod } = useBriefPeriod();
  const active = primarySection(pathname);
  const activeLabel = NAV.find(item => item.href === active)?.label || 'KaushalAI';
  const centreId = useMemo(
    () => pathname.match(/^\/centres\/([^/]+)/)?.[1] || 'DEMO-KA-104',
    [pathname],
  );

  useEffect(() => {
    const open = () => setAssistantOpen(true);
    window.addEventListener('kaushalwatch:assistant', open);
    return () => window.removeEventListener('kaushalwatch:assistant', open);
  }, []);

  return (
    <div className="min-h-screen bg-[var(--kw-page)]">
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 flex flex-col border-r border-[var(--kw-border)] bg-white transition-[width] duration-200',
          collapsed ? 'w-[72px]' : 'w-[208px]',
        )}
      >
        <div className={cn('flex h-[68px] items-center border-b border-[#EEF2F6]', collapsed ? 'justify-center px-3' : 'justify-between px-4')}>
          <Link href="/" className="kw-focus flex min-w-0 items-center gap-2.5 rounded-xl">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--kw-accent-soft)] text-[var(--kw-accent)]">
              <ShieldCheck size={19} />
            </span>
            {!collapsed && <span className="truncate text-[16px] font-semibold tracking-[-0.02em] text-[var(--kw-text)]">KaushalWatch</span>}
          </Link>
          {!collapsed && (
            <Button variant="ghost" size="icon" onClick={() => setCollapsed(true)} aria-label="Collapse navigation">
              <PanelLeftClose size={17} />
            </Button>
          )}
        </div>

        <nav className="flex-1 space-y-1 px-3 py-5" aria-label="Primary navigation">
          {NAV.map(item => {
            const Icon = item.icon;
            const selected = active === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={selected ? 'page' : undefined}
                title={collapsed ? item.label : undefined}
                className={cn(
                  'kw-focus flex h-11 items-center rounded-xl text-[14px] font-medium transition-colors',
                  collapsed ? 'justify-center' : 'gap-3 px-3',
                  selected
                    ? 'bg-[var(--kw-accent-soft)] text-[var(--kw-accent-strong)]'
                    : 'text-[#5D6B82] hover:bg-[#F7F9FC] hover:text-[#344054]',
                )}
              >
                <Icon size={18} strokeWidth={1.8} />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-[#EEF2F6] p-3">
          {collapsed ? (
            <Button variant="ghost" size="icon" onClick={() => setCollapsed(false)} aria-label="Expand navigation">
              <PanelLeftOpen size={18} />
            </Button>
          ) : (
            <div className="px-2 py-1.5">
              <div className="flex items-center gap-2 text-[11px] text-[#667085]">
                <span className="h-2 w-2 rounded-full bg-[#12B76A]" />
                <span>System ready</span>
              </div>
              <div className="mt-1 text-[11px] text-[#98A2B3]">AI surfaces evidence. Officers decide.</div>
            </div>
          )}
        </div>
      </aside>

      <div className={cn('min-h-screen transition-[padding] duration-200', collapsed ? 'pl-[72px]' : 'pl-[208px]')}>
        <header className="sticky top-0 z-20 flex h-[68px] items-center justify-between border-b border-[#EEF2F6] bg-[#F7F9FC]/95 px-8 backdrop-blur-sm">
          <div>
            <div className="text-[12px] text-[#98A2B3]">PMKVY Compliance Intelligence</div>
            <div className="mt-0.5 text-[13px] font-medium text-[#475467]">{activeLabel}</div>
          </div>

          <div className="flex items-center gap-2">
            <div className="hidden rounded-xl border border-[#E4EAF2] bg-white p-1 md:flex" aria-label="Date range">
              {[
                ['Yesterday', 'yesterday'],
                ['7 days', 'last_7_days'],
                ['30 days', 'last_30_days'],
              ].map(([label, value]) => {
                const selected = period === value;
                return (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setPeriod(value as 'yesterday' | 'last_7_days' | 'last_30_days')}
                    className={cn(
                      'kw-focus h-8 rounded-lg px-3 text-[12px] font-medium transition-colors',
                      selected
                        ? 'bg-[var(--kw-accent-soft)] text-[var(--kw-accent-strong)]'
                        : 'text-[#667085] hover:bg-[#F8FAFC] hover:text-[#344054]',
                    )}
                  >
                    {label}
                  </button>
                );
              })}
              <button
                type="button"
                disabled
                title="Custom date range will be added with the reporting phase"
                className="h-8 cursor-not-allowed rounded-lg px-3 text-[12px] font-medium text-[#B0B8C5]"
              >
                Custom
              </button>
            </div>
            <Button variant="primary" onClick={() => setAssistantOpen(true)}>
              <Sparkles size={15} />
              Ask KaushalAI
            </Button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1200px] px-8 py-9">{children}</main>
      </div>

      <AssistantDrawer open={assistantOpen} onOpenChange={setAssistantOpen} centreId={centreId} />
    </div>
  );
}
