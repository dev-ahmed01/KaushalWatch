'use client';

import { useEffect, useMemo, useState } from 'react';
import AssistantPanel from '../components/AssistantPanel';
import { getCentres, reportPdfUrl, reportUrl } from '../lib/api';
import type { Centre } from '../lib/types';
import { Metric, PageHeader, Status } from '../components/Ui';

export default function ReportsPage(){
  const [centres,setCentres]=useState<Centre[]>([]);
  const [centreId,setCentreId]=useState('DEMO-KA-104');
  const [period,setPeriod]=useState('7d');
  const [startDate,setStartDate]=useState('');
  const [endDate,setEndDate]=useState('');
  const [report,setReport]=useState<any>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');

  useEffect(()=>{
    const params=new URLSearchParams(window.location.search);
    setCentreId(params.get('centre')||'DEMO-KA-104');
    setPeriod(params.get('period')||'7d');
    setStartDate(params.get('start_date')||'');
    setEndDate(params.get('end_date')||'');
    getCentres().then(r=>setCentres(r.centres)).catch(()=>{});
  },[]);

  const rangeReady=period!=='custom'||Boolean(startDate&&endDate);
  useEffect(()=>{
    if(rangeReady) generate().catch(()=>{});
  },[centreId,period,startDate,endDate,rangeReady]);

  async function generate(){
    setBusy(true);setError('');
    try{
      const response=await fetch(reportUrl(centreId,period,startDate||undefined,endDate||undefined),{cache:'no-store'});
      const body=await response.json();
      if(!response.ok) throw new Error(body.detail||'Report unavailable');
      setReport(body);
    }catch(err:any){
      setError(err.message||'Report unavailable');
      setReport(null);
    }finally{setBusy(false);}
  }

  const analyses=report?.analyses||[];
  const compliant=analyses.filter((r:any)=>r.outcome==='compliant').length;
  const attention=analyses.filter((r:any)=>r.outcome==='attention').length;
  const blocked=analyses.filter((r:any)=>r.outcome==='blocked').length;
  const pdfHref=useMemo(()=>reportPdfUrl(centreId,period,startDate||undefined,endDate||undefined),[centreId,period,startDate,endDate]);

  return <div className="pageScene fadeIn">
    <PageHeader
      eyebrow="Reports & analytics"
      title="Compliance Reports"
      subtitle="Generate an auditable centre report from recorded analyses, cases and verification state."
      actions={<>
        <button className={period==='today'?'periodBtn active':'periodBtn'} onClick={()=>setPeriod('today')}>Today</button>
        <button className={period==='yesterday'?'periodBtn active':'periodBtn'} onClick={()=>setPeriod('yesterday')}>Yesterday</button>
        <button className={period==='7d'?'periodBtn active':'periodBtn'} onClick={()=>setPeriod('7d')}>Last 7 days</button>
        <button className={period==='30d'?'periodBtn active':'periodBtn'} onClick={()=>setPeriod('30d')}>Last 30 days</button>
        <button className={period==='custom'?'periodBtn active':'periodBtn'} onClick={()=>setPeriod('custom')}>Custom Range</button>
        <a className={rangeReady?'primaryBtn':'primaryBtn disabled'} href={rangeReady?pdfHref:undefined}>Download PDF</a>
      </>}
    />

    <div className="reportFilterRow">
      <select value={centreId} onChange={e=>setCentreId(e.target.value)}>{centres.map(c=><option key={c.centre_id} value={c.centre_id}>{c.name}</option>)}</select>
      <span>{busy?'Refreshing report…':error?'Report unavailable':'Report ready'}</span>
      <button className="secondaryBtn" type="button" onClick={()=>window.print()}>Print</button>
    </div>

    {period==='custom'&&<div className="customRange panel">
      <label><span>From</span><input type="date" value={startDate} onChange={e=>setStartDate(e.target.value)}/></label>
      <label><span>To</span><input type="date" value={endDate} onChange={e=>setEndDate(e.target.value)}/></label>
      {!rangeReady&&<span>Select both dates to generate the report.</span>}
    </div>}
    {error&&<div className="inlineError">{error}</div>}

    <section className="metricGrid four">
      <Metric label="Analysis runs" value={analyses.length} note={report?.period_label||periodLabel(period)} icon="▣"/>
      <Metric label="Compliant runs" value={compliant} note="Authoritative checks without exception" tone="good" icon="✓"/>
      <Metric label="Need attention" value={attention} note="Evidence-backed exception" tone="warn" icon="!"/>
      <Metric label="Blocked runs" value={blocked} note="No authoritative conclusion" tone={blocked?'danger':'default'} icon="×"/>
    </section>

    <div className="reportLayout">
      <section className="panel printableReport">
        <div className="reportMasthead">
          <div><span>KAUSHALWATCH</span><h2>Centre Verification Report</h2><p>{report?.centre?.name||centreId} · {report?.period_label||periodLabel(period)}</p></div>
          <Status tone={report?.summary?.pending_cases?'warn':report?.centre?.status==='compliant'?'good':'neutral'}>
            {report?.summary?.pending_cases?'Review required':report?.centre?.status==='compliant'?'Compliant':'Verification incomplete'}
          </Status>
        </div>
        <div className="reportExecutive">
          <span className="sectionKicker">Executive summary</span>
          <p>{report?.summary?.pending_cases
            ? report.summary.pending_cases+' pending case(s) require human attention. Current escalation: '+report.summary.escalation?.label+'.'
            : report?.centre?.status==='compliant'
              ? 'All required checkpoints in the current centre state have completed without an unresolved compliance exception.'
              : 'No unresolved case is open, but one or more verification checkpoints are pending or blocked. No compliant centre-level conclusion is claimed.'}</p>
        </div>
        <div className="reportSection"><h3>Current verification state</h3>
          <div className="reportRows">
            {[
              ['Attendance',report?.centre?.attendance_status],
              ['Practical Work',report?.centre?.practical_status],
              ['Infrastructure',report?.centre?.infrastructure_status],
              ['Camera Integrity',report?.centre?.camera_status],
              ['Evidence Integrity',report?.centre?.evidence_integrity_status],
            ].map(([label,value])=><div className="reportRow" key={label as string}><b>{label}</b><Status tone={stateTone(String(value||'pending')) as any}>{String(value||'pending').replaceAll('_',' ')}</Status><p></p><span></span></div>)}
          </div>
        </div>
        <div className="reportSection"><h3>Recent analyses</h3>
          <div className="reportRows">{analyses.slice(0,12).map((row:any)=><div className="reportRow" key={row.analysis_id}><span>{new Date(row.created_at).toLocaleDateString()}</span><b>{row.analysis_type.replace('_',' ')}</b><Status tone={row.outcome==='compliant'?'good':row.outcome==='blocked'?'danger':'warn'}>{row.outcome}</Status><p>{row.summary}</p></div>)}</div>
          {!analyses.length&&<div className="calmState">No analyses fall inside the selected period.</div>}
        </div>
        <div className="reportSection"><h3>Privacy & limitations</h3><p>{report?.privacy_note}</p><ul>{(report?.limitations||[]).map((x:string)=><li key={x}>{x}</li>)}</ul></div>
      </section>
      <AssistantPanel centreId={centreId}/>
    </div>
  </div>;
}

function stateTone(state:string){
  if(['compliant','nominal','clear'].includes(state)) return 'good';
  if(state==='blocked') return 'danger';
  if(state==='pending') return 'neutral';
  return 'warn';
}

function periodLabel(period:string){
  if(period==='today') return 'Today';
  if(period==='yesterday') return 'Yesterday';
  if(period==='30d') return 'Last 30 days';
  if(period==='custom') return 'Custom range';
  return 'Last 7 days';
}
