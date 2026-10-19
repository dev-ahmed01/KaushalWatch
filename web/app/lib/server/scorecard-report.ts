/** Validate private local cross-pillar qualification receipts before any UI display. */
import {lstat,readFile,realpath} from 'node:fs/promises';
import path from 'node:path';

const PILLARS=['attendance','camera_trust','equipment_count','equipment_localization','practical_activity','offline_transport'] as const;
export type PillarId=(typeof PILLARS)[number];
type MetricCard={id:PillarId;state:string;metric:Record<string,unknown>|null;support:Record<string,unknown>|null;reason:string};
export type TrustScorecard={
 schema:'KW_PROOF_OF_TRAINING_SCORECARD_V1';status:string;qualified:false;
 scope:string;pillars:Record<PillarId,MetricCard>;receipt_sha256:Record<string,string>;limitations:string;
};
const obj=(v:unknown):v is Record<string,unknown>=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const integer=(v:unknown)=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0&&v<=1e9;
const ratio=(v:unknown)=>v===null||typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1;
const hex=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);

export function localScorecardAllowed(env:NodeJS.ProcessEnv,headers:Headers):boolean{
 const mode=(env.KAUSHALWATCH_ENV||'development').toLowerCase();
 const host=headers.get('host')||'',origin=headers.get('origin');
 let sameOrigin=true;
 if(origin){try{sameOrigin=new URL(origin).host===host;}catch{sameOrigin=false;}}
 return env.KAUSHALWATCH_LOCAL_SCORECARD==='true'
  && ['development','local','test'].includes(mode)
  && env.NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY!=='true'
  && env.KAUSHALWATCH_WEB_AUTH_MODE!=='protected'
  && env.KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT!=='true'
  && /^(localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?$/.test(host)
  && (!headers.get('x-forwarded-host')||headers.get('x-forwarded-host')===host)
  && headers.get('sec-fetch-site')!=='cross-site'&&sameOrigin;
}
export function parseTrustScorecard(value:unknown):TrustScorecard{
 if(!obj(value)||value.schema!=='KW_PROOF_OF_TRAINING_SCORECARD_V1'
  ||value.status!=='evidence_gates_reported_not_field_qualified'||value.qualified!==false
  ||value.scope!=='controlled_source_receipts_not_field_certification'
  ||typeof value.limitations!=='string'||value.limitations.length>500
  ||!obj(value.pillars)||Object.keys(value.pillars).length!==PILLARS.length
  ||!obj(value.receipt_sha256)
  ||Object.entries(value.receipt_sha256).some(([id,digest])=>!PILLARS.includes(id as PillarId)||!hex(digest)))
  throw Error('Invalid source-status scorecard');
 for(const id of PILLARS){
  const p=value.pillars[id];
  if(!obj(p)||p.id!==id||typeof p.reason!=='string'||p.reason.length>300
    ||!['not_qualified','measured_loopback_fixture_only',
        'candidate_measured_not_independently_qualified'].includes(String(p.state)))
    throw Error('Unsupported qualification state');
  if(p.state==='not_qualified'){
   if(p.metric!==null||p.support!==null)throw Error('Absent evidence cannot have scored metrics');
  }else if(id==='offline_transport'&&p.state==='measured_loopback_fixture_only'){
   if(!obj(p.metric)||!integer(p.metric.request_body_bytes)||p.metric.request_body_bytes===0
     ||!integer(p.metric.response_body_bytes)||p.metric.response_body_bytes===0
     ||!integer(p.metric.delivered)||!integer(p.metric.queued)
     ||(p.metric.delivered as number)>(p.metric.queued as number))
      throw Error('Invalid network-body measurement');
  }else if(id==='equipment_localization'&&p.state==='candidate_measured_not_independently_qualified'){
   if(!obj(p.metric)||!integer(p.metric.tp)||!integer(p.metric.fp)||!integer(p.metric.fn)
     ||!obj(p.metric.per_class)||!Object.keys(p.metric.per_class).length)
     throw Error('Invalid provisional object-box metrics');
   let sums={tp:0,fp:0,fn:0};
   for(const [name,metrics] of Object.entries(p.metric.per_class)){
    if(!/^[a-z0-9_]{2,64}$/.test(name)||!obj(metrics)
      ||!integer(metrics.tp)||!integer(metrics.fp)||!integer(metrics.fn)
      ||!ratio(metrics.precision)||!ratio(metrics.recall))
       throw Error('Invalid per-class provisional accuracy');
    sums.tp+=metrics.tp as number;
    sums.fp+=metrics.fp as number;
    sums.fn+=metrics.fn as number;
   }
   if(sums.tp!==p.metric.tp||sums.fp!==p.metric.fp||sums.fn!==p.metric.fn)
    throw Error('Per-class total mismatch');
  }else{
   throw Error('No field accuracy evidence accepted for this pillar');
  }
 }
 return value as unknown as TrustScorecard;
}
export async function readTrustScorecard(file:string):Promise<TrustScorecard>{
 if(!path.isAbsolute(file))throw Error('Private absolute source file required');
 const resolved=await realpath(file),root=await realpath(process.cwd());
 if(resolved===root||resolved.startsWith(root+path.sep)
  ||resolved.includes(path.sep+'public'+path.sep))
   throw Error('Source summary must be outside the application and public assets');
 const stat=await lstat(file);
 if(!stat.isFile()||stat.isSymbolicLink()||stat.size<100||stat.size>45000)
   throw Error('Invalid private summary file');
 return parseTrustScorecard(JSON.parse((await readFile(resolved)).toString('utf8')));
}
