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

  return <aside className="assistantPanel">
    <div className="assistantHeader">
      <div className="assistantSpark">✦</div>
      <div><strong>Ask KaushalWatch</strong><small>Your compliance assistant</small></div>
      <span className="assistantOnline">● Grounded</span>
    </div>

    <div className="assistantQuick">
      {QUICK.map(item=><button type="button" key={item} onClick={()=>ask(item)}>{item}<span>›</span></button>)}
    </div>

    <div className="assistantConversation">
      {!reply&&!busy&&!error&&<div className="assistantWelcome">
        <span>AI</span>
        <p>Ask in simple language. I answer only from this centre’s recorded analyses, cases and policy state.</p>
      </div>}
      {question&&<div className="chatBubble user">{question}</div>}
      {busy&&<div className="chatBubble ai typing"><i></i><i></i><i></i></div>}
      {error&&<div className="assistantError">{error}</div>}
      {reply&&!busy&&<div className="assistantAnswer">
        <div className="chatBubble ai">{reply.answer}</div>
        <div className="groundingNote">Grounded in {reply.grounded_in.history_rows} analysis records · {reply.grounded_in.pending_cases} pending cases</div>
        <div className="assistantAnswerActions">
          <Link href={`/reports?centre=${encodeURIComponent(centreId)}&period=7d`} className="assistantAction">Generate report</Link>
          <Link href={`/centres/${centreId}/history`} className="assistantAction ghost">View history</Link>
        </div>
      </div>}
    </div>

    <form className="assistantComposer" onSubmit={event=>{event.preventDefault();ask(question);}}>
      <input value={question} onChange={event=>setQuestion(event.target.value)} placeholder="Ask about this centre…" />
      <button type="submit" disabled={busy}>↑</button>
    </form>
  </aside>;
}
