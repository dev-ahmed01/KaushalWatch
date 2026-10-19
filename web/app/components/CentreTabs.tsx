'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
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
  return (
    <nav
      className="kw-os-subnav mb-6 w-full max-w-full min-w-0 overflow-x-auto rounded-2xl border border-[#E7EDF4] bg-white p-1.5 shadow-[var(--kw-shadow)]"
      aria-label="Centre sections"
    >
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
