'use client';
import {useEffect,useState} from 'react';
import type {PillarId,TrustScorecard} from '../lib/server/scorecard-report';
import {SECURE_PROXY} from '../lib/api';

const names:Record<PillarId,string>={
 attendance:'Attendance MAE / case false alerts',
 camera_trust:'Camera trust / abstention',
 equipment_count:'Equipment class counts',
 equipment_localization:'Equipment boxes (IoU 0.50)',
 practical_activity:'Apparent practical work',
 offline_transport:'Offline transmission',
};
const ids=Object.keys(names) as PillarId[];
function format(card:TrustScorecard['pillars'][PillarId]):string{
 if(card.state==='measured_loopback_fixture_only'&&card.metric){
  return Number(card.metric.request_body_bytes).toLocaleString('en-IN')+' B sent · '+Number(card.metric.delivered)+' delivered';
 }
 if(card.state==='candidate_measured_not_independently_qualified'&&card.metric){
  return 'TP '+card.metric.tp+' · FP '+card.metric.fp+' · FN '+card.metric.fn+' · review pending';
 }
 return 'NOT QUALIFIED';
}
export default function TrustScorecardPanel(){
 const [report,setReport]=useState<TrustScorecard|null>(null);
 const [loading,setLoading]=useState(true);
 const [retry,setRetry]=useState(0);
 useEffect(()=>{
  if(SECURE_PROXY)return;
  let alive=true;setLoading(true);setReport(null);
  fetch('/api/demo/trust-scorecard',{cache:'no-store'})
   .then(async r=>r.ok?await r.json() as TrustScorecard:null)
   .then(data=>{
    if(alive&&data?.schema==='KW_PROOF_OF_TRAINING_SCORECARD_V1'
      &&data.qualified===false&&data.status==='evidence_gates_reported_not_field_qualified')
      setReport(data);
   }).catch(()=>{if(alive)setReport(null)})
   .finally(()=>{if(alive)setLoading(false)});
  return()=>{alive=false};
 },[retry]);
 if(SECURE_PROXY)return null;
 return <section className="kw-os-card mt-5 px-5 py-5 sm:px-6"
   aria-label="Proof of Training qualification scorecard">
  <div className="flex flex-wrap items-center justify-between gap-3">
   <div><h2 className="text-[16px] font-bold text-[#263B57]">Evidence qualification</h2>
    <p className="mt-1 text-[11px] text-[#8290A5]">What can be measured independently — and what cannot</p>
   </div>
   <span className="rounded-full bg-[#FFF5E8] px-3 py-1 text-[10px] font-bold text-[#866029]">
     No field certification
   </span>
  </div>
  <div className="mt-4 grid gap-x-4 gap-y-2 sm:grid-cols-2">
   {ids.map(id=>{
    const metric=report?.pillars[id];
    return <div key={id} className="flex min-w-0 flex-col justify-between gap-1 rounded-xl border border-[#E5EDF4] bg-[#FAFCFE] px-4 py-3">
     <div className="text-[11px] font-semibold text-[#49627C]">{names[id]}</div>
     <div className="text-[12px] font-bold text-[#2D4E70]">{metric?format(metric):'NOT QUALIFIED'}</div>
     <div className="text-[10px] leading-4 text-[#8797A8]">
       {metric?.state==='measured_loopback_fixture_only'?'Measured local fixture; no field transport claim':
        metric?.state==='candidate_measured_not_independently_qualified'?'Model-to-label proposal, external audit pending':
         'No admitted independent reference'}
     </div>
    </div>;
   })}
  </div>
  {!loading&&!report&&<div className="mt-3 text-[10px] text-[#8290A2]" role="status">
    No private benchmark receipt loaded. The dashboard will not invent accuracy.
    <button onClick={()=>setRetry(n=>n+1)} type="button" className="kw-focus ml-2 font-bold text-[#285B8D] underline">Retry verification</button>
  </div>}
  {report&&<p className="mt-3 text-[10px] leading-4 text-[#7A8B9E]">
    Candidate model metrics are not independently qualified. A source SHA verifies identity, not ground truth, model execution or official centre authorization.
  </p>}
 </section>;
}
