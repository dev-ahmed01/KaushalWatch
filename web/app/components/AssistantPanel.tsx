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

  if(collapsed) return <aside className="neoAssistant collapsed">
    <button type="button" className="neoAssistantLauncher" onClick={()=>setCollapsed(false)}>
      <span>✦</span><b>Ask AI</b>
    </button>
  </aside>;

  return <aside className="neoAssistant">
    <div className="neoAssistantHead">
      <span className="neoAiOrb">✦</span>
      <div><b>Ask KaushalWatch</b><small>Evidence-grounded assistant</small></div>
      <span className="neoGrounded"><i></i>Grounded</span>
      <button type="button" className="neoAssistantClose" onClick={()=>setCollapsed(true)} aria-label="Collapse assistant">×</button>
    </div>

    <div className="neoAssistantContext">
      <span>Current centre</span>
      <b>{centreId}</b>
      <small>Simple answers from analyses, cases and policy state.</small>
    </div>

    <div className="neoAssistantQuick">
      {QUICK.map(item=><button key={item} type="button" onClick={()=>ask(item)}>
        <span>◌</span><b>{item}</b><i>›</i>
      </button>)}
    </div>

    <div className="neoAssistantBody">
      {!reply&&!busy&&!error&&<div className="neoAiWelcome">
        <span>AI</span>
        <div>
          <b>Ask in plain language.</b>
          <p>I can explain what passed, what needs attention, why a centre was escalated, or turn recent activity into a report.</p>
        </div>
      </div>}

      {question&&<div className="neoChat user">{question}</div>}
      {busy&&<div className="neoChat ai loading"><i></i><i></i><i></i></div>}
      {error&&<div className="neoAssistantError">{error}</div>}

      {reply&&!busy&&<div className="neoAssistantAnswer">
        <div className="neoChat ai">{reply.answer}</div>
        <div className="neoGrounding"><span>✓</span>Grounded in {reply.grounded_in.history_rows} analysis record(s) and {reply.grounded_in.pending_cases} pending case(s).</div>
        <div className="neoAssistantActions">
          <Link href={'/reports?centre='+encodeURIComponent(centreId)+'&period='+encodeURIComponent(reply.period||'7d')} className="neoAiPrimary">Create report</Link>
          <Link href={'/centres/'+centreId+'/history'} className="neoAiSecondary">Open history</Link>
        </div>
      </div>}
    </div>

    <form className="neoAssistantComposer" onSubmit={event=>{event.preventDefault();ask(question);}}>
      <input value={question} onChange={event=>setQuestion(event.target.value)} placeholder="Ask about this centre…"/>
      <button disabled={busy} type="submit" aria-label="Ask KaushalWatch">↑</button>
    </form>
  </aside>;
}
