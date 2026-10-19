/** Trade-specific SIH controlled exhibit. Counts are fixtures, NOT verified detections. */
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import path from 'node:path';

const IDS=['workbench','chair','training_panel','drill_machine','multimeter'] as const;
const TIERS=['camera_verifiable','camera_partially_verifiable','officer_verification_required'];
const MAX_FILE=30000;
const sha=(b:Buffer)=>createHash('sha256').update(b).digest('hex');
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const num=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);

export type TradeSample={second:number;count:number;confidence:number};
export type TradeItem={
 id:string;label:string;required:number;verification_tier:string;
 source_basis:string;operability_method:string;
 sample_counts:TradeSample[];example_observed:number|null;
 example_state:'illustrative_gap'|'illustrative_alignment'|'manual_officer_check'|'no_samples';
};
export type TradeProof={
 schema:'KW_CONTROLLED_TRADE_PROOF_V1';status:'illustrative_only';
 job_role:string;job_role_code:string;source_authority:string;
 counts_are_simulated:true;video_source_sha256:null;
 model_run_verified:false;camera_quality_verified:false;
 independent_per_class_tp_fp_fn:null;external_work_authorization:'unknown';
 fixture_manifest_sha256:string;fixture_cache_sha256:string;
 sampling_seconds:number[];items:TradeItem[];
};

export function localTradePermitted(env:NodeJS.ProcessEnv=process.env):boolean{
 const mode=(env.KAUSHALWATCH_ENV||'development').toLowerCase();
 return env.NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY!=='true'
   && env.KAUSHALWATCH_WEB_AUTH_MODE!=='protected'
   && env.KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT!=='true'
   && !['pilot','prod','production','staging'].includes(mode);
}
function validatedDocument(raw:unknown):{
 job_role:string;job_role_code:string;authority:string;items:TradeItem[];
}{
 if(!object(raw)||raw.quantities_status!=='simulated'
   ||raw.job_role!=='Construction Electrician - LV'
   ||raw.job_role_code!=='CON/Q0603'
   ||!object(raw.source)||typeof raw.source.authority!=='string'
   ||!raw.source.authority.includes('CSDCI')
   ||!Array.isArray(raw.items)||raw.items.length!==IDS.length)
   throw new Error('Manifest is not the reviewed illustrative trade');
 const known=new Set<string>(),items:TradeItem[]=[];
 for(const v of raw.items){
   if(!object(v)||typeof v.id!=='string'||!IDS.includes(v.id as typeof IDS[number])
     ||known.has(v.id)||typeof v.label!=='string'||v.label.length>110
     ||typeof v.required!=='number'||!Number.isSafeInteger(v.required)||v.required<1||v.required>500
     ||typeof v.verification_tier!=='string'||!TIERS.includes(v.verification_tier)
     ||typeof v.source_basis!=='string'||v.source_basis.length>650
     ||typeof v.operability_method!=='string')throw new Error('Invalid trade item');
   known.add(v.id);
   items.push({id:v.id,label:v.label,required:v.required,
    source_basis:v.source_basis,verification_tier:v.verification_tier,
    operability_method:v.operability_method,
    sample_counts:[],example_observed:null,example_state:'no_samples'});
 }
 if(IDS.some(id=>!known.has(id)))throw new Error('Missing approved trade item');
 return {job_role:raw.job_role,job_role_code:raw.job_role_code,
   authority:raw.source.authority,items};
}

export function buildTradeProof(manifest:unknown,cache:unknown,
 manifestHash:string,cacheHash:string):TradeProof{
 const doc=validatedDocument(manifest);
 if(!Array.isArray(cache)||cache.length!==3)throw new Error('Fixture sample count changed');
 const stamps:number[]=[];
 const samples=new Map<string,TradeSample[]>();
 for(const id of IDS)samples.set(id,[]);
 for(const row of cache){
   if(!object(row)||!num(row.second)||row.second<0
     ||!Array.isArray(row.detections)||row.detections.length!==4)
       throw new Error('Malformed demo sample');
   stamps.push(row.second);
   const seen=new Set<string>();
   for(const det of row.detections){
     if(!object(det)||typeof det.label!=='string'
       ||!IDS.includes(det.label as typeof IDS[number])
       ||det.label==='multimeter'||seen.has(det.label)
       ||typeof det.count!=='number'||!Number.isSafeInteger(det.count)||det.count<0||det.count>500
       ||!num(det.confidence)||det.confidence<0||det.confidence>1)
        throw new Error('Unverified equipment fixture value');
     seen.add(det.label);
     samples.get(det.label)?.push({second:row.second,count:det.count,confidence:det.confidence});
   }
   if(seen.size!==4)throw new Error('Missing sample field is unknown, not zero');
 }
 if(stamps.some((t,i)=>t!==i*10))throw new Error('Demo fixture sample timing changed');
 const items=doc.items.map(item=>{
   const views=samples.get(item.id)||[];
   if(item.verification_tier==='officer_verification_required'){
     return {...item,sample_counts:[],example_observed:null,
       example_state:'manual_officer_check' as const};
   }
   if(views.length!==3)return {...item,sample_counts:[],example_observed:null,
     example_state:'no_samples' as const};
   const ordered=views.map(v=>v.count).sort((a,b)=>a-b);
   const median=ordered[1];
   return {...item,sample_counts:views,example_observed:median,
     example_state:median<item.required?'illustrative_gap' as const:'illustrative_alignment' as const};
 });
 return {schema:'KW_CONTROLLED_TRADE_PROOF_V1',status:'illustrative_only',
   job_role:doc.job_role,job_role_code:doc.job_role_code,
   source_authority:doc.authority,counts_are_simulated:true,
   video_source_sha256:null,model_run_verified:false,camera_quality_verified:false,
   independent_per_class_tp_fp_fn:null,external_work_authorization:'unknown',
   fixture_manifest_sha256:manifestHash,fixture_cache_sha256:cacheHash,
   sampling_seconds:stamps,items};
}

export async function loadTradeProof(root=process.cwd()):Promise<TradeProof>{
 const appRoot=path.basename(root)==='web'?path.dirname(root):root;
 const manifestPath=path.join(appRoot,'configs','job_roles','construction_electrician.demo.json');
 const cachePath=path.join(appRoot,'demo','cached_detections','construction_electrician.example.json');
 const [m,c]=await Promise.all([readFile(manifestPath),readFile(cachePath)]);
 if(m.length>MAX_FILE||c.length>MAX_FILE)throw new Error('Oversized controlled data');
 return buildTradeProof(JSON.parse(m.toString('utf8')),JSON.parse(c.toString('utf8')),sha(m),sha(c));
}
