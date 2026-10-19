'use client';
import {useEffect,useRef,useState} from 'react';
import {ArrowRight,CameraOff,ShieldCheck} from 'lucide-react';
import type {EquipmentCatalog} from '../lib/server/equipment-replay';

/** Only appears when an operator has explicitly admitted a local video+model receipt. */
export default function PrivateEquipmentReplay({withheld}:{withheld:boolean}){
 const player=useRef<HTMLVideoElement>(null);
 const [catalog,setCatalog]=useState<EquipmentCatalog|null>(null);
 const [state,setState]=useState<'off'|'ready'|'failed'>('off');
 const [decodeOk,setDecodeOk]=useState(false);
 const [decoderFailed,setDecoderFailed]=useState(false);
 const [second,setSecond]=useState(-1);
 useEffect(()=>{
   let mounted=true;
   fetch('/api/demo/equipment-replay',{cache:'no-store'})
    .then(async response=>{
      if(response.status===404)return null;
      if(!response.ok)throw Error('Invalid equipment replay');
      return await response.json() as EquipmentCatalog;
    })
    .then(data=>{
      if(!mounted||data===null)return;
      if(data.schema!=='KW_PRIVATE_EQUIPMENT_REPLAY_V1'
        ||data.status!=='source_and_receipt_matched_unqualified'
        ||data.training_centre_certified!==false
        ||data.independent_accuracy_qualified!==false
        ||data.model_execution_independently_verified!==false
        ||data.equipment_compliance_qualified!==false
        ||!Array.isArray(data.timestamps)||data.timestamps.length===0)
        throw Error('Unqualified source data');
      setCatalog(data);setState('ready');
    })
    .catch(()=>{if(mounted)setState('failed');});
   return()=>{mounted=false};
 },[]);
 if(state==='off')return null;
 const chosen=catalog?.timestamps.find(row=>Math.abs(row.second-second)<0.09);
 // Evidence is shown only at the timestamp of one saved model sample.
 const overlays=!withheld&&decodeOk&&!decoderFailed?chosen?.detections||[]:[];
 function seek(t:number){
   if(!player.current||!decodeOk)return;
   player.current.pause();
   player.current.currentTime=t;
   setSecond(t);
 }
 return <section aria-label="Recorded equipment model replay"
   className="mt-4 min-w-0 rounded-[20px] border border-[#CBDEEC] bg-white p-4 sm:p-5">
   <div className="flex flex-wrap items-start justify-between gap-3">
     <div>
       <p className="text-[11px] font-bold uppercase tracking-[.12em] text-[#7290AD]">Locally verified source and receipt</p>
       <h3 className="mt-1 text-[16px] font-bold text-[#2A4D6E]">Recorded equipment model proposals</h3>
       <p className="mt-1 max-w-[660px] text-[11px] leading-5 text-[#627B95]">
         An operator-supplied GroundingDINO output file matched to its exact private video.
         These are unreviewed proposals, not independently verified model accuracy or sanctioned equipment counts.
       </p>
     </div>
     <span className="inline-flex items-center gap-1.5 rounded-full bg-[#EEF5FC] px-3 py-1.5 text-[11px] font-semibold text-[#315E8A]">
       <ShieldCheck size={13}/> SHA matched
     </span>
   </div>
   {state==='failed'&&<p role="alert" className="mt-4 text-[12px] text-[#915B21]">
     Model receipt or video could not be admitted; no equipment proposals can be shown.
   </p>}
   {catalog&&<>
     <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(210px,.6fr)]">
       <div className="min-w-0">
         <div className="relative aspect-video overflow-hidden rounded-xl bg-[#172C41]">
           <video ref={player} src={catalog.video_url} muted playsInline preload="metadata"
             aria-label="Private recorded equipment source"
             className="h-full w-full object-contain"
             onLoadedMetadata={e=>{
               const v=e.currentTarget;
               const valid=Number.isFinite(v.duration)&&Math.abs(v.duration-catalog.duration)<=1.5
                 &&v.videoWidth===catalog.width&&v.videoHeight===catalog.height;
               setDecodeOk(valid);setDecoderFailed(!valid);
             }}
             onError={()=>{setDecoderFailed(true);setDecodeOk(false);}}
             onTimeUpdate={e=>setSecond(e.currentTarget.currentTime)}
             onSeeked={e=>setSecond(e.currentTarget.currentTime)}/>
           <span className="pointer-events-none absolute left-3 top-3 rounded bg-[#17354E]/90 px-2 py-1 text-[10px] font-bold text-white">
             Recording · not live
           </span>
           {!withheld&&decodeOk&&<div aria-hidden className="pointer-events-none absolute border border-dashed border-[#F7D483]"
             style={{left:(catalog.roi.x*100)+'%',top:(catalog.roi.y*100)+'%',
               width:(catalog.roi.width*100)+'%',height:(catalog.roi.height*100)+'%'}}/>}
           {overlays.map((box,i)=><div key={i} aria-label="Model proposal rectangle" className="pointer-events-none absolute border-2 border-[#7BE0B1]"
             style={{left:(box.x*100)+'%',top:(box.y*100)+'%',
               width:(box.width*100)+'%',height:(box.height*100)+'%'}}>
             <span className="absolute -top-4 left-0 whitespace-nowrap rounded bg-[#155B4D] px-1 text-[9px] text-white">
               {box.label} {(box.score*100).toFixed(0)}%
             </span>
           </div>)}
           {withheld&&<div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-[#132B42]/55 p-4 text-center text-[12px] font-semibold text-white">
             Camera-blockage example · model proposals withheld
           </div>}
         </div>
         {decoderFailed&&<p role="alert" className="mt-2 text-[11px] text-[#936127]">
           Browser codec or video geometry is unsupported. Playback and overlay disabled.
         </p>}
         <div className="mt-3 flex flex-wrap gap-2" aria-label="Saved model sample times">
           {catalog.timestamps.map(row=><button type="button" key={row.second}
             disabled={!decodeOk||withheld} onClick={()=>seek(row.second)}
             className="kw-focus rounded-lg border border-[#D9E5F2] bg-[#F7FAFD] px-3 py-2 text-[11px] font-semibold text-[#315D88] disabled:opacity-35">
             <ArrowRight size={11} className="mr-1 inline"/>{row.second.toFixed(1)}s
           </button>)}
         </div>
       </div>
       <aside className="space-y-3">
         <div className="rounded-xl border border-[#E0EAF3] p-3">
           <p className="text-[11px] font-bold text-[#315B80]">Source and model receipt</p>
           <p className="mt-2 text-[11px] leading-5 text-[#657E96]">
             Exact SHA-256 video and operator receipt match. Independent execution attestation and box-label accuracy are not established.
           </p>
           <code className="mt-2 block break-all font-mono text-[9px] text-[#607C99]">
             Video {catalog.source_sha256.slice(0,18)}… · Receipt {catalog.receipt_sha256.slice(0,18)}…
           </code>
           <p className="mt-2 text-[10px] leading-4 text-[#788A9D]">{catalog.source_origin}</p>
         </div>
         <div className="rounded-xl border border-[#E0EAF3] p-3">
           <p className="text-[11px] font-bold text-[#315B80]">Time-aligned model candidates</p>
           {withheld?<p className="mt-2 text-[11px] text-[#926127]"><CameraOff size={13} className="mr-1 inline"/>Withheld in camera-blockage example.</p>
             :chosen&&decodeOk?<div className="mt-2 space-y-1 text-[11px] text-[#486E8F]">
               {chosen.counts.map(c=><p key={c.id}>{c.id.replaceAll('_',' ')}: {c.count} <span className="text-[#7F8DA0]">(unreviewed proposal)</span></p>)}
             </div>
             :<p className="mt-2 text-[11px] text-[#7B8FA2]">Seek to a saved sample. No interpolation or missing=zero assumptions.</p>}
         </div>
       </aside>
     </div>
   </>}
 </section>;
}
