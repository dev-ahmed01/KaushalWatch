'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {ArrowRight,CameraOff,CheckCircle2,ClipboardCheck,Eye,EyeOff,ShieldAlert,ToolCase} from 'lucide-react';
import type {TradeItem,TradeProof} from '../lib/server/trade-proof';

const badge=(active:boolean)=>active
 ? 'border-[#A6C5E6] bg-[#ECF5FE] text-[#2B6194]'
 : 'border-[#E2E9F1] bg-white text-[#70829A]';

function stateLabel(item:TradeItem,unusable:boolean):string{
 if(unusable)return 'Observation withheld';
 if(item.example_state==='manual_officer_check')return 'Officer verification';
 if(item.example_state==='no_samples')return 'No example available';
 if(item.example_state==='illustrative_gap')return 'Example visibility gap';
 return 'Example counts align';
}
function detail(item:TradeItem,unusable:boolean):string{
 if(unusable)return 'Camera quality is marked unusable for this demonstration. Equipment count is unknown, never zero.';
 if(item.verification_tier==='officer_verification_required')return 'Small or occluded items need direct authorised inspection. The example does not infer that a multimeter is absent.';
 if(item.example_state==='illustrative_gap')return 'The example shows fewer visible items than the simulated requirement. This is a review question, not evidence that physical stock is missing.';
 if(item.id==='drill_machine')return 'Example visibility does not establish electrical safety, functional operability or actual use.';
 return 'The example counts align across the three authored samples. This is not independently measured model accuracy or proof of operational compliance.';
}
export default function TradeProofPanel(){
 const [proof,setProof]=useState<TradeProof|null>(null);
 const [state,setState]=useState<'loading'|'ready'|'error'>('loading');
 const [retry,setRetry]=useState(0);
 const [sample,setSample]=useState(10);
 const [selection,setSelection]=useState('training_panel');
 const [blocked,setBlocked]=useState(false);
 useEffect(()=>{
   let active=true;
   setState('loading');
   fetch('/api/demo/trade-proof',{cache:'no-store'})
    .then(async r=>{
      if(!r.ok)throw new Error('Trade example unavailable');
      return await r.json() as TradeProof;
    })
    .then(data=>{
      if(!active)return;
      if(data.schema!=='KW_CONTROLLED_TRADE_PROOF_V1'
        ||data.status!=='illustrative_only'||!data.counts_are_simulated
        ||data.model_run_verified!==false||data.video_source_sha256!==null
        ||data.independent_per_class_tp_fp_fn!==null)throw new Error('Untrusted trade example');
      setProof(data);setState('ready');
    })
    .catch(()=>{if(active){setProof(null);setState('error');}});
   return()=>{active=false;};
 },[retry]);
 const item=proof?.items.find(x=>x.id===selection)||proof?.items[0];
 const inspected=blocked?null:item?.sample_counts.find(x=>x.second===sample);
 return <section className="mt-6 min-w-0 rounded-[20px] border border-[#C9DDED] bg-[#F8FBFE] p-4 sm:p-5"
   aria-label="Trade equipment proof">
   <div className="flex flex-wrap items-start justify-between gap-3">
    <div>
      <p className="text-[11px] font-bold uppercase tracking-[.13em] text-[#6A87A5]">Phase 3 · Role-specific check</p>
      <h3 className="mt-1 text-[17px] font-bold text-[#294763]">Equipment proof matrix</h3>
      <p className="mt-1 text-[11px] text-[#607A94]">Construction Electrician–LV · CON/Q0603</p>
    </div>
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[#E4D3B0] bg-[#FFF7E8] px-3 py-1.5 text-[11px] font-semibold text-[#8B6227]">
      <ShieldAlert size={13}/> Quantities are simulated
    </span>
   </div>
   {state==='error'&&<div role="alert" className="mt-4 rounded-lg border border-[#E9D5B8] bg-white p-3 text-[12px] text-[#906124]">
      Trade example unavailable; no requirement or observation is inferred.
      <button type="button" onClick={()=>setRetry(n=>n+1)} className="kw-focus ml-2 font-bold underline">Retry</button>
   </div>}
   {state==='loading'&&<p role="status" className="mt-4 text-[12px] text-[#6D849E]">Verifying role and example samples…</p>}
   {state==='ready'&&proof&&item&&<>
     <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
       <div className="flex flex-wrap gap-2" aria-label="Example time samples">
         {proof.sampling_seconds.map(second=><button key={second} type="button"
           aria-pressed={sample===second} onClick={()=>setSample(second)}
           className={'kw-focus rounded-lg border px-3 py-1.5 text-[11px] font-semibold '+badge(sample===second)}>
           {String(second).padStart(2,'0')}s
         </button>)}
       </div>
       <button type="button" aria-pressed={blocked} onClick={()=>setBlocked(v=>!v)}
         className={'kw-focus inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-[11px] font-semibold '+(blocked
           ? 'border-[#D8B58A] bg-[#FFF3E4] text-[#87541D]'
           : 'border-[#DCE7F2] bg-white text-[#536D89]')}>
         {blocked?<EyeOff size={14}/>:<Eye size={14}/>}
         {blocked?'Camera blocked · example':'Illustrate camera blocked'}
       </button>
     </div>
     <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(230px,.7fr)]">
      <div className="min-w-0 overflow-hidden rounded-xl border border-[#DFE9F4] bg-white">
       <div className="grid grid-cols-[minmax(0,1.6fr)_56px_68px] gap-2 border-b border-[#EAF0F6] bg-[#F4F8FC] px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#7386A0] sm:grid-cols-[minmax(0,1.8fr)_72px_88px]">
          <span>Equipment type</span><span className="text-center">Required*</span><span className="text-center">Visible*</span>
       </div>
       {proof.items.map(v=>{
         const value=blocked?null:v.sample_counts.find(s=>s.second===sample)?.count??null;
         const manual=v.verification_tier==='officer_verification_required';
         const selected=selection===v.id;
         return <button key={v.id} type="button" onClick={()=>setSelection(v.id)}
           aria-pressed={selected}
           className={'kw-focus grid w-full grid-cols-[minmax(0,1.6fr)_56px_68px] items-center gap-2 border-b border-[#EDF1F6] px-3 py-3 text-left last:border-0 sm:grid-cols-[minmax(0,1.8fr)_72px_88px] '+(selected?'bg-[#EDF6FF]':'hover:bg-[#FAFCFF]')}>
           <span className="min-w-0 text-[11px] font-semibold text-[#314D69] sm:text-[12px]">{v.label}</span>
           <span className="text-center text-[13px] font-bold tabular-nums text-[#345675]">{v.required}</span>
           <span className={'text-center text-[13px] font-bold tabular-nums '+(value!==null&&value<v.required?'text-[#A76B29]':'text-[#315B81]')}>
             {manual||value===null?'—':value}
           </span>
         </button>;
       })}
       <p className="border-t border-[#EBEFF5] px-3 py-3 text-[10px] leading-4 text-[#768AA1]">
         *Illustrative role quantities and cached example counts; not official stock requirements or independently verified detections.
       </p>
      </div>
      <aside className="min-w-0 space-y-3">
       <div className="rounded-xl border border-[#DFE9F4] bg-white p-4" aria-label="Selected item assessment">
        <div className="flex items-center gap-2 text-[11px] font-semibold text-[#365A7B]"><ToolCase size={15}/> Selected item</div>
        <h4 className="mt-2 text-[14px] font-bold text-[#263F5D]">{item.label}</h4>
        <p className="mt-2 text-[12px] font-semibold text-[#885D29]">{stateLabel(item,blocked)}</p>
        <p className="mt-2 text-[11px] leading-5 text-[#637A95]">{detail(item,blocked)}</p>
        <p className="mt-3 border-t border-[#EDF1F6] pt-3 text-[10px] leading-5 text-[#7B8DA2]">
          {item.verification_tier==='officer_verification_required'
          ? 'Verification: physical officer check'
          :item.verification_tier==='camera_partially_verifiable'
           ? 'Verification: visual presence only; operational condition unknown'
           :'Verification: camera candidate only, pending source and independent labels'}
        </p>
       </div>
       <div className="rounded-xl border border-[#DFE9F4] bg-white p-4">
         <div className="flex items-center gap-2 text-[11px] font-semibold text-[#365A7B]"><ClipboardCheck size={14}/> Evidence gate</div>
         <div className="mt-3 space-y-2 text-[11px]">
           <p className="flex items-center gap-2 text-[#3C664F]"><CheckCircle2 size={13}/> Curriculum item type recorded</p>
           <p className="flex items-center gap-2 text-[#92682C]"><ShieldAlert size={13}/> Count authority not established</p>
           <p className="flex items-center gap-2 text-[#92682C]"><CameraOff size={13}/> No matching recorded equipment footage</p>
           <p className="flex items-center gap-2 text-[#92682C]"><ShieldAlert size={13}/> Independent TP/FP/FN not measured</p>
         </div>
       </div>
      </aside>
     </div>
     <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
       <p className="max-w-[650px] text-[11px] leading-5 text-[#657F99]">
         Three authored sample timestamps, not a detector run. ROI consistency, item recall and practical-work authorization remain unverified. A blocked camera withholds every visual count.
       </p>
       <Link href="/centres/DEMO-KA-303/practical"
         className="kw-focus inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#2B689D]">
         Practical activity workflow <ArrowRight size={13}/>
       </Link>
     </div>
   </>}
 </section>;
}
