/** Read-only private local Phase 4 transport drill. Never exposes raw queue/media. */
import {lstat,readFile,realpath} from 'node:fs/promises';
import path from 'node:path';

const integer=(v:unknown):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0&&v<1e10;
const obj=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
export type OfflineReport={
 schema:'KW_OFFLINE_TRANSPORT_DRILL_V1';status:'measured_loopback_fixture_not_field_qualified';
 fixture:true;network_cut_verified:true;queue_survived_restart:true;
 lost_ack_idempotent_reack:true;queued_before:number;delivered:number;
 remaining:number;attempts:number;failed_attempts:number;
 duplicate_ack_count:number;server_event_rows:number;
 observed_request_body_bytes_final:number;observed_response_body_bytes_final:number;
 observed_request_body_bytes_all_received:number;last_success_utc:string;
 raw_video_uploaded:false;measurement_boundary:string;
};

export function localTransportReportAllowed(env:NodeJS.ProcessEnv,headers:Headers):boolean{
 const mode=(env.KAUSHALWATCH_ENV||'development').toLowerCase();
 const host=headers.get('host')||'',origin=headers.get('origin');
 let sameOrigin=true;
 if(origin){try{sameOrigin=new URL(origin).host===host;}catch{sameOrigin=false;}}
 return env.KAUSHALWATCH_LOCAL_OFFLINE_REPORT==='true'
  && ['development','local','test'].includes(mode)
  && env.NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY!=='true'
  && env.KAUSHALWATCH_WEB_AUTH_MODE!=='protected'
  && env.KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT!=='true'
  && /^(localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?$/.test(host)
  && (!headers.get('x-forwarded-host')||headers.get('x-forwarded-host')===host)
  && headers.get('sec-fetch-site')!=='cross-site'&&sameOrigin;
}
export function parseOfflineReport(raw:unknown):OfflineReport{
 if(!obj(raw)||raw.schema!=='KW_OFFLINE_TRANSPORT_DRILL_V1'
  ||raw.status!=='measured_loopback_fixture_not_field_qualified'
  ||raw.fixture!==true||raw.network_cut_verified!==true
  ||raw.queue_survived_restart!==true||raw.lost_ack_idempotent_reack!==true
  ||raw.raw_video_uploaded!==false)
    throw Error('Untrusted transport measurement receipt');
 const required=['queued_before','delivered','remaining','attempts','failed_attempts',
  'duplicate_ack_count','server_event_rows','observed_request_body_bytes_final',
  'observed_response_body_bytes_final','observed_request_body_bytes_all_received'] as const;
 if(required.some(k=>!integer(raw[k]))
  ||raw.delivered!==raw.server_event_rows||raw.delivered+raw.remaining!==raw.queued_before
  ||raw.attempts<3||raw.failed_attempts<2||raw.duplicate_ack_count<1
  ||raw.observed_request_body_bytes_final===0||raw.observed_response_body_bytes_final===0
  ||raw.observed_request_body_bytes_all_received<raw.observed_request_body_bytes_final
  ||typeof raw.last_success_utc!=='string'
  ||Number.isNaN(Date.parse(raw.last_success_utc))
  ||typeof raw.measurement_boundary!=='string'
  ||raw.measurement_boundary.length>300)
    throw Error('Invalid measured offline counters');
 return raw as OfflineReport;
}
export async function loadPrivateOfflineReport(file:string):Promise<OfflineReport>{
 if(!path.isAbsolute(file))throw Error('Private absolute report path required');
 const resolved=await realpath(file),app=await realpath(process.cwd());
 if(resolved===app||resolved.startsWith(app+path.sep)
   ||resolved.includes(path.sep+'public'+path.sep))
   throw Error('Measured report must stay outside web application files');
 const stat=await lstat(file);
 if(!stat.isFile()||stat.isSymbolicLink()||stat.size<100||stat.size>20000)
   throw Error('Untrusted measured report file');
 return parseOfflineReport(JSON.parse((await readFile(resolved)).toString('utf8')));
}
