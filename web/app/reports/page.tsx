'use client';

import { useEffect, useState } from 'react';
import AssistantPanel from '../components/AssistantPanel';
import { API, getCentres } from '../lib/api';
import type { Centre } from '../lib/types';
import { Metric, PageHeader, Status } from '../components/Ui';

export default function ReportsPage(){
  const [centres,setCentres]=useState<Centre[]>([]);
  const [centreId,setCentreId]=useState('DEMO-KA-104');
  const [period,setPeriod]=useState('7d');
  const [report,setReport]=useState<any>(null);
  const [busy,setBusy]=useState(false);

  useEffect(()=>{
    const params=new URLSearchParams(window.location.search);
    setCentreId(params.get('centre')||'DEMO-KA-104');
    setPeriod(params.get('period')||'7d');
    getCentres().then(r=>setCentres(r.centres)).catch(()=>{});
  },[]);
  useEffect(()=>{generate().catch(()=>{});},[centreId,period]);

  async function generate(){
    setBusy(true);
    try{
      const response=await fetch(`${API}/api/centres/${encodeURIComponent(centreId)}/report?period=${period}`,{cache:'no-store'});
      const body=await response.json();
      if(!response.ok) throw new Error(body.detail||'Report unavailable');
      setReport(body);
    }finally{setBusy(false);}
  }

  const analyses=report?.analyses||[];
  const compliant=analyses.filter((r:any)=>r.outcome==='compliant').length;
  const attention=analyses.filter((r:any)=>r.outcome==='attention').length;

  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Reports & analytics" title="Compliance Reports" subtitle="Review yesterday, the last week, the last month, or a selected centre’s audit trail."
      actions={<><button className={period==='yesterday'?'periodBtn active':'periodBtn'} onClick={()=>setPeriod('yesterday')}>Yesterday</button><button className={period==='7d'?'periodBtn active':'periodBtn'} onClick={()=>setPeriod('7d')}>Last 7 days</button><button className={period==='30d'?'periodBtn active':'periodBtn'} onClick={()=>setPeriod('30d')}>Last 30 days</button><button className="primaryBtn" onClick={()=>window.print()}>Generate / Print Report</button></>}/>

    <div className="reportFilterRow"><select value={centreId} onChange={e=>setCentreId(e.target.value)}>{centres.map(c=><option key={c.centre_id} value={c.centre_id}>{c.name}</option>)}</select><span>{busy?'Refreshing report…':'Report ready'}</span></div>

    <section className="metricGrid four">
      <Metric label="Analysis runs" value={analyses.length} note={periodLabel(period)} icon="▣"/>
      <Metric label="Compliant runs" value={compliant} note="No exception created" tone="good" icon="✓"/>
      <Metric label="Need attention" value={attention} note="Evidence-backed exception" tone="warn" icon="!"/>
      <Metric label="Pending cases" value={report?.summary?.pending_cases??0} note={report?.summary?.escalation?.label||'Normal'} tone={(report?.summary?.pending_cases??0)>0?'warn':'good'} icon="▲"/>
    </section>

    <div className="reportLayout">
      <section className="panel printableReport">
        <div className="reportMasthead"><div><span>KAUSHALWATCH</span><h2>Centre Verification Report</h2><p>{report?.centre?.name||centreId} · {periodLabel(period)}</p></div><Status tone={report?.summary?.pending_cases?'warn':'good'}>{report?.summary?.pending_cases?'Review required':'No pending exception'}</Status></div>
        <div className="reportExecutive">
          <span className="sectionKicker">Executive summary</span>
          <p>{report?.summary?.pending_cases
            ? `${report.summary.pending_cases} pending case(s) require human attention. Current escalation: ${report.summary.escalation?.label}.`
            : 'No pending compliance exception is recorded for this centre in the current review state.'}</p>
        </div>
        <div className="reportSection"><h3>Recent analyses</h3>
          <div className="reportRows">{analyses.slice(0,12).map((row:any)=><div className="reportRow" key={row.analysis_id}><span>{new Date(row.created_at).toLocaleDateString()}</span><b>{row.analysis_type.replace('_',' ')}</b><Status tone={row.outcome==='compliant'?'good':row.outcome==='blocked'?'danger':'warn'}>{row.outcome}</Status><p>{row.summary}</p></div>)}</div>
        </div>
        <div className="reportSection"><h3>Privacy & limitations</h3><p>{report?.privacy_note}</p><ul>{(report?.limitations||[]).map((x:string)=><li key={x}>{x}</li>)}</ul></div>
      </section>
      <AssistantPanel centreId={centreId}/>
    </div>
  </div>;
}

function periodLabel(period:string){
  if(period==='yesterday') return 'Yesterday';
  if(period==='30d') return 'Last 30 days';
  return 'Last 7 days';
}
