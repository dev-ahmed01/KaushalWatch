/** Descriptive (not inferential) challenge audit on already-inspected research labels.
 * Do not interpret these selected clips as independent accuracy, camera-hour
 * false alarm burden, or malicious interference ground truth.
 */
import type {TraceSample, TraceClip} from './research-analysis';

export type ChallengeCounts={
 samples:number;
 unusable:number;
 possibleInterference:number;
 withheld:number;
};
export type ChallengeClip={
 id:string;
 annotated:ChallengeCounts;
 normalOrPreEvent:ChallengeCounts;
 total:number;
};
export type ChallengeSummary={
 schema:'KW_PRIVATE_CHALLENGE_DESCRIPTIVE_V1';
 evidence_basis:'PREVIOUSLY_INSPECTED_UHCTD_DAY3_SPARSE_SAMPLES';
 is_independent_holdout:false;
 field_false_alarm_rate_available:false;
 physical_tampering_proven:false;
 auto_action_allowed:false;
 clips:ChallengeClip[];
 normalOrPreEvent:ChallengeCounts;
 annotated:ChallengeCounts;
};

const newCounts=():ChallengeCounts=>({
 samples:0,unusable:0,possibleInterference:0,withheld:0,
});

function include(counts:ChallengeCounts,s:TraceSample):void{
 counts.samples++;
 if(s.usability==='NOT_USABLE_FOR_VISUAL_VERIFICATION')counts.unusable++;
 if(s.interference_review==='POSSIBLE_SCENE_INTERFERENCE_REVIEW')
   counts.possibleInterference++;
 if(s.usability!=='PROVISIONALLY_OBSERVABLE')counts.withheld++;
}

export function sampleAtOrBefore(samples:readonly TraceSample[],seconds:number):TraceSample|null{
 if(!Number.isFinite(seconds)||seconds<0||!samples.length)return null;
 // Past-only cursor: a recording at 5.8s must never show a 6.0s inference.
 let low=0,high=samples.length-1,best=-1;
 while(low<=high){
   const mid=(low+high)>>>1;
   if(samples[mid].second<=seconds+1e-8){best=mid;low=mid+1;}
   else high=mid-1;
 }
 return best<0?null:samples[best];
}

export function challengeSummary(clips:readonly TraceClip[]):ChallengeSummary{
 const totalNormal=newCounts(),totalEvent=newCounts();
 const rows:ChallengeClip[]=clips.map(c=>{
   const annotated=newCounts(),normalOrPreEvent=newCounts();
   for(const s of c.samples){
     if(s.annotation_in_event){
       include(annotated,s);include(totalEvent,s);
     }else{
       include(normalOrPreEvent,s);include(totalNormal,s);
     }
   }
   return {id:c.id,annotated,normalOrPreEvent,total:c.samples.length};
 });
 return {
   schema:'KW_PRIVATE_CHALLENGE_DESCRIPTIVE_V1',
   evidence_basis:'PREVIOUSLY_INSPECTED_UHCTD_DAY3_SPARSE_SAMPLES',
   is_independent_holdout:false,
   field_false_alarm_rate_available:false,
   physical_tampering_proven:false,
   auto_action_allowed:false,
   clips:rows,normalOrPreEvent:totalNormal,annotated:totalEvent,
 };
}
