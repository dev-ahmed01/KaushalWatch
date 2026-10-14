'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '../lib/cn';

const tabs = [
  { suffix: '', label: 'Overview' },
  { suffix: '/attendance', label: 'Attendance' },
  { suffix: '/practical', label: 'Activity' },
  { suffix: '/infrastructure', label: 'Infrastructure' },
  { suffix: '/evidence', label: 'Evidence' },
];

export default function CentreTabs({ centreId }: { centreId: string }) {
  const pathname = usePathname();
  return (
    <nav
      className="kw-scrollbar mb-7 w-full max-w-full min-w-0 overflow-x-auto border-b border-[#E6EAF0]"
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
                'kw-focus relative shrink-0 whitespace-nowrap px-4 py-3 text-[14px] font-medium transition-colors',
                active ? 'text-[#1D4ED8]' : 'text-[#667085] hover:text-[#344054]',
              )}
            >
              {tab.label}
              {active && <span className="absolute inset-x-3 bottom-[-1px] h-0.5 rounded-full bg-[#2563EB]" />}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
