export type SceneId = 'attendance' | 'camera' | 'equipment' | 'normal';
export type DemoScene = {
  id:SceneId; centreId:string; title:string; subtitle:string; reported:number;
  observed:number|null; unit:string; requirement:string; question:string;
  compare:string; conclusion:string; action:string; href:string;
};
export const DEMO_SCENES:readonly DemoScene[]=[
  {id:'attendance',centreId:'DEMO-KA-104',title:'Attendance gap',subtitle:'01 · Attendance',reported:28,observed:19,unit:'trainees',
  requirement:'Construction Electrician - LV. Compare with the approved batch record.',
  question:'A centre reports 28 trainees. What does the available observation support?',
  compare:'A simple people counter might declare fraud after one low frame.',
  conclusion:'Persistent discrepancies require an evidence-backed officer review, not an automatic fraud finding.',
  action:'Review the attendance case and its time-linked evidence.',href:'/centres/DEMO-KA-104/evidence'},
  {id:'camera',centreId:'DEMO-KA-207',title:'Camera is obstructed',subtitle:'02 · Camera Trust',reported:21,observed:null,unit:'trainees',
  requirement:'A usable camera is required before physical attendance can be assessed.',
  question:'The register reports 21 people. The camera cannot reliably see them.',
  compare:'A simple system might mistake an unavailable count for zero people.',
  conclusion:'KaushalWatch withholds the headcount and requests verification. No absence allegation.',
  action:'Inspect the camera and request another authorised source.',href:'/centres/DEMO-KA-207/camera-trust'},
  {id:'equipment',centreId:'DEMO-KA-303',title:'Equipment visibility',subtitle:'03 · Infrastructure',reported:12,observed:9,unit:'panels',
  requirement:'Job-role manifest: distinguish sanctioned types and counts from camera-visible items.',
  question:'The manifest expects 12 training panels. Nine appear in the illustrative record.',
  compare:'A basic detector may mislabel an occluded item as missing or broken.',
  conclusion:'Not visible is not proven absent. Apparent activity is not proof of mechanical health.',
  action:'Request equipment-specific officer verification.',href:'/centres/DEMO-KA-303/infrastructure'},
  {id:'normal',centreId:'DEMO-KA-112',title:'No exception needed',subtitle:'04 · Negative control',reported:24,observed:24,unit:'trainees',
  requirement:'A good decision system needs negative control cases, not just alerts.',
  question:'A reliable comparison should also show what aligned evidence looks like.',
  compare:'A dramatic dashboard focuses on red alerts rather than correct quiet outcomes.',
  conclusion:'The illustrative attendance numbers align. This does not certify all centre operations.',
  action:'Continue normal monitoring without inventing a case.',href:'/centres/DEMO-KA-112'}
] as const;
export const STAGES=['Reported','Required','Observed','Decision'] as const;
export function stageDescription(scene:DemoScene,index:number):string{
  switch(index){
    case 0:return 'Reported '+scene.reported+' '+scene.unit+'. This is a centre claim, not independently verified physical attendance.';
    case 1:return scene.requirement;
    case 2:return scene.observed===null?'Evidence unavailable. An obstructed camera cannot establish zero attendance.':
      'Illustrative observed '+scene.observed+' '+scene.unit+'. Exact model run and independent annotation are separate qualification steps.';
    default:return scene.action;
  }
}
