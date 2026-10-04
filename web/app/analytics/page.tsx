'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { getCentres, getDashboard, getHistory } from '../lib/api';
import type { AnalysisRow, Centre } from '../lib/types';
import { Metric, PageHeader } from '../components/Ui';

export default function AnalyticsPage(){
  const [centres,setCentres]=useState<Centre[]>([]);
  const [history,setHistory]=useState<AnalysisRow[]>([]);
  const [cases,setCases]=useState<any[]>([]);

  useEffect(()=>{
    getCentres().then(async payload=>{
      setCentres(payload.centres);
      const histories=await Promise.all(payload.centres.map(c=>getHistory(c.centre_id,200).catch(()=>({rows:[]}))));
      setHistory(histories.flatMap(item=>item.rows));
    }).catch(()=>{});
    getDashboard().then(d=>setCases(d.pending_cases||[])).catch(()=>{});
  },[]);

  const totals=useMemo(()=>({
    compliant:centres.filter(c=>c.status==='compliant').length,
    incomplete:centres.filter(c=>c.status==='incomplete').length,
    pending:centres.reduce((sum,c)=>sum+c.pending_cases,0),
    escalated:centres.filter(c=>c.escalation.level>0).length,
  }),[centres]);
  const max=Math.max(1,...centres.map(c=>c.pending_cases));

  const trend=useMemo(()=>{
    const today=new Date();
    const buckets=Array.from({length:30},(_,index)=>{
      const date=new Date(today);
      date.setDate(today.getDate()-(29-index));
      const key=date.toISOString().slice(0,10);
      return {key,total:0,compliant:0};
    });
    const byKey=new Map(buckets.map(bucket=>[bucket.key,bucket]));
    for(const row of history){
      const key=String(row.created_at||'').slice(0,10);
      const bucket=byKey.get(key);
      if(!bucket) continue;
      bucket.total+=1;
      if(row.outcome==='compliant') bucket.compliant+=1;
    }
    return buckets;
  },[history]);

  const trendPoints=useMemo(()=>{
    const points=trend.flatMap((bucket,index)=>{
      if(!bucket.total) return [];
      const rate=bucket.compliant/bucket.total;
      const x=20+(index/(trend.length-1))*560;
      const y=200-(rate*150);
      return [x.toFixed(1)+','+y.toFixed(1)];
    });
    return points.join(' ');
  },[trend]);

  const issueMix=useMemo(()=>{
    const mix={attendance:0,infrastructure:0,practical:0,camera:0,evidence:0,other:0};
    for(const item of cases){
      const type=String(item.case_type||'');
      if(type==='attendance_discrepancy') mix.attendance+=1;
      else if(type==='infrastructure_compliance') mix.infrastructure+=1;
      else if(type.startsWith('practical_activity')) mix.practical+=1;
      else if(type==='camera_integrity') mix.camera+=1;
      else if((item.evidence||[]).some((e:any)=>e.duplicate_of)) mix.evidence+=1;
      else mix.other+=1;
    }
    return mix;
  },[cases]);

  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Portfolio analytics" title="Monitoring Analytics" subtitle="Network analytics are calculated from recorded verification history and open cases — no decorative demo trend is substituted for missing data."
      actions={<Link href="/reports" className="primaryBtn">Open Reports</Link>}/>
    <section className="metricGrid four">
      <Metric label="Compliant centres" value={totals.compliant} note="All required checkpoints complete" tone="good" icon="✓"/>
      <Metric label="Incomplete centres" value={totals.incomplete} note="Pending or blocked verification" icon="•"/>
      <Metric label="Pending cases" value={totals.pending} note="Across all centres" tone="warn" icon="!"/>
      <Metric label="Escalated centres" value={totals.escalated} note="Any active trigger" tone="danger" icon="▲"/>
    </section>

    <div className="analyticsGrid">
      <section className="panel trendPanel">
        <div className="panelHead"><div><span className="sectionKicker">Compliance trend</span><h2>Recorded 30-day analysis history</h2></div></div>
        {trendPoints
          ? <div className="lineChartMock">
              <svg viewBox="0 0 600 220" role="img" aria-label="30 day compliant analysis rate">
                <line x1="20" y1="200" x2="580" y2="200" stroke="currentColor" opacity=".12"/>
                <line x1="20" y1="125" x2="580" y2="125" stroke="currentColor" opacity=".08"/>
                <line x1="20" y1="50" x2="580" y2="50" stroke="currentColor" opacity=".08"/>
                <polyline points={trendPoints} fill="none" stroke="currentColor" strokeWidth="4" strokeLinejoin="round" strokeLinecap="round"/>
              </svg>
              <div className="chartAxis"><span>30 days ago</span><span>20 days</span><span>10 days</span><span>Today</span></div>
            </div>
          : <div className="calmState">No recorded analyses yet. The trend will appear after real verification runs are written to history.</div>}
      </section>

      <section className="panel barsPanel">
        <div className="panelHead"><div><span className="sectionKicker">Issues by centre</span><h2>Pending review concentration</h2></div></div>
        <div className="barList">{centres.map(c=><div className="barRow" key={c.centre_id}><span>{c.name}</span><i><b style={{width:(c.pending_cases?Math.max(4,(c.pending_cases/max)*100):0)+'%'}}></b></i><em>{c.pending_cases}</em></div>)}</div>
      </section>

      <section className="panel issueMixPanel">
        <div className="panelHead"><div><span className="sectionKicker">Issue mix</span><h2>Open evidence-backed signals</h2></div></div>
        <div className="issueCountList">
          <Issue label="Attendance" value={issueMix.attendance}/>
          <Issue label="Practical work" value={issueMix.practical}/>
          <Issue label="Infrastructure" value={issueMix.infrastructure}/>
          <Issue label="Camera integrity" value={issueMix.camera}/>
          <Issue label="Evidence integrity" value={issueMix.evidence}/>
          <Issue label="Other" value={issueMix.other}/>
        </div>
      </section>
    </div>
  </div>;
}

function Issue({label,value}:{label:string;value:number}){
  return <div className="issueCountRow"><span>{label}</span><b>{value}</b></div>;
}
