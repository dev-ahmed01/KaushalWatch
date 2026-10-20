/** Local controlled-story continuation; no caller-supplied redirect URLs. */
import {DEMO_SCENES,type SceneId} from './demoMission.ts';

const SCENES=new Map<string,string>(DEMO_SCENES.map(s=>[s.id,s.centreId]));

export type MissionPosition={scene:SceneId;step:number};
export const INITIAL_MISSION_POSITION:MissionPosition={scene:'attendance',step:0};

export function missionPositionFromSearch(search:string):MissionPosition{
 const params=new URLSearchParams(search.startsWith('?')?search.slice(1):search);
 const scene=params.get('scene')||'';
 const step=params.get('step')||'';
 if(!SCENES.has(scene)||!['0','1','2','3'].includes(step))
   return INITIAL_MISSION_POSITION;
 return {scene:scene as SceneId,step:Number(step)};
}

/** Only an expected centre-scoped case can return to its demo scenario. */
export function returnToMissionFromCase(search:string,centreId:string):string|null{
 const params=new URLSearchParams(search.startsWith('?')?search.slice(1):search);
 if(params.get('from')!=='mission')return null;
 const position=missionPositionFromSearch(search);
 if(SCENES.get(position.scene)!==centreId)return null;
 if(params.get('scene')!==position.scene||params.get('step')!==String(position.step))
   return null;
 return missionHref(position);
}
export function missionHref(position:MissionPosition):string{
 if(!SCENES.has(position.scene)||!Number.isInteger(position.step)
   ||position.step<0||position.step>3)
   throw new Error('Unsupported controlled walkthrough position');
 return '/demo/mission?scene='+position.scene+'&step='+position.step;
}
export function caseHrefWithReturn(caseId:string,position:MissionPosition):string{
 if(!/^[A-Za-z0-9_-]{3,96}$/.test(caseId))
   throw new Error('Invalid case identifier');
 const params=new URLSearchParams({
   from:'mission',scene:position.scene,step:String(position.step),
 });
 missionHref(position);
 return '/cases/'+encodeURIComponent(caseId)+'?'+params.toString();
}
