'use client';

import { createContext, useContext, useMemo, useState } from 'react';

export type BriefPeriod = 'yesterday' | 'last_7_days' | 'last_30_days';

type PeriodContextValue = {
  period: BriefPeriod;
  setPeriod: (period: BriefPeriod) => void;
  label: string;
};

const LABELS: Record<BriefPeriod, string> = {
  yesterday: 'Yesterday',
  last_7_days: '7 days',
  last_30_days: '30 days',
};

const PeriodContext = createContext<PeriodContextValue | null>(null);

export function PeriodProvider({ children }: { children: React.ReactNode }) {
  const [period, setPeriod] = useState<BriefPeriod>('yesterday');
  const value = useMemo(
    () => ({ period, setPeriod, label: LABELS[period] }),
    [period],
  );
  return <PeriodContext.Provider value={value}>{children}</PeriodContext.Provider>;
}

export function useBriefPeriod() {
  const value = useContext(PeriodContext);
  if (!value) throw new Error('useBriefPeriod must be used within PeriodProvider');
  return value;
}
