'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import AssistantPanel from '../components/AssistantPanel';
import { getCentres } from '../lib/api';
import type { Centre } from '../lib/types';
import { Metric, PageHeader, Status } from '../components/Ui';

export default function EscalationsPage(){
  const [centres,setCentres]=useState<Centre[]>([]);
  const [selected,setSelected]=useState('DEMO-KA-104');
  useEffect(()=>{getCentres().then(r=>setCentres(r.centres)).catch(()=>{});},[]);
  const escalated=useMemo(()=>centres.filter(c=>c.escalation.level>0).sort((a,b)=>b.escalation.level-a.escalation.level),[centres]);
  const selectedCentre=centres.find(c=>c.centre_id===selected)||escalated[0]||centres[0];

  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Escalation operations" title="Escalations & Review" subtitle="Repeated, severe, unresolved or multi-signal issues rise above ordinary centre review."
      actions={<><select className="headerSelect" value={selected} onChange={e=>setSelected(e.target.value)}>{centres.map(c=><option key={c.centre_id} value={c.centre_id}>{c.name}</option>)}</select><Link href={selectedCentre?`/centres/${selectedCentre.centre_id}/review`:'#'} className="primaryBtn">Open Review Queue</Link></>}/>
    <section className="metricGrid four">
      <Metric label="Open escalations" value={escalated.length} note="Any active escalation trigger" icon="!"/>
      <Metric label="High priority" value={escalated.filter(c=>c.escalation.level>=3).length} note="Regional or ministry review" tone="danger" icon="▲"/>
      <Metric label="Centre review" value={escalated.filter(c=>c.escalation.level===1).length} note="Single persistent exception" tone="warn" icon="●"/>
      <Metric label="Multi-signal" value={escalated.filter(c=>c.escalation.reasons.some(r=>r.includes('multiple independent'))).length} note="Independent signals fired" icon="◈"/>
    </section>

    <div className="escalationLayout">
      <section className="panel escalationTable">
        <div className="panelHead"><div><span className="sectionKicker">Priority order</span><h2>Active escalations</h2></div><span>{escalated.length} centres</span></div>
        <div className="escalationRows">
          {escalated.map(c=><button type="button" key={c.centre_id} className={selected===c.centre_id?'escalationRow selected':'escalationRow'} onClick={()=>setSelected(c.centre_id)}>
            <span className={`escalationIcon level${c.escalation.level}`}>!</span>
            <div><strong>{c.name}</strong><small>{c.escalation.reasons.join(' · ')}</small><em>{c.location}</em></div>
            <Status tone={c.escalation.level>=3?'danger':c.escalation.level>=2?'warn':'info'}>{c.escalation.label}</Status>
          </button>)}
          {!escalated.length&&<div className="queueClear">✓ No active escalation triggers.</div>}
        </div>
      </section>

      <section className="panel escalationSummary">
        <span className="sectionKicker">AI summary</span>
        <h2>{selectedCentre?.name||'Select a centre'}</h2>
        {selectedCentre&&<>
          <div className={`escalationHero level${selectedCentre.escalation.level}`}><span>Level {selectedCentre.escalation.level}</span><strong>{selectedCentre.escalation.label}</strong></div>
          <h3>Why this is escalated</h3>
          <ul>{selectedCentre.escalation.reasons.map(reason=><li key={reason}>{reason}</li>)}</ul>
          <h3>Recommended next step</h3>
          <p>{selectedCentre.escalation.level>=3?'Regional reviewer should inspect evidence, review case history and confirm whether repeated issues require ministry attention.':'Centre monitoring officer should review the open evidence-backed cases before the next scheduled cycle.'}</p>
          <div className="summaryActions"><Link href={`/centres/${selectedCentre.centre_id}/review`} className="primaryBtn">Review Cases</Link><Link href={`/reports?centre=${selectedCentre.centre_id}&period=30d`} className="secondaryBtn">Generate 30-day Report</Link></div>
        </>}
      </section>

      {selectedCentre&&<AssistantPanel centreId={selectedCentre.centre_id}/>}
    </div>
  </div>;
}
