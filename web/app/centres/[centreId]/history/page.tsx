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
  useEffect(()=>{getHistory(id,200).then(r=>setRows(r.rows)).catch(()=>{});},[id]);

  const filtered=useMemo(()=>rows.filter(row=>type==='all'||row.analysis_type===type),[rows,type]);

  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Selected Centre / History" title="Analysis History" subtitle="Every recorded verification run for this centre, with outcome and report context."
      actions={<><select className="headerSelect" value={period} onChange={e=>setPeriod(e.target.value)}><option value="yesterday">Yesterday</option><option value="7d">Last 7 days</option><option value="30d">Last 30 days</option></select><a href={\`/reports?centre=\${id}&period=\${period}\`} className="primaryBtn">Generate Report</a></>}/>

    <div className="historyLayout">
      <section className="panel historyTablePanel">
        <div className="filterBar compact"><select value={type} onChange={e=>setType(e.target.value)}><option value="all">All analysis types</option><option value="attendance">Attendance</option><option value="practical_work">Practical Work</option><option value="infrastructure">Infrastructure</option></select><span>{filtered.length} runs</span></div>
        <div className="dataTableWrap"><table className="dataTable"><thead><tr><th>Date & Time</th><th>Analysis</th><th>Status</th><th>Summary</th><th>Report</th></tr></thead><tbody>
          {filtered.map(row=><tr key={row.analysis_id}><td>{new Date(row.created_at).toLocaleString()}</td><td>{row.analysis_type.replace('_',' ')}</td><td><Status tone={row.outcome==='compliant'?'good':row.outcome==='blocked'?'danger':'warn'}>{row.outcome}</Status></td><td className="summaryCell">{row.summary}</td><td><a className="tableLink" href={\`/reports?centre=\${id}&period=\${period}\`}>View</a></td></tr>)}
        </tbody></table></div>
        {!filtered.length&&<div className="queueClear">No recorded analyses yet for this centre.</div>}
      </section>
      <AssistantPanel centreId={id}/>
    </div>
  </div>;
}
