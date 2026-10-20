import {NextResponse} from 'next/server';
import proceduralManifest from '../../../../public/camera-trust/manifest.json';
import {loadReplayCatalog,localReplayPermitted} from '../../../lib/server/replay-catalog';

export const runtime='nodejs';
export const dynamic='force-dynamic';

// The public Vercel showcase uses committed SHA metadata and verifies each
// actual CDN video byte-for-byte in the browser before enabling playback.
// Vercel serverless bundles need not expose a public/ filesystem to the API.
const CLOUD_CLIPS=[
  {id:'training-bay',name:'Training bay',cue:'Focus variation',start:8,end:13},
  {id:'workshop-floor',name:'Workshop floor',cue:'Visibility change',start:9,end:15},
  {id:'east-corridor',name:'East corridor',cue:'Scene alignment',start:7,end:13},
] as const;

// Only the pre-generated, public synthetic clips are allowlisted here.
// This API never accepts filenames, reads Drive, exposes private CCTV,
// streams a secret video, or permits model receipts in a protected release.
export async function GET(){
 if(process.env.NEXT_PUBLIC_KAUSHALWATCH_PUBLIC_SHOWCASE==='true'
    && process.env.KAUSHALWATCH_PUBLIC_SHOWCASE==='true'
    && process.env.NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY!=='true'){
    const clips=CLOUD_CLIPS.map(clip=>({
      ...clip,duration:20,fps:12,
      sha256:proceduralManifest.clips[clip.id].sha256,
      source_url:'/camera-trust/'+clip.id+'.mp4',
      // The browser independently verifies these CDN bytes before acceptance.
      status:'verified',receipt_status:'absent',receipt:null,
    }));
    if(proceduralManifest.schema!=='KW_SUBMISSION_SAMPLE_MEDIA_V1'
      || proceduralManifest.provenance!=='PROCEDURALLY_GENERATED_RECORDING_NOT_REAL_CCTV'
      || clips.some(clip=>!/^[a-f0-9]{64}$/.test(clip.sha256)))
      return NextResponse.json({detail:'Invalid committed sample manifest'},{status:503});
    return NextResponse.json({
      schema:'KW_SOURCE_LOCKED_REPLAY_V1',kind:'synthetic_quality_demonstration',
      status:'ready',physical_camera_accuracy_qualified:false,
      private_video_available:false,source_match_is_model_validation:false,clips,
    },{headers:{'Cache-Control':'public, max-age=120','X-Content-Type-Options':'nosniff'}});
 }
 if(!localReplayPermitted())return NextResponse.json(
   {detail:'Controlled replay is disabled in protected environments'},
   {status:404,headers:{'Cache-Control':'private, no-store'}});
 const result=await loadReplayCatalog();
 return NextResponse.json(result,{
   status:result.status==='ready'?200:503,
   headers:{'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'},
 });
}
