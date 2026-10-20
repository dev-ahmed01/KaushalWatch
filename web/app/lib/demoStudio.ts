/**
 * Presentation-only script. Every finding and response is simulated and
 * triggered by media playback TIME, not by video pixels or a model.
 * Keep this deliberately separate from the backend's real case pipeline.
 */
export type StudioSceneId = 'attendance' | 'infrastructure' | 'camera';
export type StudioView = 'Overview' | 'Issues' | 'Insights' | 'Centre Desk' | 'Chatbox';

export type StudioEvent = {
  at: number;
  title: string;
  detail: string;
  kind: 'neutral' | 'check' | 'attention';
};
export type StudioScene = {
  id: StudioSceneId;
  title: string;
  centre: string;
  centreId: string;
  subtitle: string;
  clipId: 'training-bay' | 'workshop-floor' | 'east-corridor';
  category: string;
  reported: number | null;
  observed: number | null;
  unit: string;
  issue: string;
  finding: string;
  recommendation: string;
  role: string;
  events: readonly StudioEvent[];
};

export const STUDIO_SCENES: readonly StudioScene[] = [
  {
    id: 'attendance', clipId: 'training-bay',
    title: 'Attendance gap', subtitle: 'Training bay · Scenario 01',
    centre: 'Hubballi TC-03', centreId: 'DEMO-KA-104',
    category: 'Attendance reconciliation', unit: 'trainees', reported: 28, observed: 19,
    issue: 'Reported and illustrative occupancy differ by nine.',
    finding: 'The scripted sample compares 28 reported trainees with 19 simulated visible trainees. This is a review signal, not proof of absence.',
    recommendation: 'Request the batch register and check alternate rooms before the officer decides.',
    role: 'Centre Head',
    events: [
      {at: 0, title: 'Recording ready', detail: 'Source-locked procedural training-bay clip selected.', kind: 'neutral'},
      {at: 4, title: 'Frame quality check', detail: 'Scripted example marks the camera usable for this scene.', kind: 'check'},
      {at: 8, title: 'Anonymous occupancy sample', detail: 'Script generates 19 visible trainees against a reported 28.', kind: 'neutral'},
      {at: 12, title: 'Discrepancy surfaced', detail: 'Nine-trainee variance enters the synthetic officer review queue.', kind: 'attention'},
      {at: 16, title: 'Case prepared', detail: 'Simulated case and centre-head follow-up are available.', kind: 'check'},
    ],
  },
  {
    id: 'infrastructure', clipId: 'workshop-floor',
    title: 'Equipment visibility', subtitle: 'Workshop floor · Scenario 02',
    centre: 'Hubballi TC-03', centreId: 'DEMO-KA-104',
    category: 'Infrastructure assurance', unit: 'training panels', reported: 3, observed: 2,
    issue: 'One required panel is not visible in the simulated sample.',
    finding: 'The scripted equipment example records two visible panels against three on the training manifest. Visibility alone does not prove an item is missing.',
    recommendation: 'Ask the centre head for an updated room scan and inventory confirmation.',
    role: 'Lab Support',
    events: [
      {at: 0, title: 'Recording ready', detail: 'Source-locked procedural workshop clip selected.', kind: 'neutral'},
      {at: 4, title: 'Viewpoint check', detail: 'Scripted camera usability check completed.', kind: 'check'},
      {at: 8, title: 'Equipment proposal', detail: 'Synthetic detector response: two training panels visible.', kind: 'neutral'},
      {at: 12, title: 'Requirement comparison', detail: 'Three specified versus two visible; officer clarification needed.', kind: 'attention'},
      {at: 16, title: 'Follow-up prepared', detail: 'Synthetic inspection follow-up created in Centre Desk.', kind: 'check'},
    ],
  },
  {
    id: 'camera', clipId: 'east-corridor',
    title: 'Camera trust', subtitle: 'East corridor · Scenario 03',
    centre: 'Mysuru TC-01', centreId: 'DEMO-KA-207',
    category: 'Evidence usability', unit: 'trainees', reported: 21, observed: null,
    issue: 'Camera-quality concern suspends attendance inference.',
    finding: 'The scripted scenario withholds attendance counts because the simulated camera-trust gate cannot establish usable evidence. It does not prove deliberate tampering.',
    recommendation: 'Ask the centre to restore a usable camera view and collect new evidence.',
    role: 'Centre Head',
    events: [
      {at: 0, title: 'Recording ready', detail: 'Source-locked procedural corridor clip selected.', kind: 'neutral'},
      {at: 4, title: 'Visibility check', detail: 'Scripted quality signal is under review.', kind: 'neutral'},
      {at: 8, title: 'Usability warning', detail: 'Camera-quality scenario triggers an uncertain evidence state.', kind: 'attention'},
      {at: 12, title: 'Counts withheld', detail: 'No observed attendance count is asserted from this recording.', kind: 'attention'},
      {at: 16, title: 'Restoration requested', detail: 'Synthetic officer follow-up recommends a new usable view.', kind: 'check'},
    ],
  },
] as const;

export const STUDIO_VIEWS: readonly StudioView[] = ['Overview','Issues','Insights','Centre Desk','Chatbox'];

export function studioStage(scene: StudioScene, second: number) {
  const timeline = scene.events.filter(event => event.at <= second);
  return {
    timeline,
    checked: second >= 4,
    sampled: second >= 8,
    flagged: second >= 12,
    prepared: second >= 16,
    active: timeline[timeline.length - 1] || scene.events[0],
  };
}

export function scriptedAnswer(scene: StudioScene, second: number, question: string, reviewed: boolean): string {
  const stage = studioStage(scene, second);
  const q = question.toLowerCase();
  if (!stage.sampled) {
    return 'The selected recording has not reached the scripted analysis checkpoint yet. Play or seek to 00:08 to reveal its illustrative finding. No camera inference is being performed.';
  }
  if (/source|real|actual|model|confidence|genuine|prove/.test(q)) {
    return 'This is a controlled, time-synchronised simulation using a SHA-verified procedural recording. The detections, case and explanation are scripted; they are not model output or independently validated training-centre evidence.';
  }
  if (/next|action|follow|resolve|contact|message|recommend/.test(q)) {
    return scene.recommendation + (reviewed ? ' The synthetic officer case has been marked reviewed locally.' : ' An officer must review it before closure.');
  }
  if (/why|reason|evidence|gap|count|attendance|equipment|camera/.test(q)) {
    return scene.finding + ' Source: ' + scene.clipId + ' (procedural replay) at the 00:08–00:16 simulation checkpoints.';
  }
  return scene.title + ' — ' + scene.finding + ' ' + (stage.flagged ? scene.recommendation : 'Continue playback to reveal the review workflow.');
}
