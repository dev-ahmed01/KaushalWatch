'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { getCentres } from '../lib/api';
import type { Centre } from '../lib/types';
import { PageHeader, Status } from '../components/Ui';

export default function CentresPage(){
  const [rows,setRows]=useState<Centre[]>([]);
  const [query,setQuery]=useState('');
  const [status,setStatus]=useState('all');
  useEffect(()=>{getCentres().then(r=>setRows(r.centres)).catch(()=>{});},[]);
  const filtered=useMemo(()=>rows.filter(c=>{
    const q=query.toLowerCase();
    return (!q||c.name.toLowerCase().includes(q)||c.district.toLowerCase().includes(q)||c.batch_id.toLowerCase().includes(q))
      &&(status==='all'||c.status===status);
  }),[rows,query,status]);

  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Centre directory" title="Training Centres" subtitle="Search, filter and open any centre without leaving the monitoring workspace."/>
    <div className="filterBar">
      <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search centre, district or batch…" />
      <select value={status} onChange={e=>setStatus(e.target.value)}>
        <option value="all">All statuses</option><option value="compliant">Compliant</option><option value="attention">Needs review</option><option value="high_priority">High priority</option>
      </select>
      <span>{filtered.length} centres</span>
    </div>
    <div className="centreCardGrid">
      {filtered.map(c=><Link href={`/centres/${c.centre_id}`} className="centreCard" key={c.centre_id}>
        <div className="centreCardVisual"><span>TC</span><div className={`pulseRing ${c.status}`}></div></div>
        <div className="centreCardBody">
          <div className="centreCardTitle"><div><strong>{c.name}</strong><small>{c.location}</small></div><Status tone={c.status==='compliant'?'good':c.status==='high_priority'?'danger':'warn'}>{c.status.replace('_',' ')}</Status></div>
          <div className="centreMeta"><span>{c.batch_id}</span><span>{c.trainees} trainees</span><span>{c.connectivity_mode.replace('_',' ')}</span></div>
          <div className="miniChecks"><span className={c.attendance_status}>Attendance</span><span className={c.practical_status}>Practical</span><span className={c.infrastructure_status}>Infrastructure</span></div>
          <div className="centreEscalation"><b>{c.escalation.label}</b><small>{c.escalation.reasons[0]}</small></div>
        </div>
      </Link>)}
    </div>
  </div>;
}
