'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { SECURE_PROXY } from '../lib/api';

export default function SecureSessionGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!SECURE_PROXY || pathname === '/login') {
      setReady(true);
      return;
    }
    let alive = true;
    setReady(false);
    fetch('/api/auth/status', { cache: 'no-store', credentials: 'same-origin' })
      .then(response => response.ok ? response.json() : null)
      .then(status => {
        if (!alive) return;
        if (status?.mode === 'protected' && status?.authenticated) setReady(true);
        else router.replace('/login?next=' + encodeURIComponent(pathname));
      })
      .catch(() => { if (alive) router.replace('/login?next=' + encodeURIComponent(pathname)); });
    return () => { alive = false; };
  }, [pathname, router]);

  if (!SECURE_PROXY) return <>{children}</>;
  if (pathname === '/login') return <>{children}</>;
  if (!ready) return <div role="status" className="flex min-h-screen items-center justify-center bg-[#F8FAFC] px-6 text-[14px] text-[#667085]">Verifying officer session…</div>;
  return <>{children}</>;
}
