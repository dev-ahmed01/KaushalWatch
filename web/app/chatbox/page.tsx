'use client';

import Link from 'next/link';
import { ArrowLeft, ArrowRight, MessageCircle, RefreshCw, Search, Send, ShieldCheck, UserCircle2 } from 'lucide-react';
import { type FormEvent, useCallback, useEffect, useState } from 'react';
import { getChatboxThreads, getChatboxMessages, sendChatboxMessage } from '../lib/api';
import { EmptyState, PageHeader, StatusBadge } from '../components/WorkspaceUi';
import type { ChatThread, ChatMessage, ChatboxIndex } from '../lib/types';
import { VoiceNoteControls, VoiceNotePlayer } from '../components/VoiceNoteControls';

const initialCentre = 'DEMO-KA-104';
const demoActor = (centreId: string) => 'demo-officer-' + centreId;
function timeIst(value: string) {
  return new Date(value).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit'});
}
function personInitial(name: string) { return name.split(' ').map(x=>x[0]).slice(-2).join('').toUpperCase(); }

export default function ChatboxPage() {
  const [actorId,setActorId] = useState(demoActor(initialCentre));
  const [centreId,setCentreId] = useState(initialCentre);
  const [personLink,setPersonLink] = useState('');
  const [issueLink,setIssueLink] = useState('');
  const [index,setIndex] = useState<ChatboxIndex|null>(null);
  const [selected,setSelected] = useState('');
  const [messages,setMessages] = useState<ChatMessage[]>([]);
  const [search,setSearch] = useState('');
  const [filter,setFilter] = useState('all');
  const [draft,setDraft] = useState('');
  const [sending,setSending] = useState(false);
  const [error,setError] = useState('');
  const [loading,setLoading] = useState(true);
  const [mobileThread,setMobileThread] = useState(false);
  const [refresh,setRefresh] = useState(0);

  useEffect(()=>{
    const params=new URLSearchParams(window.location.search);
    const centre=params.get('centre') || initialCentre;
    setCentreId(centre);
    setActorId(demoActor(centre));
    setPersonLink(params.get('person') || '');
    setIssueLink(params.get('issue') || '');
  },[]);

  useEffect(()=>{
    let live=true;
    setLoading(true);
    setMessages([]);
    getChatboxThreads(actorId).then(result=>{
      if (!live) return;
      setIndex(result);
      const preferred=result.threads.find(t=>personLink && t.participant_ids.includes(personLink));
      const target=preferred || result.threads.find(t=>t.id===selected) || result.threads[0];
      setSelected(target?.id || '');
      setError('');
    }).catch(err=>{if(live){setIndex(null);setError(err instanceof Error?err.message:'Chatbox is unavailable');}})
      .finally(()=>{if(live)setLoading(false);});
    return()=>{live=false};
  },[actorId,personLink,refresh]);

  const updateMessages=useCallback(async()=>{
    if (!selected) {setMessages([]);return;}
    const response=await getChatboxMessages(selected,actorId);
    setMessages(response.messages);
  },[selected,actorId]);

  useEffect(()=>{
    if (!selected) return;
    let live=true;
    getChatboxMessages(selected,actorId).then(response=>{if(live)setMessages(response.messages);})
      .catch(err=>{if(live)setError(err instanceof Error?err.message:'Message history unavailable');});
    const timer=window.setInterval(()=>{
      if(document.visibilityState!=='visible')return;
      getChatboxMessages(selected,actorId).then(response=>{if(live)setMessages(response.messages);}).catch(()=>{});
    },10000);
    return()=>{live=false;window.clearInterval(timer)};
  },[selected,actorId,refresh]);

  async function send(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !draft.trim() || sending) return;
    const clean=draft.trim();
    const idem=crypto.randomUUID();
    setSending(true);setError('');
    try {
      await sendChatboxMessage(selected,actorId,clean,idem);
      setDraft('');
      await updateMessages();
      setRefresh(x=>x+1);
    } catch (err) {setError(err instanceof Error?err.message:'Message could not be saved');}
    finally {setSending(false);}
  }
  const thread=index?.threads.find(t=>t.id===selected);
  const visible=index?.threads.filter(t=>{
    const q=search.trim().toLowerCase();
    return (filter==='all'||t.peer.role===filter)&&(!q||t.peer.name.toLowerCase().includes(q)||t.topic.toLowerCase().includes(q));
  })||[];
  const peer=thread?.peer;
  return <div>
    <PageHeader title="Chatbox" description="Centre conversations"
      action={<div className="flex items-center gap-2">
        {index?.simulated && <StatusBadge label="Simulated demo messages"/>}
        <button aria-label="Refresh conversations" onClick={()=>setRefresh(x=>x+1)} type="button" className="kw-focus rounded-lg border border-[#dce6f2] p-2 text-[#657d9d]"><RefreshCw size={16}/></button>
      </div>}/>
    {error && <div role="alert" className="mb-3 rounded-xl border border-[#f1dbbf] bg-[#fffbf5] p-3 text-[12px] text-[#8a5720]">{error}</div>}
    {!index && !loading && <EmptyState title="Chatbox unavailable" detail="Controlled local demo accounts are required. No messages were delivered or fabricated."/>}
    {loading && !index && <div role="status" className="kw-surface p-5 text-[12px] text-[#667085]">Loading permitted conversations…</div>}
    {index && <section aria-label="Chatbox workspace" className="grid min-w-0 overflow-hidden rounded-2xl border border-[#e2eaf5] bg-white shadow-[var(--kw-shadow)] md:grid-cols-[minmax(210px,280px)_minmax(0,1fr)] xl:grid-cols-[minmax(210px,280px)_minmax(0,1fr)_220px]">
      <aside aria-label="Conversations" className={'min-w-0 border-r border-[#e8eef6] p-3 sm:p-4 '+(mobileThread?'hidden md:block':'block')}>
        <label htmlFor="chat-actor" className="text-[10px] font-semibold text-[#8797aa]">Demo role (local only)</label>
        <select id="chat-actor" aria-label="Demo role" value={actorId} onChange={e=>{setActorId(e.target.value);setPersonLink('');setMobileThread(false);}}
          className="kw-focus mt-1 h-10 w-full min-w-0 rounded-lg border border-[#dae5f2] bg-white px-2 text-[11px]">
          {index.roles.map(p=><option key={p.id} value={p.id}>{p.name} · {p.role.replaceAll('_',' ')}</option>)}
        </select>
        <div className="relative mt-4"><Search size={14} className="pointer-events-none absolute left-3 top-3 text-[#94a3b8]"/>
          <label htmlFor="chat-search" className="sr-only">Search conversations</label>
          <input id="chat-search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search people" className="kw-focus h-9 w-full rounded-lg border border-[#dae5f2] bg-white pl-8 pr-2 text-[11px]"/></div>
        <div className="kw-scrollbar mt-3 flex gap-1.5 overflow-x-auto pb-2" aria-label="Conversation role filters">
          {['all','centre_head','trainer','officer'].map(value=><button type="button" key={value} onClick={()=>setFilter(value)} aria-pressed={filter===value}
            className={'kw-focus shrink-0 rounded-lg px-2 py-1.5 text-[10px] font-medium '+(filter===value?'bg-[#eaf2ff] text-[#215bb2]':'bg-[#f7f9fc] text-[#667085]')}>{value==='all'?'All':value.replaceAll('_',' ')}</button>)}
        </div>
        <div className="mt-2 space-y-1" aria-label="Permitted threads">
          {visible.map(t=><button key={t.id} type="button" aria-pressed={selected===t.id} onClick={()=>{setSelected(t.id);setMobileThread(true);}}
            className={'kw-focus flex w-full items-center gap-2.5 rounded-xl p-2.5 text-left '+(selected===t.id?'bg-[#edf5ff]':'hover:bg-[#f8faff]')}>
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#dceafd] text-[11px] font-semibold text-[#2563eb]">{personInitial(t.peer.name)}</span>
            <span className="min-w-0 flex-1"><strong className="block truncate text-[11px]">{t.peer.name}</strong>
              <span className="block truncate text-[10px] capitalize text-[#8a99aa]">{t.last_message?.kind==='text'?t.last_message.body||'':t.last_message?'Voice note':t.peer.role.replaceAll('_',' ')}</span></span>
            {t.last_message && <span className="text-[9px] text-[#94a3b8]">{timeIst(t.last_message.created_at_utc)}</span>}
          </button>)}
          {!visible.length && <p className="p-3 text-[11px] text-[#8491a3]">No permitted conversations match.</p>}
        </div>
      </aside>
      <div className={'flex min-w-0 min-h-[510px] flex-col bg-[#fbfcff] '+(!mobileThread?'hidden md:flex':'flex')}>
        {thread ? <>
          <header className="flex items-center gap-2 border-b border-[#e6ecf5] bg-white px-3 py-3 sm:px-4">
            <button type="button" aria-label="Back to conversations" onClick={()=>setMobileThread(false)} className="kw-focus rounded-lg p-1 text-[#687a92] md:hidden"><ArrowLeft size={17}/></button>
            <UserCircle2 size={24} className="text-[#3973c6]"/>
            <span className="min-w-0 flex-1"><strong className="block truncate text-[12px]">{peer?.name}</strong>
              <small className="block text-[10px] capitalize text-[#8d9bb0]">{peer?.role.replaceAll('_',' ')} · Local demo</small></span>
            <ShieldCheck size={15} className="text-[#0a996d]"/>
          </header>
          {issueLink && <Link className="kw-focus flex items-center justify-between gap-2 border-b border-[#e4ecf6] bg-[#f2f7ff] px-4 py-2 text-[11px] text-[#275cad]"
            href={'/issues?issue='+encodeURIComponent(issueLink)}>Related issue <ArrowRight size={13}/></Link>}
          <div aria-label="Message history" aria-live="polite" className="kw-scrollbar flex-1 space-y-3 overflow-y-auto p-4" style={{minHeight:300,maxHeight:510}}>
            {!messages.length && <p className="py-16 text-center text-[12px] text-[#8a97a9]">No messages yet. Start an authorised demo conversation.</p>}
            {messages.map(msg=><div key={msg.id} className={'flex '+(msg.sender_id===actorId?'justify-end':'justify-start')}>
              <div className={'max-w-[85%] rounded-xl px-3 py-2.5 text-[12px] leading-5 sm:max-w-[75%] '+(msg.sender_id===actorId?'bg-[#2563eb] text-white':'border border-[#e2e9f2] bg-white text-[#40516a]')}>
                {msg.kind==='text'?<p className="whitespace-pre-wrap break-words">{msg.body}</p>:<VoiceNotePlayer messageId={msg.id} actorId={actorId} durationMs={msg.duration_ms}/>}
                <small className={'mt-1 block text-right text-[9px] '+(msg.sender_id===actorId?'text-[#c8ddff]':'text-[#8c9aaa]')}>{timeIst(msg.created_at_utc)} IST</small>
              </div>
            </div>)}
          </div>
          <VoiceNoteControls key={selected + actorId} threadId={selected} actorId={actorId} onSent={() => { void updateMessages(); setRefresh(x => x + 1); }}/>
          <form onSubmit={send} className="flex min-w-0 items-end gap-2 border-t border-[#e7edf5] bg-white p-3">
            <label htmlFor="chat-draft" className="sr-only">Type a text message</label>
            <textarea id="chat-draft" rows={2} maxLength={2000} value={draft} onChange={e=>setDraft(e.target.value)}
              onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();e.currentTarget.form?.requestSubmit();}}}
              placeholder="Message…" className="kw-focus min-w-0 flex-1 resize-none rounded-xl border border-[#dae5f3] bg-[#fbfdff] p-2.5 text-[11px] outline-none"/>
            <button type="submit" aria-label="Send message" disabled={!draft.trim()||sending}
              className="kw-focus flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#2563eb] text-white disabled:bg-[#a7bddf]"><Send size={17}/></button>
          </form>
        </> : <EmptyState title="Select a conversation" detail="Only permitted demo participants are shown."/>}
      </div>
      <aside className="hidden min-w-0 border-l border-[#e6ecf5] p-4 xl:block" aria-label="Conversation details">
        <h2 className="text-[13px] font-semibold">Conversation details</h2>
        {peer&&<div className="mt-4 rounded-xl bg-[#f7faff] p-3"><p className="text-[12px] font-semibold">{peer.name}</p>
          <p className="mt-1 text-[10px] capitalize text-[#8390a4]">{peer.role.replaceAll('_',' ')}</p></div>}
        <div className="mt-4 space-y-2 text-[11px] text-[#708198]"><p>{centreId}</p><p>Private local demo transport</p>
          <p>Role and centre membership checked on each request. Message receipts are not fabricated.</p></div>
        {issueLink && <Link href={'/issues?issue='+encodeURIComponent(issueLink)} className="kw-focus mt-4 inline-flex items-center gap-1 text-[11px] font-semibold text-[#2563eb]">Open linked issue <ArrowRight size={13}/></Link>}
        <div className="mt-5 flex items-start gap-2 border-t border-[#e8eef5] pt-4 text-[10px] leading-5 text-[#8a98a9]"><MessageCircle size={15} className="shrink-0"/> AI conversation summaries require a separately authorised source-grounded integration.</div>
      </aside>
    </section>}
  </div>;
}
