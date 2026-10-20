'use client';

import Link from 'next/link';
import { AlertCircle, ArrowRight, Bot, CheckCircle2, ClipboardList, Eye, FileCheck2, Fingerprint, LoaderCircle, Send, ShieldCheck, Sparkles, Users } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { DataRetry } from './components/NetworkStatus';
import { PageHeader, StatTile, StatusBadge, EmptyState } from './components/WorkspaceUi';
import { askAssistant, getActionQueue, getAssistantStatus, getKaushalBrief, SECURE_PROXY } from './lib/api';
import { useBriefPeriod } from './lib/period';
import type { ActionQueue, AssistantReply, AssistantStatus, KaushalBrief } from './lib/types';

type ChatLine = { id: number; role: 'user' | 'assistant'; text: string; sources?: AssistantReply['sources'] };
const STARTERS = ['Which centres need action?', 'Summarise the priority issue', 'What evidence needs review?'];
const TONES = { high: 'red', medium: 'amber', low: 'blue' } as const;

export default function OverviewPage() {
  const { period } = useBriefPeriod();
  const [brief, setBrief] = useState<KaushalBrief | null>(null);
  const [queue, setQueue] = useState<ActionQueue | null>(null);
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<ChatLine[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [sending, setSending] = useState(false);
  const [askError, setAskError] = useState('');

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.allSettled([getKaushalBrief(period), getActionQueue(period), getAssistantStatus()])
      .then(([b, q, s]) => {
        if (!mounted) return;
        setBrief(b.status === 'fulfilled' ? b.value : null);
        setQueue(q.status === 'fulfilled' ? q.value : null);
        setStatus(s.status === 'fulfilled' ? s.value : null);
        setError(b.status === 'rejected' || q.status === 'rejected' ? 'Some authorised records could not be loaded.' : '');
      })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [period, retry]);

  const counts = brief?.counts;
  const issues = queue?.actions || [];
  const targetCentre = queue?.top_action?.centre_id || brief?.priority?.centre_id || brief?.centres[0]?.centre_id;
  const assistantReady = status?.configured === true && status.available === true && !!targetCentre;
  const highlighted = issues.slice(0, 4);
  const operational = queue?.summary || brief?.bullets?.[0] || 'No authorised operational summary available.';
  const isDemo = brief?.simulated === true || queue?.simulated === true;

  async function submit(question: string) {
    const clean = question.trim();
    if (!clean || !assistantReady || !targetCentre || sending) return;
    setSending(true);
    setAskError('');
    setMessage('');
    setMessages(lines => [...lines, { id: Date.now(), role: 'user', text: clean }]);
    try {
      const answer = await askAssistant(targetCentre, clean, sessionId);
      setSessionId(answer.session_id);
      setMessages(lines => [...lines, { id: Date.now() + 1, role: 'assistant', text: answer.message, sources: answer.sources }]);
    } catch (err) {
      setAskError(err instanceof Error ? err.message : 'KaushalAI could not answer. Try again.');
    } finally {
      setSending(false);
    }
  }
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit(message);
  }

  return <div>
    <PageHeader title="Overview" description={brief ? brief.period_label + ' · Training centre intelligence' : 'Training centre intelligence'}
      action={<div className="flex flex-wrap items-center gap-2">{isDemo && <StatusBadge label="Simulated demo data" />}{!SECURE_PROXY && <Link href="/demo/mission" className="kw-focus inline-flex items-center gap-1 text-[11px] font-semibold text-[#2563eb]">Explore the Proof of Training <ArrowRight size={12}/></Link>}</div>}/>
    {error && <div role="alert" className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#f1dbbf] bg-[#fffbf5] p-3 text-[12px] text-[#8b591f]">
      {error}<DataRetry onRetry={() => setRetry(value => value + 1)} disabled={loading}/></div>}

    <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(330px,2fr)]">
      <div className="min-w-0 space-y-5">
        <section aria-label="Training centre status">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-[14px] font-semibold">Training centre status</h2>
            {brief && <span className="text-[10px] text-[#667085]">{brief.source_counts.analysis_rows_in_period} period analysis records</span>}
          </div>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <StatTile icon={<Users size={18}/>} label="Centres monitored" value={counts?.total ?? '—'} tone="blue"/>
            <StatTile icon={<AlertCircle size={18}/>} label="Open issues" value={queue?.counts.total ?? '—'} tone="red"/>
            <StatTile icon={<ClipboardList size={18}/>} label="Review needed" value={counts?.review ?? '—'} tone="amber"/>
            <StatTile icon={<CheckCircle2 size={18}/>} label="Verified" value={counts?.verified ?? '—'} tone="green"/>
          </div>
        </section>

        <section aria-label="Priority issues" className="kw-surface p-4 sm:p-5">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-[15px] font-semibold">Priority issues</h2>
            <Link href="/issues" className="kw-focus inline-flex items-center gap-1 text-[11px] font-semibold text-[#2563eb]">View all issues <ArrowRight size={13}/></Link>
          </div>
          {highlighted.length ? <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
            {highlighted.map(item => <Link key={item.action_id} href={'/issues?issue=' + encodeURIComponent(item.action_id)}
              className="kw-focus group rounded-xl border border-[#e5edf7] bg-[#fcfdff] p-3.5 transition-colors hover:border-[#a8c8f8] hover:bg-[#f6faff]">
              <div className="flex items-start justify-between gap-2"><h3 className="line-clamp-1 text-[12px] font-semibold">{item.title}</h3>
                <StatusBadge label={item.priority} tone={TONES[item.priority]}/></div>
              <p className="mt-1 truncate text-[11px] font-medium text-[#49617c]">{item.centre_name}</p>
              <p className="mt-1.5 line-clamp-2 min-h-8 text-[11px] leading-4 text-[#7a889e]">{item.reason}</p>
              <span className="mt-2 inline-flex items-center gap-1 text-[10px] font-medium text-[#2563eb]">Inspect evidence <ArrowRight size={12}/></span>
            </Link>)}
          </div> : <div className="mt-3"><EmptyState title={loading ? 'Loading issues…' : queue ? 'No issues in this period' : 'Issue queue unavailable'}
            detail={queue ? 'No action-required records were returned.' : 'Retry to load the authorised queue.'}/></div>}
        </section>

        <section className="kw-surface p-4 sm:p-5" aria-label="Highlighted capabilities">
          <h2 className="text-[14px] font-semibold">Highlighted features</h2>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[{title:'Anonymous observation',icon:Eye,detail:'Aggregate visual signals'},
              {title:'Evidence quality gate',icon:ShieldCheck,detail:'Uncertain when blocked'},
              {title:'Officer review',icon:Fingerprint,detail:'Human-owned decisions'},
              {title:'Source provenance',icon:FileCheck2,detail:'Retained audit records'}].map(item => {
                const Icon = item.icon;
                return <div key={item.title} className="min-w-0"><Icon size={18} className="text-[#2563eb]"/>
                  <h3 className="mt-2 text-[10px] font-semibold leading-4">{item.title}</h3>
                  <p className="mt-0.5 text-[10px] leading-4 text-[#8491a2]">{item.detail}</p></div>;
              })}
          </div>
        </section>
      </div>

      <aside className="flex min-w-0 flex-col overflow-hidden rounded-[18px] border border-[#d1e1f7] bg-[linear-gradient(155deg,#f0f6ff,#ffffff_65%)] p-4 shadow-[var(--kw-shadow)] sm:p-5" aria-label="KaushalAI copilot">
        <div className="flex items-center gap-2.5"><span className="rounded-xl bg-[#e8f0ff] p-2 text-[#2563eb]"><Sparkles size={21}/></span>
          <div><h2 className="text-[18px] font-semibold">KaushalAI copilot</h2><p className="text-[10px] text-[#70819b]">Evidence-aware centre intelligence</p></div>
        </div>
        <div className="mt-4 rounded-xl border border-[#e4ebf7] bg-white p-4">
          <div className="flex items-center gap-2 text-[12px] font-semibold text-[#224f99]"><Bot size={16}/> {assistantReady ? 'Current operational briefing' : 'Operational summary'}</div>
          <p className="mt-2 text-[12px] leading-6 text-[#495c75]">{operational}</p>
          {brief && <p className="mt-3 text-[10px] text-[#8592a5]">Source: {brief.source_counts.analysis_rows_in_period} analyses · {brief.source_counts.unresolved_or_confirmed_cases} saved unresolved/confirmed cases</p>}
        </div>
        {queue?.top_action && <Link href={'/issues?issue=' + encodeURIComponent(queue.top_action.action_id)}
          className="kw-focus mt-3 flex items-center justify-between gap-3 rounded-xl bg-[#eaf2ff] p-4 text-[#244d90]">
          <span><strong className="block text-[10px] uppercase tracking-[.08em]">Top recommendation</strong>
            <span className="mt-1 block text-[12px] font-semibold">{queue.top_action.centre_name}</span>
            <span className="mt-1 block text-[11px]">{queue.top_action.title}</span></span><ArrowRight size={16} className="shrink-0"/>
        </Link>}

        <div className="mt-4 flex-1">
          <h3 className="text-[12px] font-semibold">Try asking</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {STARTERS.map(starter => <button key={starter} type="button" disabled={!assistantReady || sending}
              onClick={() => void submit(starter)} className="kw-focus rounded-lg border border-[#dfe9f8] bg-white px-3 py-2 text-left text-[11px] font-medium text-[#4d6585] hover:bg-[#f7fbff] disabled:cursor-not-allowed disabled:opacity-50">{starter}</button>)}
          </div>
          {messages.length > 0 && <div aria-live="polite" className="kw-scrollbar mt-4 max-h-[270px] space-y-2 overflow-y-auto">
            {messages.map(line => <div key={line.id} className={'rounded-xl p-3 text-[11px] leading-5 ' + (line.role === 'user' ? 'bg-[#eaf2ff]' : 'bg-white')}>
              <strong className="mb-1 block text-[10px]">{line.role === 'assistant' ? 'KaushalAI response' : 'You'}</strong>{line.text}
              {line.sources?.length ? <div className="mt-2 flex flex-wrap gap-2">{line.sources.map(source => <Link key={source.kind+source.id} href={source.href} className="font-semibold text-[#2563eb] hover:underline">{source.label}</Link>)}</div> : null}
            </div>)}
          </div>}
        </div>
        {!assistantReady && <p className="mt-3 text-[11px] leading-5 text-[#667085]">
          Gemini is {status?.configured === false ? 'not configured' : status?.available === false ? 'unavailable' : 'not ready'}. The summary above comes from recorded data, not an AI model. Configure the backend Gemini key to ask questions.
        </p>}
        {askError && <p role="alert" className="mt-2 text-[11px] text-[#b42318]">{askError}</p>}
        <form onSubmit={handleSubmit} className="mt-3 flex items-center gap-2 rounded-xl border border-[#d3e1f4] bg-white p-2">
          <label htmlFor="overview-ai-question" className="sr-only">Ask KaushalAI about authorised evidence</label>
          <input id="overview-ai-question" value={message} disabled={!assistantReady || sending}
            onChange={event => setMessage(event.target.value)} placeholder={assistantReady ? 'Ask about centres, issues or evidence…' : 'AI questions require configured Gemini'}
            className="kw-focus min-w-0 flex-1 bg-transparent px-2 py-1 text-[11px] outline-none placeholder:text-[#8e9bb0] disabled:cursor-not-allowed"/>
          <button type="submit" aria-label="Send question" disabled={!assistantReady || sending || !message.trim()}
            className="kw-focus flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#2563eb] text-white disabled:bg-[#aebed7]">
            {sending ? <LoaderCircle size={15} className="animate-spin"/> : <Send size={15}/>}</button>
        </form>
      </aside>
    </div>
  </div>;
}
