'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { getCentres } from './lib/api';
import type { Centre } from './lib/types';
import { Metric, PageHeader, Skeleton, Status } from './components/Ui';

const statusTone=(status:string)=>status==='compliant'?'good':status==='high_priority'?'danger':'warn';

export default function NetworkOverview(){
  const [centres,setCentres]=useState<Centre[]>([]);
  const [error,setError]=useState('');
  useEffect(()=>{getCentres().then(r=>setCentres(r.centres)).catch(e=>setError(e.message));},[]);

  const stats=useMemo(()=>{
    const compliant=centres.filter(c=>c.status==='compliant').length;
    const review=centres.filter(c=>c.status==='attention').length;
    const high=centres.filter(c=>c.status==='high_priority').length;
    return {total:centres.length,compliant,review,high};
  },[centres]);

  return <div className="pageScene fadeIn">
    <PageHeader
      eyebrow="Network command centre"
      title="Training Centre Network"
      subtitle="Monitor distributed training centres, surface exceptions, and drill into one centre without reviewing hours of raw footage."
      actions={<><Link href="/reports" className="secondaryBtn">Recent Reports</Link><Link href="/centres/DEMO-KA-104" className="primaryBtn">Open Bengaluru TC-04 →</Link></>}
    />
    {error&&<div className="inlineError">{error}</div>}

    <section className="metricGrid four">
      <Metric label="Total Centres" value={stats.total||'—'} note="Demo network" icon="▣"/>
      <Metric label="Compliant Centres" value={stats.compliant} note="No active exception" tone="good" icon="✓"/>
      <Metric label="Need Review" value={stats.review} note="Pending officer action" tone="warn" icon="!"/>
      <Metric label="High Priority" value={stats.high} note="Escalated pattern" tone="danger" icon="▲"/>
    </section>

    <section className="networkHeroGrid">
      <div className="panel networkMapPanel">
        <div className="panelHead"><div><span className="sectionKicker">Network pulse</span><h2>Karnataka demo network</h2></div><Status tone="good">Live summaries</Status></div>
        <div className="networkCanvas" aria-label="Stylised network map">
          <div className="mapWash"></div>
          {centres.map((centre,index)=><Link
            key={centre.centre_id}
            href={`/centres/${centre.centre_id}`}
            className={`mapNode ${centre.status}`}
            style={{left:`${18+(index*13)%68}%`,top:`${22+(index*17)%56}%`}}
            title={centre.name}
          ><span></span><b>{centre.name.replace(' TC-',' ')}</b></Link>)}
          {!centres.length&&<Skeleton lines={5}/>}
        </div>
      </div>

      <div className="panel attentionPanel">
        <div className="panelHead"><div><span className="sectionKicker">Escalation summary</span><h2>What needs attention</h2></div><Link href="/escalations">Open all →</Link></div>
        <div className="attentionList">
          {centres.filter(c=>c.escalation.level>0).slice(0,5).map(c=><Link href={`/centres/${c.centre_id}`} key={c.centre_id} className="attentionRow">
            <span className={`attentionDot level${c.escalation.level}`}></span>
            <div><strong>{c.name}</strong><small>{c.escalation.reasons[0]}</small></div>
            <Status tone={statusTone(c.status) as any}>{c.escalation.label}</Status>
          </Link>)}
          {!!centres.length&&!centres.some(c=>c.escalation.level>0)&&<div className="calmState">✓ No active escalation triggers</div>}
        </div>
      </div>
    </section>

    <section className="panel centresTablePanel">
      <div className="panelHead"><div><span className="sectionKicker">All centres</span><h2>Operational status</h2></div><Link href="/centres">View directory →</Link></div>
      <div className="dataTableWrap">
        <table className="dataTable">
          <thead><tr><th>Centre</th><th>Location</th><th>Batch</th><th>Attendance</th><th>Practical</th><th>Infrastructure</th><th>Exceptions</th><th>Status</th></tr></thead>
          <tbody>{centres.map(c=><tr key={c.centre_id}>
            <td><Link className="tableLink" href={`/centres/${c.centre_id}`}>{c.name}</Link></td>
            <td>{c.district}</td><td>{c.batch_id}</td>
            <td><Status tone={c.attendance_status==='compliant'?'good':'warn'}>{c.attendance_status}</Status></td>
            <td><Status tone={c.practical_status==='compliant'?'good':'warn'}>{c.practical_status}</Status></td>
            <td><Status tone={c.infrastructure_status==='compliant'?'good':'warn'}>{c.infrastructure_status}</Status></td>
            <td>{c.pending_cases}</td>
            <td><Status tone={statusTone(c.status) as any}>{c.status.replace('_',' ')}</Status></td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>
  </div>;
}
