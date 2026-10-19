'use client';
import {useEffect,useState} from 'react';
import {WifiOff} from 'lucide-react';
import type {OfflineReport} from '../lib/server/offline-report';

export default function OfflineTransportPanel(){
 const [report,setReport]=useState<OfflineReport|null>(null);
 useEffect(()=>{
   let active=true;
   fetch('/api/demo/offline-transport',{cache:'no-store'})
     .then(async r=>r.ok?await r.json() as OfflineReport:null)
     .then(value=>{
       if(active&&value?.schema==='KW_OFFLINE_TRANSPORT_DRILL_V1'
         &&value.status==='measured_loopback_fixture_not_field_qualified'
         &&value.raw_video_uploaded===false)setReport(value);
     }).catch(()=>{if(active)setReport(null)});
   return()=>{active=false};
 },[]);
 return <section className="rounded-xl border border-[#E0E9F4] bg-white p-4"
   aria-label="Offline transport proof">
   <WifiOff size={17} className="text-[#5C7DA4]"/>
   <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
    <h3 className="text-[13px] font-bold text-[#2A4666]">Offline by design</h3>
    <span className="text-[10px] font-semibold text-[#856329]">
      {report?'Measured · loopback fixture':'Not independently measured here'}
    </span>
   </div>
   {report?<>
    <div className="mt-3 grid grid-cols-3 gap-2">
     <div><p className="text-[10px] text-[#7E8DA2]">Delivered</p>
       <strong className="text-[20px] tabular-nums text-[#284967]">{report.delivered}/{report.queued_before}</strong></div>
     <div><p className="text-[10px] text-[#7E8DA2]">Retries</p>
       <strong className="text-[20px] tabular-nums text-[#284967]">{report.failed_attempts}</strong></div>
     <div><p className="text-[10px] text-[#7E8DA2]">Body bytes</p>
       <strong className="text-[20px] tabular-nums text-[#284967]">{report.observed_request_body_bytes_final.toLocaleString('en-IN')}</strong></div>
    </div>
    <p className="mt-2 text-[10px] text-[#71859C]">
     Queue {report.remaining} · duplicate re-ACK {report.duplicate_ack_count} · last sync {new Date(report.last_success_utc).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',hour12:true})} IST
    </p>
    <p className="mt-1 text-[10px] leading-4 text-[#8392A4]">Actual local HTTP-body measurement, not Internet/TLS bandwidth or real-camera accuracy.</p>
   </>:<p className="mt-2 text-[11px] leading-5 text-[#70849C]">
    Privacy-safe edge metadata can queue durably and retry. No local measured reconnect receipt is loaded.
   </p>}
 </section>;
}
