'use client';

import {useEffect,useState} from 'react';
import Link from 'next/link';
import {ArrowRight,ClipboardCheck,FileDown,ShieldAlert} from 'lucide-react';
import {getEvidencePack,reportPdfUrl} from '../lib/api';
import type {EvidenceReviewPack} from '../lib/types';
import type {SceneId} from '../lib/demoMission';
import {caseHrefWithReturn} from '../lib/missionContinuity';

type Status='loading'|'loaded'|'error'|'none';
const accent='font-semibold text-[#2F597D]';
export default function OfficerProofJourney({
 caseId,centreId,normalControl=false,sceneId,step=0,
 caseLedgerState='ready',onRetryCaseLedger,
}:{
 caseId:string|null;centreId:string;normalControl?:boolean;
 sceneId?:SceneId;step?:number;
 caseLedgerState?:'loading'|'ready'|'unavailable';
 onRetryCaseLedger?:()=>void;
}){
 const [pack,setPack]=useState<EvidenceReviewPack|null>(null);
 const [state,setState]=useState<Status>('loading');
 const [retry,setRetry]=useState(0);
 useEffect(()=>{
  if(!caseId){setPack(null);setState('none');return;}
  let active=true;
  setPack(null);setState('loading');
  getEvidencePack(caseId)
   .then(data=>{
    if(!active)return;
    if(data?.case?.case_id!==caseId||data.case.centre_id!==centreId)
     throw Error('Mismatched centre/case evidence');
    setPack(data);setState('loaded');
   })
   .catch(()=>{if(active){setPack(null);setState('error');}});
  return()=>{active=false};
 },[caseId,centreId,retry]);

 const saved=pack?.case;
 const simulated=Boolean(saved?.details?.simulated)||Boolean(saved?.case_id?.startsWith('SIM-'));
 const sourceHash=saved?.details?.source_video_sha256;
 const sourceBound=typeof sourceHash==='string'&&/^[a-f0-9]{64}$/.test(sourceHash)&&!simulated;
 const retained=pack?.integrity?.retained_count||0;
 const digest=Boolean(pack?.integrity?.checks?.sha256_retained);
 const duplicate=pack?.integrity?.possible_duplicate_count||0;
 const history=pack?.review?.history?.length||0;
 const caseLink=caseId&&sceneId&&/^[A-Za-z0-9_-]{3,96}$/.test(caseId)
   ?caseHrefWithReturn(caseId,{scene:sceneId,step})
   :caseId?'/cases/'+encodeURIComponent(caseId):null;

 return <section className="mt-6 rounded-[20px] border border-[#DAE4F0] bg-white p-4 sm:p-5"
   aria-label="Officer evidence chain">
  <div className="flex flex-wrap items-center justify-between gap-2">
   <div><div className="text-[11px] font-bold uppercase tracking-widest text-[#7C94AC]">Saved officer record</div>
    <h3 className="mt-1 text-[16px] font-bold text-[#2D4B68]">Officer evidence chain</h3></div>
   <span className="rounded-full bg-[#F2F6FA] px-3 py-1 text-[10px] font-semibold text-[#5D738B]">
    {state==='loaded'?(simulated?'Controlled case':'Saved case'):'No new case created'}
   </span>
  </div>

  {state==='loading'&&<p role="status" className="mt-3 text-[11px] text-[#71869C]">Checking saved evidence and audit…</p>}
  {state==='error'&&<div role="alert" className="mt-3 text-[11px] text-[#9A6231]">
   Saved case evidence is unavailable. No case status or source relationship was assumed.
   <button type="button" onClick={()=>setRetry(n=>n+1)} className="kw-focus ml-2 font-bold underline">Retry record</button>
  </div>}
  {state==='none'&&caseLedgerState==='loading'&&<p role="status" className="mt-3 text-[12px] text-[#668098]">
    Checking whether the centre has a saved case…
  </p>}
  {state==='none'&&caseLedgerState==='unavailable'&&<div role="alert" className="mt-3 text-[12px] text-[#92631E]">
    Case records unavailable. The authored scenario can still be inspected, but no saved decision or audit is confirmed.
    {onRetryCaseLedger&&<button type="button" onClick={onRetryCaseLedger}
      className="kw-focus ml-2 font-bold underline">Retry case lookup</button>}
  </div>}
  {state==='none'&&caseLedgerState==='ready'&&<p className="mt-3 text-[12px] text-[#668098]">
   {normalControl?'Normal control: no exception case is required for this authored example.'
     :'No case has been linked to this source. Officer decision and audit are not implied.'}
  </p>}
  {state==='loaded'&&saved&&pack&&<>
   <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4" role="list" aria-label="Saved evidence checkpoints">
    <div role="listitem" className="rounded-xl bg-[#F6F9FC] p-3">
     <span className="text-[10px] text-[#7D91A7]">01 · Source</span>
     <p className={'mt-1 text-[12px] '+accent}>{sourceBound?'Video digest recorded':'Original video not linked'}</p>
     <p className="mt-1 text-[10px] leading-4 text-[#788CA2]">
      {simulated?'This seeded case is not derived from the procedural replay above.':
       sourceBound?'SHA exists; run and camera identity still need external verification.':
       'No verified matching video provenance attached to this case.'}
     </p>
    </div>
    <div role="listitem" className="rounded-xl bg-[#F6F9FC] p-3">
     <span className="text-[10px] text-[#7D91A7]">02 · Evidence</span>
     <p className={'mt-1 text-[12px] '+accent}>{retained} saved frame{retained===1?'':'s'}</p>
     <p className="mt-1 text-[10px] leading-4 text-[#788CA2]">
      {digest?('SHA recorded'+(duplicate?' · '+duplicate+' possible duplicate':'')+'.'):
        'Independent image integrity not established.'}
     </p>
    </div>
    <div role="listitem" className="rounded-xl bg-[#F6F9FC] p-3">
     <span className="text-[10px] text-[#7D91A7]">03 · Officer</span>
     <p className={'mt-1 text-[12px] '+accent}>{pack.review.status.replaceAll('_',' ')}</p>
     <p className="mt-1 text-[10px] leading-4 text-[#788CA2]">
      {history?(history+' saved audit event'+(history===1?'':'s')+'.'):'Awaiting officer decision; none implied.'}
     </p>
    </div>
    <div role="listitem" className="rounded-xl bg-[#F6F9FC] p-3">
     <span className="text-[10px] text-[#7D91A7]">04 · Report</span>
     <p className={'mt-1 text-[12px] '+accent}>Centre PDF ready to request</p>
     <p className="mt-1 text-[10px] leading-4 text-[#788CA2]">Saved record and review information, not government approval.</p>
    </div>
   </div>
   <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
    <span className="inline-flex items-center gap-1.5 text-[10px] text-[#7C8DA2]"><ShieldAlert size={13}/>
     {simulated?'Recorded case fixture; not independent camera evidence':'Officer review must verify context and source rights'}
    </span>
    <div className="flex flex-wrap gap-3">
     <Link href={caseLink||'/actions'}
      className="kw-focus inline-flex items-center gap-1 text-[11px] font-semibold text-[#275D91]">
      <ClipboardCheck size={13}/> Review saved case <ArrowRight size={13}/>
     </Link>
     <a href={reportPdfUrl(centreId)} target="_blank" rel="noreferrer"
      className="kw-focus inline-flex items-center gap-1 text-[11px] font-semibold text-[#275D91]">
      <FileDown size={13}/> Centre PDF
     </a>
    </div>
   </div>
  </>}
 </section>;
}
