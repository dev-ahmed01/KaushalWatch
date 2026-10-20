'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef } from 'react';
import { cn } from '../lib/cn';
import { LayoutDashboard, Users, Activity, HardHat, FileCheck2, Camera } from 'lucide-react';

const tabs = [
  { suffix: '', label: 'Overview', icon: LayoutDashboard },
  { suffix: '/attendance', label: 'Attendance', icon: Users },
  { suffix: '/practical', label: 'Activity', icon: Activity },
  { suffix: '/infrastructure', label: 'Infrastructure', icon: HardHat },
  { suffix: '/evidence', label: 'Evidence', icon: FileCheck2 },
  { suffix: '/camera-trust', label: 'Camera Trust', icon: Camera },
];

export default function CentreTabs({ centreId }: { centreId: string }) {
  const pathname = usePathname();
  const scroller = useRef<HTMLElement>(null);
  useEffect(() => {
    const nav = scroller.current;
    const active = nav?.querySelector<HTMLElement>('a[aria-current="page"]');
    if (!nav || !active) return;
    // Keep the selected section discoverable on a small viewport without
    // scrolling the entire document or changing the user's reading position.
    const activeLeft = active.offsetLeft - nav.offsetLeft;
    const margin = 12;
    const visibleLeft = nav.scrollLeft;
    const visibleRight = visibleLeft + nav.clientWidth;
    if (activeLeft < visibleLeft + margin) {
      nav.scrollTo({left: Math.max(0, activeLeft - margin), behavior: 'instant'});
    } else if (activeLeft + active.offsetWidth > visibleRight - margin) {
      nav.scrollTo({
        left: activeLeft + active.offsetWidth - nav.clientWidth + margin,
        behavior: 'instant',
      });
    }
  }, [pathname]);
  return (
    <nav
      ref={scroller}
      className="kw-os-subnav mb-6 w-full max-w-full min-w-0 overflow-x-auto overscroll-x-contain rounded-2xl border border-[#E7EDF4] bg-white p-1.5 shadow-[var(--kw-shadow)]"
      aria-label="Centre sections"
    >
      <span className="sr-only">Scroll horizontally to discover all centre sections. The active section is brought into view.</span>
      <div className="flex min-w-max gap-1">
        {tabs.map(tab => {
          const href = `/centres/${centreId}${tab.suffix}`;
          const active = tab.suffix ? pathname === href : pathname === `/centres/${centreId}`;
          return (
            <Link
              key={tab.label}
              href={href}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'kw-focus flex shrink-0 items-center gap-2 whitespace-nowrap rounded-xl px-3.5 py-2.5 text-[12px] font-medium transition-colors',
                active ? 'bg-[#EFF5FF] text-[#1D4ED8]' : 'text-[#708198] hover:bg-[#F8FAFD] hover:text-[#344054]',
              )}
            >
              <tab.icon size={15} strokeWidth={1.8} aria-hidden="true"/>{tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
