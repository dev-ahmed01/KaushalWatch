'use client';

import { useState } from 'react';
import Link from 'next/link';
import { askAssistant } from '../lib/api';
import type { AssistantReply } from '../lib/types';

const QUICK=[
  'What happened today?',
  'Summarise the last 7 days',
  'Why is this centre escalated?',
  'What needs officer verification?',
];

export default function AssistantPanel({centreId}:{centreId:string}){
  const [question,setQuestion]=useState('');
  const [reply,setReply]=useState<AssistantReply|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [collapsed,setCollapsed]=useState(false);

  async function ask(text:string){
    const q=text.trim();
    if(!q) return;
    setQuestion(q);
    setBusy(true);
    setError('');
    try{
      setReply(await askAssistant(centreId,q,'7d'));
    }catch(err:any){
      setError(err.message||'Assistant unavailable');
    }finally{
      setBusy(false);
    }
  }

  if(collapsed) return <aside className="assistantPanel collapsed">
    <button className="assistantExpand" type="button" onClick={()=>setCollapsed(false)} aria-label="Open KaushalWatch assistant">
      <span>✦</span><b>AI</b>
    </button>
  </aside>;

  return <aside className="assistantPanel">
    <div className="assistantHeader">
      <div className="assistantSpark">✦</div>
      <div className="assistantTitle"><strong>Ask KaushalWatch</strong><small>Evidence-grounded compliance assistant</small></div>
      <span className="assistantOnline"><i></i>Grounded</span>
      <button className="assistantCollapse" type="button" onClick={()=>setCollapsed(true)} aria-label="Collapse assistant">×</button>
    </div>

    <div className="assistantContext">
      <span>Current centre</span>
      <strong>{centreId}</strong>
      <small>Answers use recorded analyses, cases and policy state only.</small>
    </div>

    <div className="assistantQuick">
      {QUICK.map(item=><button type="button" key={item} onClick={()=>ask(item)}><span>{item}</span><b>›</b></button>)}
    </div>

    <div className="assistantConversation">
      {!reply&&!busy&&!error&&<div className="assistantWelcome">
        <span>AI</span>
        <div><strong>Ask in simple language.</strong><p>I can explain what passed, what failed, why something was escalated, or turn the history into a report.</p></div>
      </div>}
      {question&&<div className="chatBubble user">{question}</div>}
      {busy&&<div className="chatBubble ai typing"><i></i><i></i><i></i></div>}
      {error&&<div className="assistantError">{error}</div>}
      {reply&&!busy&&<div className="assistantAnswer">
        <div className="chatBubble ai">{reply.answer}</div>
        <div className="groundingNote"><span>✓</span>Grounded in {reply.grounded_in.history_rows} analysis records · {reply.grounded_in.pending_cases} pending cases</div>
        <div className="assistantSuggestions">
          {(reply.suggested_actions||[]).slice(0,3).map(item=><button key={item} type="button" onClick={()=>ask(item)}>{item}</button>)}
        </div>
        <div className="assistantAnswerActions">
          <Link href={`/reports?centre=${encodeURIComponent(centreId)}&period=${encodeURIComponent(reply.period||'7d')}`} className="assistantAction">Create report</Link>
          <Link href={`/centres/${centreId}/history`} className="assistantAction ghost">Open history</Link>
        </div>
      </div>}
    </div>

    <form className="assistantComposer" onSubmit={event=>{event.preventDefault();ask(question);}}>
      <input value={question} onChange={event=>setQuestion(event.target.value)} placeholder="Ask about this analysis or centre…" />
      <button type="submit" disabled={busy} aria-label="Ask assistant">↑</button>
    </form>
  </aside>;
}
