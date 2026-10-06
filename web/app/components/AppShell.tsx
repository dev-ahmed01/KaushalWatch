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
import AssistantDrawer from './AssistantDrawer';
import { Button } from './ui/button';

const NAV = [
  { href: '/', label: 'KaushalAI', icon: Home },
  { href: '/centres', label: 'Centres', icon: Building2 },
  { href: '/insights', label: 'Insights', icon: BarChart3 },
  { href: '/actions', label: 'Actions', icon: CheckSquare2 },
];

function primarySection(pathname: string) {
  if (pathname.startsWith('/centres')) return '/centres';
  if (pathname.startsWith('/insights') || pathname.startsWith('/reports') || pathname.startsWith('/analytics')) return '/insights';
  if (pathname.startsWith('/actions') || pathname.startsWith('/cases') || pathname.startsWith('/escalations')) return '/actions';
  return '/';
}

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const active = primarySection(pathname);
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
    <div className="min-h-screen bg-[#F7F9FC]">
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 flex flex-col border-r border-[#E7ECF3] bg-white transition-[width] duration-200',
          collapsed ? 'w-[76px]' : 'w-[216px]',
        )}
      >
        <div className={cn('flex h-[72px] items-center border-b border-[#EEF2F6]', collapsed ? 'justify-center px-3' : 'justify-between px-5')}>
          <Link href="/" className="kw-focus flex items-center gap-3 rounded-xl">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#EFF6FF] text-[#2563EB]">
              <ShieldCheck size={20} />
            </span>
            {!collapsed && <span className="text-[17px] font-medium tracking-[-0.02em] text-[#152238]">KaushalWatch</span>}
          </Link>
          {!collapsed && (
            <Button variant="ghost" size="icon" onClick={() => setCollapsed(true)} aria-label="Collapse navigation">
              <PanelLeftClose size={18} />
            </Button>
          )}
        </div>

        <nav className="flex-1 space-y-1 px-3 py-6" aria-label="Primary navigation">
          {NAV.map(item => {
            const Icon = item.icon;
            const selected = active === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={selected ? 'page' : undefined}
                className={cn(
                  'kw-focus flex h-11 items-center rounded-xl text-[15px] font-medium transition-colors',
                  collapsed ? 'justify-center' : 'gap-3 px-3',
                  selected
                    ? 'bg-[#EAF2FF] text-[#155EEF]'
                    : 'text-[#5D6B82] hover:bg-[#F8FAFC] hover:text-[#344054]',
                )}
              >
                <Icon size={19} strokeWidth={1.8} />
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
            <div className="px-2 py-2">
              <div className="flex items-center gap-2 text-[11px] text-[#667085]">
                <span className="h-2 w-2 rounded-full bg-[#12B76A]" />
                <span>System ready</span>
              </div>
              <div className="mt-1 text-[11px] text-[#98A2B3]">AI surfaces evidence. Officers decide.</div>
            </div>
          )}
        </div>
      </aside>

      <div className={cn('min-h-screen transition-[padding] duration-200', collapsed ? 'pl-[76px]' : 'pl-[216px]')}>
        <header className="sticky top-0 z-20 flex h-[72px] items-center justify-between border-b border-[#EEF2F6] bg-[#F7F9FC]/95 px-10 backdrop-blur-sm">
          <div className="text-[13px] font-medium text-[#667085]">PMKVY Compliance Intelligence</div>
          <div className="flex items-center gap-2">
            <div className="hidden rounded-xl border border-[#E4EAF2] bg-white p-1 md:flex" aria-label="Date range">
              {['Yesterday', '7 days', '30 days', 'Custom'].map((label, index) => (
                <button
                  key={label}
                  type="button"
                  className={cn(
                    'kw-focus h-8 rounded-lg px-3 text-[12px] font-medium',
                    index === 0 ? 'bg-[#EFF6FF] text-[#155EEF]' : 'text-[#667085] hover:text-[#344054]',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <Button variant="primary" onClick={() => setAssistantOpen(true)}>
              <Sparkles size={16} />
              Ask KaushalAI
            </Button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1240px] px-10 py-10">{children}</main>
      </div>

      <AssistantDrawer open={assistantOpen} onOpenChange={setAssistantOpen} centreId={centreId} />
    </div>
  );
}
