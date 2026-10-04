'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import { getHistory } from '../../../lib/api';
import type { AnalysisRow } from '../../../lib/types';
import { PageHeader, Status } from '../../../components/Ui';

export default function CentreHistory(){
  const {centreId}=useParams<{centreId:string}>();
  const id=String(centreId);
  const [rows,setRows]=useState<AnalysisRow[]>([]);
  const [period,setPeriod]=useState('30d');
  const [type,setType]=useState('all');
  const [startDate,setStartDate]=useState('');
  const [endDate,setEndDate]=useState('');
  useEffect(()=>{getHistory(id,200).then(r=>setRows(r.rows)).catch(()=>{});},[id]);

  const filtered=useMemo(()=>{
    const now=Date.now();
    const cutoff=period==='yesterday'
      ? now-48*60*60*1000
      : period==='30d'
        ? now-30*24*60*60*1000
        : now-7*24*60*60*1000;
    return rows.filter(row=>{
      const matchesType=type==='all'||row.analysis_type===type;
      const created=Date.parse(row.created_at);
      if(!Number.isFinite(created)) return matchesType;
      if(period==='custom'){
        if(!startDate||!endDate) return false;
        const start=Date.parse(startDate+'T00:00:00');
        const end=Date.parse(endDate+'T23:59:59.999');
        return matchesType&&created>=start&&created<=end;
      }
      if(period==='yesterday'){
        const oneDayAgo=now-24*60*60*1000;
        return matchesType&&created>=cutoff&&created<oneDayAgo;
      }
      return matchesType&&created>=cutoff;
    });
  },[rows,type,period,startDate,endDate]);

  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Selected Centre / History" title="Analysis History" subtitle="Review completed verification runs by time period, outcome and analysis type without opening raw footage."
      actions={<><select className="headerSelect" value={period} onChange={e=>setPeriod(e.target.value)}><option value="yesterday">Yesterday</option><option value="7d">Last 7 days</option><option value="30d">Last 30 days</option><option value="custom">Custom range</option></select><a href={`/reports?centre=${id}&period=${period}${period==='custom'&&startDate&&endDate?'&start_date='+startDate+'&end_date='+endDate:''}`} className="primaryBtn">Generate Report</a></>}/>

    {period==='custom'&&<div className="customRange panel">
      <label><span>From</span><input type="date" value={startDate} onChange={e=>setStartDate(e.target.value)}/></label>
      <label><span>To</span><input type="date" value={endDate} onChange={e=>setEndDate(e.target.value)}/></label>
      {(!startDate||!endDate)&&<span>Select both dates to view a custom range.</span>}
    </div>}
    <div className="historyLayout">
      <section className="panel historyTablePanel">
        <div className="filterBar compact"><select value={type} onChange={e=>setType(e.target.value)}><option value="all">All analysis types</option><option value="attendance">Attendance</option><option value="practical_work">Practical Work</option><option value="infrastructure">Infrastructure</option></select><span>{filtered.length} runs</span></div>
        <div className="dataTableWrap"><table className="dataTable"><thead><tr><th>Date & Time</th><th>Analysis</th><th>Status</th><th>Summary</th><th>Report</th></tr></thead><tbody>
          {filtered.map(row=><tr key={row.analysis_id}><td>{new Date(row.created_at).toLocaleString()}</td><td>{row.analysis_type.replace('_',' ')}</td><td><Status tone={row.outcome==='compliant'?'good':row.outcome==='blocked'?'danger':'warn'}>{row.outcome}</Status></td><td className="summaryCell">{row.summary}</td><td><a className="tableLink" href={`/reports?centre=${id}&period=${period}${period==='custom'&&startDate&&endDate?'&start_date='+startDate+'&end_date='+endDate:''}`}>View</a></td></tr>)}
        </tbody></table></div>
        {!filtered.length&&<div className="queueClear">No recorded analyses yet for this centre.</div>}
      </section>
      <AssistantPanel centreId={id}/>
    </div>
  </div>;
}
