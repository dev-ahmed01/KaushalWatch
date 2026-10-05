'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '../lib/cn';

const tabs = [
  { suffix: '', label: 'Cockpit' },
  { suffix: '/attendance', label: 'Attendance' },
  { suffix: '/practical', label: 'Practical' },
  { suffix: '/infrastructure', label: 'Infrastructure' },
  { suffix: '/evidence', label: 'Evidence' },
];

export default function CentreTabs({ centreId }: { centreId: string }) {
  const pathname = usePathname();
  return (
    <nav className="mb-12 flex flex-wrap gap-1 border-b border-[#E6EAF0]" aria-label="Centre sections">
      {tabs.map(tab => {
        const href = `/centres/${centreId}${tab.suffix}`;
        const active = tab.suffix ? pathname === href : pathname === `/centres/${centreId}`;
        return <Link key={tab.label} href={href} aria-current={active ? 'page' : undefined} className={cn('kw-focus relative px-4 py-3 text-[14px] font-medium transition-colors', active ? 'text-[#1D4ED8]' : 'text-[#667085] hover:text-[#344054]')}>
          {tab.label}
          {active && <span className="absolute inset-x-3 bottom-[-1px] h-0.5 rounded-full bg-[#2563EB]" />}
        </Link>;
      })}
    </nav>
  );
}
