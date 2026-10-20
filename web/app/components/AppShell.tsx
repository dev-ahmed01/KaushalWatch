'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BarChart3,
  Building2,
  MessageCircle,
  ClipboardList,
  Home,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldCheck,
  Sparkles,
  Clapperboard,
} from 'lucide-react';
import { MotionConfig } from 'framer-motion';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { cn } from '../lib/cn';
import { PeriodProvider, useBriefPeriod } from '../lib/period';
import AssistantDrawer from './AssistantDrawer';
import { NetworkStatus } from './NetworkStatus';
import SecureSessionGate from './SecureSessionGate';
import { SECURE_PROXY, logoutOfficer, getReviewAccess } from '../lib/api';
import { Button } from './ui/button';

const NAV = [
  { href: '/', label: 'Overview', icon: Home },
  { href: '/issues', label: 'Issues', icon: ClipboardList },
  { href: '/insights', label: 'Insights', icon: BarChart3 },
  { href: '/centre-desk', label: 'Centre Desk', icon: Building2 },
  { href: '/chatbox', label: 'Chatbox', icon: MessageCircle },
] as const;

function primarySection(pathname: string) {
  if (pathname.startsWith('/centre-desk') || pathname.startsWith('/centres')) return '/centre-desk';
  if (pathname.startsWith('/chatbox')) return '/chatbox';
  if (pathname.startsWith('/insights') || pathname.startsWith('/reports') || pathname.startsWith('/analytics')) return '/insights';
  if (pathname.startsWith('/issues') || pathname.startsWith('/actions') || pathname.startsWith('/cases') || pathname.startsWith('/escalations')) return '/issues';
  return '/';
}

export default function AppShell({ children }: { children: ReactNode }) {
  // The public showcase is a standalone, intentionally unprivileged experience.
  if (process.env.NEXT_PUBLIC_KAUSHALWATCH_PUBLIC_SHOWCASE === 'true') return <PeriodProvider>{children}</PeriodProvider>;
  return (
    <MotionConfig reducedMotion="user">
      <PeriodProvider>
        <SecureSessionGate>
          <AppShellContent>{children}</AppShellContent>
        </SecureSessionGate>
      </PeriodProvider>
    </MotionConfig>
  );
}

function AppShellContent({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantAllowed, setAssistantAllowed] = useState(!SECURE_PROXY);
  const [signOutError, setSignOutError] = useState('');
  const [todayIst, setTodayIst] = useState('Today · IST');
  const isLogin = pathname === '/login';

  useEffect(() => {
    setTodayIst('Today, ' + new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' }).format(new Date()));
  }, []);
  const { period, setPeriod } = useBriefPeriod();
  const active = pathname.startsWith('/demo/') ? '' : primarySection(pathname);
  const activeLabel = pathname === '/demo/studio' ? 'Recorded demo studio'
    : pathname === '/demo/mission' ? 'Proof of Training'
    : NAV.find(item => item.href === active)?.label || 'Overview';
  // The global range control previously caused redundant controls and
  // network refreshes across unrelated modules. Insights owns the period.
  const showDateRange = false; // Range is owned by the one selector in Insights.
  const centreId = useMemo(
    () => pathname.match(/^\/centres\/([^/]+)/)?.[1] || 'DEMO-KA-104',
    [pathname],
  );

  useEffect(() => {
    // The login page is public: polling officer context before authentication
    // would trigger the API client's 401 redirect back to /login indefinitely.
    if (!SECURE_PROXY || isLogin) return;
    let active = true;
    getReviewAccess()
      .then(policy => {
        if (active) setAssistantAllowed(policy.can_use_network_assistant === true);
      })
      .catch(() => { if (active) setAssistantAllowed(false); });
    return () => { active = false; };
  }, [isLogin]);

  useEffect(() => {
    const open = () => { if (assistantAllowed) setAssistantOpen(true); };
    window.addEventListener('kaushalwatch:assistant', open);
    if (!assistantAllowed) setAssistantOpen(false);
    return () => window.removeEventListener('kaushalwatch:assistant', open);
  }, [assistantAllowed]);

  if (SECURE_PROXY && isLogin) return <>{children}</>;

  return (
    <div className="min-h-screen bg-[var(--kw-page)]">
      <a href="#main-content" className="kw-skip-link">Skip to content</a>
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-[#E7EDF5] bg-[#FCFDFF] transition-[width] duration-200 md:flex',
          collapsed ? 'w-[72px]' : 'w-[252px]',
        )}
      >
        <div className={cn('flex h-[78px] items-center border-b border-[#EEF2F6]', collapsed ? 'justify-center px-3' : 'justify-between px-4')}>
          <Link href="/" className="kw-focus flex min-w-0 items-center gap-2.5 rounded-xl">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#E9F1FF] text-[#1E4EA3]">
              <ShieldCheck size={19} />
            </span>
            {!collapsed && <span className="min-w-0"><strong className="kw-brand-title block truncate text-[18px] font-bold leading-[1.2] text-[#142841]">KaushalWatch</strong><small className="mt-1 block text-[9px] font-semibold uppercase tracking-[.17em] text-[#8A9BB1]">TRAINING CENTRE OPERATIONS</small></span>}
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
                  'kw-focus kw-os-navlink flex h-11 items-center rounded-xl text-[13px] font-medium transition-colors',
                  collapsed ? 'justify-center' : 'gap-3 px-3',
                  selected
                    ? 'bg-[#ECF3FF] text-[#1B56B7]'
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
              <div className="flex items-center gap-2 text-[11px] font-medium text-[#50627B]"><span className="h-2 w-2 rounded-full bg-[#0B996A]"/> Officer workspace</div>
              <div className="mt-1 text-[10px] text-[#98A2B3]">Human-reviewed decisions</div>
              {!SECURE_PROXY && <Link href="/demo/studio" className="kw-focus mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[#ECF4FF] px-2.5 py-2 text-[11px] font-semibold text-[#2360AF]"><Clapperboard size={14}/> Recorded demo</Link>}
            </div>
          )}
        </div>
      </aside>

      <div className={cn('kw-os-page min-h-screen transition-[padding] duration-200', collapsed ? 'md:pl-[72px]' : 'md:pl-[252px]')}>
        <header className="sticky top-0 z-20 flex min-h-[62px] items-center justify-between gap-2 border-b border-[#E5EAF2] bg-white/95 px-3 py-2 backdrop-blur-xl sm:px-4 md:min-h-[74px] md:px-7">
          <div className="min-w-0">
            <div className="hidden text-[10px] font-semibold uppercase tracking-[.14em] text-[#95A2B6] sm:block">KaushalWatch OS</div>
            <div className="kw-brand-title truncate text-[16px] font-semibold text-[#253F61] sm:mt-0.5">{activeLabel}</div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <span aria-label="Current date in India Standard Time" className="hidden whitespace-nowrap rounded-lg border border-[#E5EAF2] bg-white px-3 py-2 text-[11px] font-medium text-[#667085] lg:inline-flex">{todayIst}</span>
            {showDateRange && <label className="md:hidden">
              <span className="sr-only">Date range</span>
              <select
                aria-label="Date range"
                value={period}
                onChange={event => setPeriod(event.target.value as 'yesterday' | 'last_7_days' | 'last_30_days')}
                className="kw-focus h-9 rounded-lg border border-[#DCE3EC] bg-white px-2 text-[12px] font-medium text-[#475467]"
              >
                <option value="yesterday">Yesterday</option>
                <option value="last_7_days">7 days</option>
                <option value="last_30_days">30 days</option>
              </select>
            </label>}
            {showDateRange && <div role="group" className="hidden rounded-xl border border-[#E4EAF2] bg-white p-1 md:flex" aria-label="Date range">
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
            </div>}
            {signOutError && <span role="alert" className="text-[11px] text-[#B42318]">{signOutError}</span>}
            {SECURE_PROXY && (
              <button type="button" aria-label="Sign out of officer session"
                onClick={() => {
                  setSignOutError('');
                  void logoutOfficer()
                    .then(() => window.location.replace('/login'))
                    .catch(() => setSignOutError('Unable to revoke this session. Try again.'));
                }}
                className="kw-focus rounded-lg border border-[#D0D5DD] bg-white px-3 py-2 text-[12px] font-medium text-[#344054]">
                Sign out
              </button>
            )}
            {assistantAllowed && (
              <Button variant="primary" onClick={() => setAssistantOpen(true)} aria-label="Ask KaushalAI">
                <Sparkles size={15} />
                <span className="hidden sm:inline">Ask KaushalAI</span>
              </Button>
            )}
          </div>
        </header>
        <NetworkStatus/>

        <main id="main-content" tabIndex={-1} className="focus:outline-none mx-auto w-full max-w-[1440px] px-3 py-5 pb-24 sm:px-5 md:px-7 md:py-7 md:pb-10">{children}</main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-[#E6EAF0] bg-white/96 px-2 pb-[max(env(safe-area-inset-bottom),8px)] pt-2 backdrop-blur md:hidden" aria-label="Mobile primary navigation">
        {NAV.map(item => {
          const Icon = item.icon;
          const selected = active === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={selected ? 'page' : undefined}
              className={cn(
                'kw-focus flex min-h-12 min-w-0 flex-col items-center justify-center gap-1 rounded-xl text-[9px] font-medium',
                selected ? 'bg-[var(--kw-accent-soft)] text-[var(--kw-accent-strong)]' : 'text-[#667085]',
              )}
            >
              <Icon size={17} strokeWidth={1.8} />
              <span className="max-w-full truncate px-0.5">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {assistantAllowed && <AssistantDrawer open={assistantOpen} onOpenChange={setAssistantOpen} centreId={centreId} />}
    </div>
  );
}
