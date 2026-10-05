'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { FileText, FolderSearch2, Map, PanelLeftClose, PanelLeftOpen, ShieldCheck } from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { cn } from '../lib/cn';
import AssistantDrawer from './AssistantDrawer';
import { Button } from './ui/button';

const NAV = [
  { href: '/', label: 'Network', icon: Map },
  { href: '/cases', label: 'Cases', icon: FolderSearch2 },
  { href: '/reports', label: 'Reports', icon: FileText },
];

function primarySection(pathname: string) {
  if (pathname.startsWith('/cases')) return '/cases';
  if (pathname.startsWith('/reports')) return '/reports';
  return '/';
}

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const active = primarySection(pathname);
  const centreId = useMemo(() => pathname.match(/^\/centres\/([^/]+)/)?.[1] || 'DEMO-KA-104', [pathname]);

  useEffect(() => {
    const open = () => setAssistantOpen(true);
    window.addEventListener('kaushalwatch:assistant', open);
    return () => window.removeEventListener('kaushalwatch:assistant', open);
  }, []);

  return (
    <div className="min-h-screen bg-[#F7F8FA]">
      <aside className={cn('fixed inset-y-0 left-0 z-30 flex flex-col border-r border-[#E6EAF0] bg-white transition-[width] duration-200', collapsed ? 'w-[76px]' : 'w-[208px]')}>
        <div className={cn('flex h-16 items-center border-b border-[#EEF1F4]', collapsed ? 'justify-center px-3' : 'justify-between px-5')}>
          <Link href="/" className="kw-focus flex items-center gap-3 rounded-xl">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#EFF6FF] text-[#2563EB]"><ShieldCheck size={20} /></span>
            {!collapsed && <span className="text-[16px] font-medium tracking-[-0.01em] text-[#172033]">KaushalWatch</span>}
          </Link>
          {!collapsed && <Button variant="ghost" size="icon" onClick={() => setCollapsed(true)} aria-label="Collapse navigation"><PanelLeftClose size={18} /></Button>}
        </div>

        <nav className="flex-1 space-y-1 px-3 py-5" aria-label="Primary navigation">
          {NAV.map(item => {
            const Icon = item.icon;
            const selected = active === item.href;
            return (
              <Link key={item.href} href={item.href} aria-current={selected ? 'page' : undefined} className={cn('kw-focus flex h-11 items-center rounded-xl text-[15px] font-medium transition-colors', collapsed ? 'justify-center' : 'gap-3 px-3', selected ? 'bg-[#EFF6FF] text-[#1D4ED8]' : 'text-[#667085] hover:bg-[#F8FAFC] hover:text-[#344054]')}>
                <Icon size={19} strokeWidth={1.8} />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-[#EEF1F4] p-3">
          {collapsed ? (
            <Button variant="ghost" size="icon" onClick={() => setCollapsed(false)} aria-label="Expand navigation"><PanelLeftOpen size={18} /></Button>
          ) : (
            <div className="flex items-center gap-2 whitespace-nowrap px-2 py-2 text-[11px] text-[#667085]">
              <span className="h-2 w-2 shrink-0 rounded-full bg-[#98A2B3]" />
              <span>Queue ready · Sync not reported</span>
            </div>
          )}
        </div>
      </aside>

      <div className={cn('min-h-screen transition-[padding] duration-200', collapsed ? 'pl-[76px]' : 'pl-[208px]')}>
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-[#EEF1F4] bg-[#F7F8FA] px-10">
          <div className="text-[13px] font-medium text-[#667085]">Trusted Visual Compliance · PMKVY</div>
          <div className="text-[13px] text-[#98A2B3]">AI surfaces evidence. Officers decide.</div>
        </header>
        <main className="mx-auto w-full max-w-[1280px] px-10 py-10">{children}</main>
      </div>

      <AssistantDrawer open={assistantOpen} onOpenChange={setAssistantOpen} centreId={centreId} />
    </div>
  );
}
