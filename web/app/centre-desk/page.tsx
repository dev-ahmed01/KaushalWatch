'use client';

import Link from 'next/link';
import { ArrowRight, Bell, CalendarDays, Check, ClipboardList, HardHat, MessageCircle, RefreshCw, Sparkles, Users } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { getCentreDeskDay, updateCentreDeskTask } from '../lib/api';
import { EmptyState, PageHeader, StatTile, StatusBadge } from '../components/WorkspaceUi';
import EvidenceCopilot from '../components/EvidenceCopilot';
import type { CentreDeskResponse, CentreDeskTask } from '../lib/types';

function lastUpdate(value: string) {
  return new Date(value).toLocaleTimeString('en-IN', {timeZone: 'Asia/Kolkata',hour:'2-digit',minute:'2-digit'}) + ' IST';
}
export default function CentreDeskPage() {
  const [centreId, setCentreId] = useState('');
  const [data, setData] = useState<CentreDeskResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyTask, setBusyTask] = useState('');
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active=true;
    setLoading(true);
    getCentreDeskDay(centreId || undefined).then(response => {
      if (!active) return;
      setData(response);
      setCentreId(response.day.centre_id);
      setError('');
    }).catch(err => { if (active) { setData(null); setError(err instanceof Error ? err.message : 'Centre Desk unavailable'); }})
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [centreId,refresh]);

  const update = useCallback(async (task: CentreDeskTask, status: CentreDeskTask['status']) => {
    if (busyTask || !data) return;
    setBusyTask(task.id);
    setError('');
    try {
      await updateCentreDeskTask(data.day.centre_id, task.id, status);
      setRefresh(number => number + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update task');
    } finally {
      setBusyTask('');
    }
  }, [busyTask, data]);

  const day = data?.day;
  const summaries = day ? [
    {label:'Batches today', value:day.counts.batches_today, icon:<CalendarDays size={19}/>,tone:'blue' as const},
    {label:'Trainers present', value:day.counts.trainers_present ?? '—', icon:<Users size={19}/>,tone:'neutral' as const},
    {label:'Equipment alerts', value:day.counts.equipment_alerts, icon:<HardHat size={19}/>,tone:'amber' as const},
    {label:'Attendance follow-ups', value:day.counts.attendance_followups, icon:<ClipboardList size={19}/>,tone:'red' as const},
    {label:'Messages pending', value:day.counts.messages_pending ?? '—', icon:<MessageCircle size={19}/>,tone:'neutral' as const},
  ] : [];

  return <div>
    <PageHeader title="Centre Desk" description={day ? day.centre_name + ' · ' + day.date_local + ' · IST' : 'Centre operations'}
      action={<div className="flex items-center gap-2">
        {day && <StatusBadge label="Simulated demo data"/>}
        {data && <label><span className="sr-only">Centre context</span>
          <select className="kw-focus max-w-[170px] rounded-lg border border-[#dce5f1] bg-white px-2 py-2 text-[11px]" value={centreId}
            onChange={e => setCentreId(e.target.value)} aria-label="Centre context">
            {data.centres.map(c=><option key={c.centre_id} value={c.centre_id}>{c.name}</option>)}
          </select></label>}
        <button type="button" onClick={() => setRefresh(n=>n+1)} aria-label="Refresh Centre Desk" className="kw-focus rounded-lg border border-[#dce5f1] p-2 text-[#667085]"><RefreshCw size={16}/></button>
      </div>}/>
    {error && <div role="alert" className="mb-4 rounded-xl border border-[#efd9cb] bg-[#fff9f5] p-3 text-[12px] text-[#a34b27]">{error}</div>}
    {loading && !day && <p role="status" className="kw-surface p-6 text-[12px] text-[#667085]">Loading authorised Centre Desk…</p>}
    {day && <div className="space-y-4">
      <div aria-label="Today at a glance">
        <h2 className="mb-2 text-[14px] font-semibold">Today at a glance</h2>
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-5">
          {summaries.map(x=><StatTile key={x.label} {...x}/>)}
        </div>
        <p className="mt-2 text-[10px] text-[#8493a7]">Trainer check-ins and message receipts are not recorded. “—” means unavailable, not zero.</p>
      </div>
      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(255px,1.25fr)]">
        <div className="min-w-0 space-y-4">
          <section className="kw-surface p-4 sm:p-5" aria-label="Today's batches">
            <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-[15px] font-semibold">Today’s batches</h2>
              <span className="text-[10px] text-[#8493a7]">Scheduled · {day.timezone}</span></div>
            <div className="mt-3 space-y-2">
              {day.batches.map(batch=><div key={batch.id} className="grid gap-2 rounded-xl border border-[#e5ebf3] px-3 py-3 sm:grid-cols-[78px_minmax(0,1fr)_auto] sm:items-center">
                <strong className="text-[12px] text-[#23599d]">{batch.starts_at_ist}</strong>
                <div className="min-w-0"><p className="truncate text-[12px] font-semibold">{batch.trade}</p>
                  <p className="mt-0.5 text-[10px] text-[#8392a6]">{batch.participant_count} on planned roster · Demo lead trainer · until {batch.ends_at_ist}</p></div>
                <StatusBadge label={batch.readiness} tone="blue"/>
              </div>)}
            </div>
          </section>
          <section className="kw-surface p-4 sm:p-5" aria-label="Centre operational actions">
            <div className="flex items-center justify-between gap-2"><h2 className="text-[15px] font-semibold">Action needed</h2>
              <span className="text-[10px] text-[#8493a7]">{day.tasks.filter(x=>x.status!=='resolved').length} open tasks</span></div>
            <div className="mt-3 divide-y divide-[#edf1f6]">
              {day.tasks.map(task=><div key={task.id} className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-0 flex-1"><p className="text-[12px] font-semibold">{task.title}</p>
                  <div className="mt-1 flex items-center gap-2"><StatusBadge label={task.status.replaceAll('_',' ')} tone={task.status==='resolved'?'green':task.status==='acknowledged'?'blue':'amber'}/>
                    <span className="text-[10px] text-[#7e8fa5]">{task.category}</span></div></div>
                {task.status==='pending' && <button type="button" disabled={!!busyTask} onClick={()=>void update(task,'acknowledged')}
                  aria-label={'Acknowledge '+task.title} className="kw-focus rounded-lg border border-[#d3e1f5] px-3 py-2 text-[11px] font-semibold text-[#2563eb] disabled:opacity-40">Acknowledge</button>}
                {task.status==='acknowledged' && <button type="button" disabled={!!busyTask} onClick={()=>void update(task,'resolved')}
                  aria-label={'Complete '+task.title} className="kw-focus inline-flex items-center gap-1 rounded-lg bg-[#2563eb] px-3 py-2 text-[11px] font-semibold text-white disabled:opacity-40"><Check size={12}/> Complete</button>}
              </div>)}
            </div>
          </section>
        </div>
        <aside className="min-w-0 space-y-4">
          <section className="kw-surface p-4 sm:p-5" aria-label="People to reach">
            <h2 className="text-[15px] font-semibold">People to reach</h2>
            <div className="mt-3 divide-y divide-[#edf1f6]">
              {day.contacts.map(person=><Link key={person.id} href={'/chatbox?person='+encodeURIComponent(person.id)+'&centre='+encodeURIComponent(day.centre_id)}
                className="kw-focus flex items-center gap-2.5 py-3 hover:text-[#2563eb]">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#eaf2ff] text-[12px] font-semibold text-[#2563eb]">{person.name.split(' ').slice(-1)[0]?.[0] || 'D'}</span>
                <span className="min-w-0 flex-1"><span className="block truncate text-[11px] font-semibold">{person.name}</span>
                  <span className="block text-[10px] capitalize text-[#8b99ad]">{person.role.replaceAll('_',' ')}</span></span><ArrowRight size={14}/>
              </Link>)}
            </div>
            <p className="mt-2 text-[10px] leading-4 text-[#8998aa]">Demo contacts only. Messaging is activated after membership checks are connected.</p>
          </section>
          <section className="rounded-2xl border border-[#d9e5fa] bg-[#eff6ff] p-4" aria-label="Operational priorities">
            <div className="flex items-center gap-2"><Sparkles size={16} className="text-[#2563eb]"/><h2 className="text-[13px] font-semibold">Operational priorities</h2></div>
            <p className="mt-2 text-[11px] leading-5 text-[#526887]">{day.tasks.find(t=>t.status!=='resolved')?.title || 'No open fixture tasks.'}</p>
            <p className="mt-2 text-[10px] text-[#7d90ab]">Rule-based task summary · not an AI-generated assessment</p>
            <div className="mt-3"><EvidenceCopilot centreId={day.centre_id} compact fallback={day.tasks.find(t=>t.status!=='resolved')?.title || 'No open fixture tasks.'} question={'Review the recorded centre intelligence for '+day.centre_name+'. Explain evidence-backed follow-ups only. Batch, roster and task fixtures are local demo data, not measurements.'}/></div>
          </section>
        </aside>
      </div>
      <footer className="flex items-center gap-2 text-[10px] text-[#8a99ad]">
        <Bell size={13}/> Saved local operational fixtures · refreshed {lastUpdate(day.last_refreshed_at_utc)} · No live staff integration</footer>
    </div>}
    {!loading && !day && <EmptyState title="Centre Desk unavailable" detail="This operation requires the controlled local fixture environment or a provisioned staff integration."/>}
  </div>;
}
