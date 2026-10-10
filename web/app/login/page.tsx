'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { SECURE_PROXY } from '../lib/api';

export default function OfficerLogin() {
  const query = useSearchParams();
  const next = query.get('next') || '/';
  const safeNext = next.startsWith('/') && !next.startsWith('//') && !next.includes('\\') ? next : '/';
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!SECURE_PROXY) return;
    fetch('/api/auth/status', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then(status => {
        if (status?.authenticated && status.mode === 'protected') window.location.replace(safeNext);
      }).catch(() => {});
  }, [safeNext]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
        body: JSON.stringify({ accessKey: key }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail || 'Officer login unavailable.');
      // Discard the officer key immediately; only the server has the session.
      setKey('');
      window.location.replace(safeNext);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Officer login failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F8FAFC] px-5 py-10">
      <section className="w-full max-w-[420px] rounded-2xl border border-[#E6EAF0] bg-white p-8 shadow-[0_12px_32px_rgba(16,24,40,.06)]">
        <div className="mb-7 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#EFF6FF] text-[#1D4ED8] text-[22px]">◈</div>
          <div>
            <h1 className="text-[23px] font-semibold tracking-[-0.03em] text-[#101828]">Officer sign in</h1>
            <p className="mt-0.5 text-[12px] text-[#667085]">KaushalWatch · protected evidence console</p>
          </div>
        </div>
        <p className="mb-6 text-[13px] leading-6 text-[#667085]">Enter the access key assigned by your administrator. The key is exchanged for a short-lived, HttpOnly browser session. It is not saved in local storage.</p>
        {!SECURE_PROXY ? (
          <p role="alert" className="text-[13px] text-[#B42318]">Protected browser sign-in is disabled for this local demo build.</p>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <label htmlFor="kw-officer-key" className="block text-[13px] font-medium text-[#344054]">Officer access key</label>
            <input id="kw-officer-key" type="password" value={key}
              onChange={e => setKey(e.target.value)} autoComplete="off" spellCheck={false}
              className="kw-focus w-full rounded-xl border border-[#D0D5DD] px-4 py-3 text-[14px] text-[#101828]"
              required minLength={32} maxLength={1024} placeholder="Enter access key" />
            {error && <p role="alert" className="text-[12px] text-[#B42318]">{error}</p>}
            <button type="submit" disabled={busy} className="kw-focus w-full rounded-xl bg-[#2563EB] px-4 py-3 text-[14px] font-semibold text-white disabled:opacity-50">
              {busy ? 'Checking key…' : 'Sign in securely'}
            </button>
          </form>
        )}
        <p className="mt-6 text-[11px] leading-5 text-[#98A2B3]">No official government identity integration is implied. All sensitive reads and evidence require server-side authorization.</p>
      </section>
    </main>
  );
}
