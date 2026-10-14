'use client';

import { AlertTriangle, RotateCcw } from 'lucide-react';
import { useEffect } from 'react';
import { Button } from './components/ui/button';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[55vh] max-w-xl items-center justify-center px-4">
      <div role="alert" className="w-full rounded-[18px] border border-[#E6EAF0] bg-white p-7 text-center shadow-[var(--kw-shadow)]">
        <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-[#FEF3F2] text-[#B42318]">
          <AlertTriangle size={20} />
        </span>
        <h1 className="mt-4 text-[22px] font-semibold tracking-[-0.03em] text-[var(--kw-text)]">This view could not be loaded</h1>
        <p className="mt-2 text-[13px] leading-6 text-[#667085]">
          Monitoring data has not been changed. Retry the view, or return to another section from the main navigation.
        </p>
        <Button variant="primary" className="mt-5" onClick={reset}>
          <RotateCcw size={15} />
          Retry
        </Button>
      </div>
    </div>
  );
}
