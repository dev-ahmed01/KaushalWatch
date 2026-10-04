'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { getCentres } from '../lib/api';
import type { Centre } from '../lib/types';
import { Metric, PageHeader } from '../components/Ui';

export default function AnalyticsPage(){
  const [centres,setCentres]=useState<Centre[]>([]);
  useEffect(()=>{getCentres().then(r=>setCentres(r.centres)).catch(()=>{});},[]);
  const totals=useMemo(()=>({
    compliant:centres.filter(c=>c.status==='compliant').length,
    pending:centres.reduce((sum,c)=>sum+c.pending_cases,0),
    escalated:centres.filter(c=>c.escalation.level>0).length,
    camera:centres.filter(c=>c.camera_status!=='nominal').length,
  }),[centres]);
  const max=Math.max(1,...centres.map(c=>c.pending_cases));

  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Portfolio analytics" title="Monitoring Analytics" subtitle="A simple network-level picture of compliance, exceptions and escalation concentration."
      actions={<Link href="/reports" className="primaryBtn">Generate Network Report</Link>}/>
    <section className="metricGrid four">
      <Metric label="Compliant centres" value={totals.compliant} note="Current demo state" tone="good" icon="✓"/>
      <Metric label="Pending cases" value={totals.pending} note="Across all centres" tone="warn" icon="!"/>
      <Metric label="Escalated centres" value={totals.escalated} note="Any active trigger" icon="▲"/>
      <Metric label="Camera issues" value={totals.camera} note="Open integrity signal" icon="◉"/>
    </section>

    <div className="analyticsGrid">
      <section className="panel trendPanel"><div className="panelHead"><div><span className="sectionKicker">Compliance trend</span><h2>30-day demo trend</h2></div></div><div className="lineChartMock"><svg viewBox="0 0 600 220"><path d="M20 170 C90 150 110 165 170 120 S270 105 320 125 S420 70 480 85 S540 60 580 52" fill="none" stroke="currentColor" strokeWidth="4"/><path d="M20 170 C90 150 110 165 170 120 S270 105 320 125 S420 70 480 85 S540 60 580 52 L580 210 L20 210Z" fill="currentColor" opacity=".08"/></svg><div className="chartAxis"><span>Week 1</span><span>Week 2</span><span>Week 3</span><span>Today</span></div></div></section>
      <section className="panel barsPanel"><div className="panelHead"><div><span className="sectionKicker">Issues by centre</span><h2>Pending review concentration</h2></div></div><div className="barList">{centres.map(c=><div className="barRow" key={c.centre_id}><span>{c.name}</span><i><b style={{width:\`\${Math.max(4,(c.pending_cases/max)*100)}%\`}}></b></i><em>{c.pending_cases}</em></div>)}</div></section>
      <section className="panel issueMixPanel"><div className="panelHead"><div><span className="sectionKicker">Issue mix</span><h2>Independent signals</h2></div></div><div className="donutMock"><div className="donut"></div><div><span><i className="blue"></i>Attendance</span><span><i className="orange"></i>Infrastructure</span><span><i className="purple"></i>Evidence integrity</span><span><i className="red"></i>Camera integrity</span></div></div></section>
    </div>
  </div>;
}
