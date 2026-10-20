'use client';

import Link from 'next/link';
import { ArrowRight, LoaderCircle, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { askAssistant, getAssistantStatus, getReviewAccess } from '../lib/api';
import type { AssistantReply } from '../lib/types';

export default function EvidenceCopilot({ centreId, fallback, question, sourceHref, compact = false }: {
  centreId: string; fallback: string; question: string; sourceHref?: string; compact?: boolean;
}) {
  const [available, setAvailable] = useState(false);
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState<AssistantReply | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setChecked(false);
    Promise.all([getAssistantStatus(), getReviewAccess()]).then(([status, access]) => {
      if (active) setAvailable(status.enabled === true && status.configured === true &&
        status.available === true && access.can_use_network_assistant !== false);
    }).catch(() => { if (active) setAvailable(false); })
      .finally(() => { if (active) setChecked(true); });
    return () => { active = false; };
  }, []);
  useEffect(() => { setReply(null); setError(''); }, [centreId, question]);

  async function explain() {
    if (!available || busy || !centreId || !question.trim()) return;
    setError(''); setBusy(true);
    try {
      const result = await askAssistant(centreId, question.slice(0, 3800));
      setReply(result);
    } catch (err) { setError(err instanceof Error ? err.message : 'KaushalAI unavailable'); }
    finally { setBusy(false); }
  }
  return <section aria-label="Contextual KaushalAI" className={compact ?
    'rounded-xl border border-[#dce9fa] bg-[#f5f9ff] p-3' :
    'rounded-xl border border-[#dce9fa] bg-[#f5f9ff] p-4'}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="flex items-center gap-1.5 text-[12px] font-semibold text-[#2459a6]"><Sparkles size={14}/> KaushalAI context</h3>
      {available && <button type="button" aria-label="Ask KaushalAI about this record" onClick={() => void explain()} disabled={busy}
        className="kw-focus inline-flex items-center gap-1 rounded-lg border border-[#aecdf4] bg-white px-2.5 py-1.5 text-[10px] font-semibold text-[#2563eb] disabled:opacity-40">
        {busy ? <LoaderCircle size={12} className="animate-spin"/> : <Sparkles size={12}/>}
        {reply ? 'Ask again' : 'Explain with Gemini'}
      </button>}
    </div>
    {reply ? <div aria-live="polite" className="mt-2"><p className="whitespace-pre-wrap text-[11px] leading-5 text-[#405b7e]">{reply.message}</p>
      {reply.sources?.length > 0 && <div className="mt-2 flex flex-wrap gap-2">
        {reply.sources.map(s => <Link href={s.href} key={s.kind+s.id} className="kw-focus inline-flex items-center gap-1 text-[10px] font-semibold text-[#2563eb]">{s.label}<ArrowRight size={11}/></Link>)}
      </div>}</div> :
      <><p className="mt-2 line-clamp-4 text-[11px] leading-5 text-[#536984]">{fallback}</p>
        <p className="mt-1.5 text-[10px] text-[#8896ab]">{available ? 'Recorded summary · select Explain for a Gemini answer' :
          checked ? 'Recorded summary · Gemini unavailable or not authorised' : 'Checking assistant access…'}</p></>}
    {sourceHref && !reply && <Link href={sourceHref} className="kw-focus mt-2 inline-flex items-center gap-1 text-[10px] font-semibold text-[#2563eb]">Open source record <ArrowRight size={11}/></Link>}
    {error && <p role="alert" className="mt-2 text-[10px] text-[#b42318]">{error}</p>}
  </section>;
}
