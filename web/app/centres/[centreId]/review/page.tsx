'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import AssistantPanel from '../../../components/AssistantPanel';
import WorkflowStepper from '../../../components/WorkflowStepper';
import { API, getDashboard } from '../../../lib/api';
import type { CaseRecord } from '../../../lib/types';
import { PageHeader, Status } from '../../../components/Ui';

const tone=(severity:string)=>severity==='high'?'danger':severity==='medium'?'warn':'info';

export default function ReviewQueue(){
  const {centreId}=useParams<{centreId:string}>();
  const id=String(centreId);
  const [cases,setCases]=useState<CaseRecord[]>([]);
  const [history,setHistory]=useState<CaseRecord[]>([]);
  const [selectedId,setSelectedId]=useState('');
  const [note,setNote]=useState('');
  const [busy,setBusy]=useState(false);

  async function refresh(){
    const payload=await getDashboard(id);
    const pending=(payload.pending_cases||[]) as CaseRecord[];
    const resolved=(payload.resolved_case_history||[]) as CaseRecord[];
    setCases(pending);
    setHistory(resolved);
    setSelectedId(current=>current&&[...pending,...resolved].some(c=>c.case_id===current)?current:(pending[0]?.case_id||resolved[0]?.case_id||''));
  }

  useEffect(()=>{refresh().catch(()=>{});},[id]);
  const all=useMemo(()=>[...cases,...history],[cases,history]);
  const selected=all.find(c=>c.case_id===selectedId)||null;
  const resolved=selected?['confirmed','false_positive','resolved'].includes(selected.status):false;
  const activeReview=selected?['under_review','virtual_verification'].includes(selected.status):false;

  async function act(action:string){
    if(!selected) return;
    setBusy(true);
    try{
      const response=await fetch(\`\${API}/api/cases/\${selected.case_id}/review\`,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action,note:note.trim()||null}),
      });
      const body=await response.json();
      if(!response.ok) throw new Error(body.detail||'Could not update case');
      setNote('');
      await refresh();
    }catch(err:any){alert(err.message);}
    finally{setBusy(false);}
  }

  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Selected Centre / Human Review" title="Review Queue" subtitle="AI surfaces evidence. Officers inspect, record rationale, and make the final compliance decision." actions={<><Status tone="warn">{cases.length} pending</Status><Status tone="neutral">{history.length} resolved</Status></>}/>
    <WorkflowStepper centreId={id} states={{attendance:'complete',practical:'complete',infrastructure:'complete',review:cases.length?'attention':'complete'}}/>

    <div className="reviewLayout">
      <section className="caseListPanel">
        <div className="caseTabs"><button className="active">Pending ({cases.length})</button><button>Resolved ({history.length})</button></div>
        <div className="caseList">
          {cases.map(item=><button type="button" key={item.case_id} onClick={()=>setSelectedId(item.case_id)} className={selectedId===item.case_id?'caseListItem active':'caseListItem'}>
            <span className={\`caseBullet \${item.severity}\`}></span>
            <div><strong>{item.case_type.replaceAll('_',' ')}</strong><small>{item.summary}</small><em>{item.case_id}</em></div>
            <Status tone={tone(item.severity) as any}>{item.severity}</Status>
          </button>)}
          {!cases.length&&<div className="queueClear">✓ No pending cases for this centre.</div>}
          {!!history.length&&<div className="resolvedMini"><b>Resolved history</b>{history.slice(0,4).map(item=><button key={item.case_id} onClick={()=>setSelectedId(item.case_id)} className={selectedId===item.case_id?'resolvedRow active':'resolvedRow'}><span>{item.case_type.replaceAll('_',' ')}</span><small>{item.status.replaceAll('_',' ')}</small></button>)}</div>}
        </div>
      </section>

      <section className="caseDetailPanel">
        {!selected&&<div className="resultEmpty"><span>✓</span><b>No case selected</b><p>Pending review cases will appear here.</p></div>}
        {selected&&<>
          <div className="caseDetailHead">
            <div><span className="sectionKicker">Case {selected.case_id}</span><h2>{selected.case_type.replaceAll('_',' ')}</h2></div>
            <Status tone={resolved?'good':activeReview?'info':'warn'}>{selected.status.replaceAll('_',' ')}</Status>
          </div>

          <div className="casePillarBanner">
            <b>{pillar(selected.case_type)}</b><span>{selected.summary}</span>
          </div>

          {!!selected.evidence?.some(e=>e.duplicate_of)&&<div className="integritySignal">
            <span>◈</span><div><strong>Independent evidence-integrity signal</strong><p>Possible duplicate evidence matched a previous evidence record. Treat this separately from the compliance finding.</p></div>
          </div>}

          <div className="caseEvidenceGrid">
            <div className="evidencePreview">
              {selected.evidence?.[0]
                ? <img src={\`\${API}/evidence/\${selected.evidence[0].evidence_id}.jpg\`} alt={\`Evidence for \${selected.case_id}\`}/>
                : <div className="noEvidence">No retained evidence frame</div>}
            </div>
            <div className="evidenceFacts">
              <div><span>Centre</span><b>{selected.centre_id}</b></div>
              <div><span>Batch</span><b>{selected.batch_id}</b></div>
              <div><span>Severity</span><b>{selected.severity}</b></div>
              <div><span>Evidence</span><b>{selected.evidence?.length||0} record(s)</b></div>
            </div>
          </div>

          {!resolved&&<>
            <div className="reviewSteps">
              <div className={selected.evidence?.length?'done':''}><span>{selected.evidence?.length?'✓':'1'}</span><b>Inspect evidence</b></div>
              <div className={activeReview?'done':''}><span>{activeReview?'✓':'2'}</span><b>Enter review</b></div>
              <div className={note.trim()?'done':''}><span>{note.trim()?'✓':'3'}</span><b>Record rationale</b></div>
            </div>
            <textarea className="reviewNote" value={note} onChange={e=>setNote(e.target.value)} rows={4} placeholder="What did you verify, and why should this case be confirmed or marked false positive?"/>
            <div className="reviewButtonRow">
              <button className="secondaryBtn" disabled={busy||selected.status==='under_review'} onClick={()=>act('under_review')}>Start Review</button>
              <button className="secondaryBtn" disabled={busy||selected.status==='virtual_verification'} onClick={()=>act('virtual_verification')}>Virtual Verify</button>
              <button className="secondaryBtn dangerText" disabled={busy||!activeReview||!note.trim()} onClick={()=>act('false_positive')}>False Positive</button>
              <button className="primaryBtn" disabled={busy||!activeReview||!note.trim()} onClick={()=>act('confirmed')}>Confirm & Resolve</button>
            </div>
          </>}

          {!!selected.review_history?.length&&<div className="auditTrail"><h3>Decision History</h3>{selected.review_history.map((event,index)=><div className="auditTrailRow" key={index}><span></span><div><b>{event.from_status.replaceAll('_',' ')} → {event.to_status.replaceAll('_',' ')}</b><small>{new Date(event.timestamp).toLocaleString()} · {event.actor||'prototype officer'}</small>{event.note&&<p>{event.note}</p>}</div></div>)}</div>}
        </>}
      </section>

      <AssistantPanel centreId={id}/>
    </div>
  </div>;
}

function pillar(type:string){
  if(type==='attendance_discrepancy') return 'ATTENDANCE DISCREPANCY';
  if(type.startsWith('practical_activity')) return 'PRACTICAL-WORK AUTHORIZATION';
  if(type==='infrastructure_compliance') return 'INFRASTRUCTURE GAP';
  if(type==='camera_integrity') return 'CAMERA INTEGRITY';
  return 'COMPLIANCE REVIEW';
}
