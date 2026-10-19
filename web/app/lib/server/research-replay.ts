/** Local-only private Camera Trust research replay. Never serves Google Drive URLs. */
import {createHash} from 'node:crypto';
import {lstat,readFile,realpath} from 'node:fs/promises';
import path from 'node:path';

const SHA=/^[0-9a-f]{64}$/;
const IDS=['quality-covered','quality-defocused','quality-moved','quality-normal'] as const;
const NAMES=[
 'covered_gentle_frame721_onset.mp4',
 'defocused_strong_frame166275_onset.mp4',
 'moved_gentle_frame7919_onset.mp4',
 'normal_control_1.mp4',
] as const;
const CLASSES=['covered','defocused','moved','normal'];
export type ResearchClip={
 id:string;name:string;annotation_class:string;fps:number;
 duration_seconds:number;event_start_seconds:number|null;
 event_end_seconds:number|null;source_sha256:string;source_url:string;
 source_type:'research_annotation_not_model_inference';
};
export type ResearchCatalog={
 schema:'KW_PRIVATE_RESEARCH_REPLAY_STATUS_V1';status:'ready';
 research_only:true;training_centre_validation:false;
 model_inference_qualified:false;clips:ResearchClip[];
};
type InternalClip={visible:ResearchClip;bytes:Buffer};

const plain=(x:unknown):x is Record<string,unknown>=>
 Boolean(x)&&typeof x==='object'&&!Array.isArray(x);
const finite=(x:unknown):x is number=>typeof x==='number'&&Number.isFinite(x);
const localHost=(host:string)=>/^(localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?$/.test(host.toLowerCase());

export function localResearchPermitted(env:NodeJS.ProcessEnv,headers:Headers):boolean{
 const mode=(env.KAUSHALWATCH_ENV||'').toLowerCase();
 const host=headers.get('host')||'';
 const forwarded=headers.get('x-forwarded-host');
 return env.KAUSHALWATCH_LOCAL_RESEARCH_REPLAY==='true'
   && ['local','development','test'].includes(mode)
   && env.NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY!=='true'
   && env.KAUSHALWATCH_WEB_AUTH_MODE!=='protected'
   && env.KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT!=='true'
   && localHost(host)&&(!forwarded||forwarded===host)
   && headers.get('sec-fetch-site')!=='cross-site';
}

export async function checkedResearchClips(root:string):Promise<InternalClip[]>{
 if(!path.isAbsolute(root))throw new Error('No approved absolute research cache');
 const home=await realpath(root);
 const application=await realpath(process.cwd());
 if(home===application||home.startsWith(application+path.sep)
    ||home.includes(path.sep+'public'+path.sep))
    throw new Error('Research cache must reside outside application and public files');
 const filename=path.join(home,'kw-research-replay.local.json');
 const manifestStat=await lstat(filename);
 if(!manifestStat.isFile()||manifestStat.isSymbolicLink()||manifestStat.size>24_000)
   throw new Error('Invalid research manifest file');
 const manifest:unknown=JSON.parse((await readFile(filename)).toString('utf8'));
 if(!plain(manifest)||manifest.schema!=='KW_RESEARCH_REPLAY_V1'
   ||manifest.provenance!=='MEVA_UHCTD_RESEARCH_ANNOTATIONS_NOT_SKILL_CENTRE'
   ||manifest.annotation_origin!=='existing_Meva_UHCTD_Day3_selected_clips_csv'
   ||manifest.model_inference_qualified!==false
   ||manifest.training_centre_provenance!==false
   ||!Array.isArray(manifest.clips)||manifest.clips.length!==IDS.length)
    throw new Error('Research manifest not qualified');
 const byId=new Map<string,unknown>();
 for(const item of manifest.clips){
   if(!plain(item)||typeof item.id!=='string'||byId.has(item.id))
     throw new Error('Duplicate or missing clip identity');
   byId.set(item.id,item);
 }
 const clips:InternalClip[]=[];
 for(let i=0;i<IDS.length;i++){
   const id=IDS[i],entry=byId.get(id);
   if(!plain(entry)||entry.filename!==NAMES[i]
     ||entry.annotation_class!==CLASSES[i]
     ||typeof entry.name!=='string'||entry.name.length>80
     ||!SHA.test(String(entry.source_sha256))
     ||entry.fps!==3||!finite(entry.duration_seconds)
     ||entry.duration_seconds<1||entry.duration_seconds>300
     ||!Number.isSafeInteger(entry.bytes)||Number(entry.bytes)<10000
     ||Number(entry.bytes)>16_000_000)throw new Error('Unapproved clip metadata');
   const start=entry.event_start_seconds,end=entry.event_end_seconds;
   if(id==='quality-normal'){
     if(start!==null||end!==null)throw new Error('Normal control has unexpected event');
   }else if(!finite(start)||!finite(end)||start<0||start>=end
     ||end>entry.duration_seconds)throw new Error('Invalid event timing');
   const clipPath=path.join(home,NAMES[i]);
   const stat=await lstat(clipPath);
   if(!stat.isFile()||stat.isSymbolicLink()||stat.size!==entry.bytes)
     throw new Error('Cached clip identity mismatch');
   const bytes=await readFile(clipPath);
   if(bytes.subarray(4,8).toString('utf8')!=='ftyp'
     ||createHash('sha256').update(bytes).digest('hex')!==entry.source_sha256)
     throw new Error('Cached clip checksum mismatch');
   clips.push({visible:{
     id,name:String(entry.name),annotation_class:String(entry.annotation_class),
     fps:3,duration_seconds:entry.duration_seconds,
     event_start_seconds:start as number|null,
     event_end_seconds:end as number|null,
     source_sha256:String(entry.source_sha256),
     source_url:'/api/demo/research-replay/'+id+'/media',
     source_type:'research_annotation_not_model_inference',
   },bytes});
 }
 return clips;
}
export async function researchCatalog(env:NodeJS.ProcessEnv):Promise<ResearchCatalog>{
 const found=await checkedResearchClips(env.KAUSHALWATCH_RESEARCH_REPLAY_DIR||'');
 return {schema:'KW_PRIVATE_RESEARCH_REPLAY_STATUS_V1',
   status:'ready',research_only:true,training_centre_validation:false,
   model_inference_qualified:false,clips:found.map(x=>x.visible)};
}
