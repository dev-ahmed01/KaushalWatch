'use client';

import { useMemo, useState } from 'react';
import { API } from '../lib/api';

type Evidence={
  evidence_id:string;
  created_at?:string;
  sha256?:string;
  perceptual_hash?:string;
  duplicate_of?:string|null;
  metadata?:Record<string,unknown>;
};

export default function EvidenceGallery({
  evidence,
  title='Evidence',
  compact=false,
}:{
  evidence:Evidence[];
  title?:string;
  compact?:boolean;
}){
  const [selected,setSelected]=useState(0);
  const current=evidence[selected]||evidence[0];
  const metadata=useMemo(()=>Object.entries(current?.metadata||{}).filter(([,value])=>value!==null&&value!==undefined),[current]);

  if(!current) return <div className="evidenceGallery empty"><span>□</span><b>No retained evidence</b><small>This case has no central evidence frame.</small></div>;

  return <section className={compact?'evidenceGallery compact':'evidenceGallery'}>
    <div className="evidenceGalleryHead">
      <div><span className="sectionKicker">{title}</span><b>{current.evidence_id}</b></div>
      <span className={current.duplicate_of?'evidenceIntegrity duplicate':'evidenceIntegrity'}>{current.duplicate_of?'Possible duplicate':'Unique evidence'}</span>
    </div>

    <div className="evidenceHero">
      <img src={API+'/evidence/'+current.evidence_id+'.jpg'} alt={'Retained evidence '+current.evidence_id}/>
      <div className="evidenceHeroMeta">
        <span>{current.created_at?new Date(current.created_at).toLocaleString():'Retained frame'}</span>
        {current.sha256&&<code title={current.sha256}>SHA-256 {current.sha256.slice(0,16)}…</code>}
      </div>
    </div>

    {evidence.length>1&&<div className="evidenceThumbs">
      {evidence.map((item,index)=><button type="button" key={item.evidence_id} onClick={()=>setSelected(index)} className={index===selected?'active':''}>
        <img src={API+'/evidence/'+item.evidence_id+'.jpg'} alt=""/>
        <span>{index+1}</span>
      </button>)}
    </div>}

    {!compact&&metadata.length>0&&<div className="evidenceMetadata">
      {metadata.slice(0,8).map(([key,value])=><div key={key}><span>{key.replaceAll('_',' ')}</span><b>{formatValue(value)}</b></div>)}
    </div>}
    {current.duplicate_of&&<div className="evidenceDuplicateNote">Possible duplicate of <b>{current.duplicate_of}</b>. Evidence integrity is reviewed separately from the compliance finding.</div>}
  </section>;
}

function formatValue(value:unknown){
  if(Array.isArray(value)) return value.join(', ');
  if(typeof value==='object') return JSON.stringify(value);
  return String(value);
}
