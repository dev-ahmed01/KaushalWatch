'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { getCentres } from './lib/api';
import type { Centre } from './lib/types';
import { Metric, PageHeader, Skeleton, Status } from './components/Ui';

const statusTone=(status:string)=>status==='compliant'?'good':status==='high_priority'?'danger':status==='incomplete'?'neutral':'warn';
const pillarTone=(status:string)=>['compliant','nominal','clear'].includes(status)?'good':status==='blocked'?'danger':status==='pending'?'neutral':'warn';

const MAP_POSITIONS:Record<string,{left:string;top:string}> = {
  'DEMO-KA-104':{left:'68%',top:'78%'},
  'DEMO-KA-112':{left:'46%',top:'78%'},
  'DEMO-KA-207':{left:'57%',top:'61%'},
  'DEMO-KA-303':{left:'41%',top:'31%'},
  'DEMO-KA-509':{left:'27%',top:'18%'},
  'DEMO-KA-601':{left:'21%',top:'65%'},
};

export default function NetworkOverview(){
  const [centres,setCentres]=useState<Centre[]>([]);
  const [error,setError]=useState('');
  const [filter,setFilter]=useState<'all'|'review'|'camera'|'incomplete'>('all');
  useEffect(()=>{getCentres().then(r=>setCentres(r.centres)).catch(e=>setError(e.message));},[]);

  const stats=useMemo(()=>{
    const compliant=centres.filter(c=>c.status==='compliant').length;
    const review=centres.filter(c=>c.status==='attention').length;
    const high=centres.filter(c=>c.status==='high_priority').length;
    return {total:centres.length,compliant,review,high};
  },[centres]);

  const filtered=useMemo(()=>{
    if(filter==='review') return centres.filter(c=>c.status!=='compliant');
    if(filter==='camera') return centres.filter(c=>c.camera_status!=='nominal');
    if(filter==='incomplete') return centres.filter(c=>c.status==='incomplete'||[c.attendance_status,c.practical_status,c.infrastructure_status].some(state=>['blocked','pending'].includes(String(state))));
    return centres;
  },[centres,filter]);

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
        <div className="networkCanvas" aria-label="Stylised Karnataka training-centre network map">
          <div className="mapWash"></div>
          <svg className="networkSilhouette" viewBox="0 0 500 360" aria-hidden="true">
            <path d="M156 24 L238 35 L289 63 L315 103 L353 124 L340 166 L371 208 L350 254 L316 276 L296 328 L242 338 L198 310 L169 275 L132 252 L112 211 L128 169 L106 131 L123 89 Z"/>
            <path className="networkRoute" d="M135 68 C190 110 220 160 287 280"/>
            <path className="networkRoute" d="M150 238 C215 213 246 190 300 280"/>
            <path className="networkRoute" d="M195 112 C218 160 225 205 223 278"/>
          </svg>
          <div className="networkMapLabel"><b>Karnataka</b><span>Operational topology · stylised, not survey geometry</span></div>
          {centres.map(centre=><Link
            key={centre.centre_id}
            href={`/centres/${centre.centre_id}`}
            className={`mapNode ${centre.status}`}
            style={MAP_POSITIONS[centre.centre_id]||{left:'50%',top:'50%'}}
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
      <div className="networkFilterTabs">
        <button className={filter==='all'?'active':''} onClick={()=>setFilter('all')}>All Centres <span>{centres.length}</span></button>
        <button className={filter==='review'?'active':''} onClick={()=>setFilter('review')}>Requires Review <span>{centres.filter(c=>c.status!=='compliant').length}</span></button>
        <button className={filter==='camera'?'active':''} onClick={()=>setFilter('camera')}>Camera Issues <span>{centres.filter(c=>c.camera_status!=='nominal').length}</span></button>
        <button className={filter==='incomplete'?'active':''} onClick={()=>setFilter('incomplete')}>Verification Incomplete <span>{centres.filter(c=>c.status==='incomplete').length}</span></button>
      </div>
      <div className="panelHead"><div><span className="sectionKicker">Centre directory</span><h2>Operational status</h2></div><Link href="/centres">View directory →</Link></div>
      <div className="dataTableWrap">
        <table className="dataTable">
          <thead><tr><th>Centre</th><th>Location</th><th>Batch</th><th>Attendance</th><th>Practical</th><th>Infrastructure</th><th>Exceptions</th><th>Status</th></tr></thead>
          <tbody>{filtered.map(c=><tr key={c.centre_id}>
            <td><Link className="tableLink" href={`/centres/${c.centre_id}`}>{c.name}</Link></td>
            <td>{c.district}</td><td>{c.batch_id}</td>
            <td><Status tone={pillarTone(c.attendance_status) as any}>{c.attendance_status}</Status></td>
            <td><Status tone={pillarTone(c.practical_status) as any}>{c.practical_status}</Status></td>
            <td><Status tone={pillarTone(c.infrastructure_status) as any}>{c.infrastructure_status}</Status></td>
            <td>{c.pending_cases}</td>
            <td><Status tone={statusTone(c.status) as any}>{c.status.replace('_',' ')}</Status></td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>
  </div>;
}
