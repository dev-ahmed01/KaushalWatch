# Proof of Training — controlled SIH product redesign

PS SIH26245. Date: 20 October 2026. Source baseline: main 03240e59e7ff628763731ca744651829fd6052c5.

## The pitch

A centre reports. An approved trade manifest defines its obligations. The camera contributes limited visual observations. KaushalWatch checks evidence quality and persistence, identifies a question needing review, and lets an authorised officer decide.

Keep four top-level modules only: KaushalAI, Centres, Insights, Actions. Do not create a separate fake ministry backend or imply automated grant sanctions. The guided mission is a contextual link from KaushalAI.

## Competitor source audit — Abhilash-K-R/KausalyaDrishti-SIH2026

Inspected GitHub main repository tree (45 entries), README, PLAN, Hackathon Phases, Simple Guide, all/implement notes, all React edge/audit/ministry components, CSS, mock data, compliance rules, six developer logs, package manifests, Vite config and text-based companion HTML to the binary solution-plan PDF. Binary PDF and generated dependency lockfile were not separately visually audited. Repository metadata describes an unrelated healthcare PS, whereas the app and documentation target SIH26245.

* Real feature: browser-side TensorFlow.js COCO-SSD person detection and canvas overlays in src/components/edge/AiDetector.jsx.
* Demonstration shortcut: CameraFeedView.jsx includes simulatedExtraBatch controls that increase the displayed headcount by 5/37 in addition to detected people.
* Data boundary: src/data/centerMockData.js provides five handwritten Karnataka centre records and invented-looking national KPIs, not a live government dataset.
* Equipment audit: present/detected counts are populated from the mocked sanctionedEquipment arrays; code does not demonstrate independent industrial machinery precision/recall.
* Classification: complianceRules.js returns isGhostFraud for any delta greater than zero, and generates formal-sounding MSDE grant suspension text without real authority.
* MinistryConsole.jsx uses a browser alert as its dispatch acknowledgement; it is not evidence of official integration or actual notice delivery.
* BandwidthTelemetry.jsx renders JSON examples; no observed network transfer/byte comparison is proven by this UI component.
* UI: three dark portal screens (Edge, Audit, Ministry) with several detailed scorecards. Strong stage visuals; weak uncertainty boundaries.

Do not claim this rival has zero real model inference; it has real COCO-SSD. Do not claim our vision accuracy is higher unless measured on a matched independent dataset. Avoid reusing protected visuals or copying their branding.

## The six-phase implementation programme

### Phase 1 — Guided inspection (implementation underway)
Controlled fixture scenes with attendance shortfall, obstructed camera, missing equipment visibility and normal outcome. Each shows reported → required → observed → accountable decision. Where available, link actual saved API cases; never write to a case as a demo side effect. Authored fixtures clearly labelled and disabled entirely in protected mode. Pass: Next production build, browser E2E, mobile overflow checks.

### Phase 2 — Source-locked replay
Use already-authorised local/private footage, with no upload loop. Exact source SHA-256, frozen OpenVINO model/profile, replay with timestamps, evidence overlays derived from actual inference, camera quality events. Clear label: recorded playback, never disguised as a live stream. Fail closed on missing source, unsupported permission or mismatched hash. Pass: replay reproducible and coverage bounded.

### Phase 3 — Manifest and practical proof
Connect trade manifest to visible item types and numbers, verify ROI, frames and equipment temporally. Distinguish not-visible from absent; apparent motion from mechanical health. Add work-zone activity with independently verified authorization. Pass: source-locked item recall/precision and difficult negative clips.

### Phase 4 — Offline transport proof
Disconnect edge network, actually queue sanitized events, reconnect, measure transmitted bytes, duplicate acknowledgements, retry idempotence. No guaranteed 5KB claim without measurement. Pass: interruption/recovery integration and real byte metrics.

### Phase 5 — Officer evidence and accuracy
One inspection becomes reviewable case with original time window, SHA-bound evidence and officer action trail. Evaluate attendance MAE, false case rate, abstention coverage, equipment precision/recall, practical activity uncertainty and camera failure on independent blind labels. Include correct negative controls.

### Phase 6 — Submission quality and demo rehearsal
Polish light CRM, typography Bricolage heading + Poppins body, keep information concise; mock-data honesty, reproducible 3-minute click path, mobile/accessibility, full E2E/build/CI, locally preloaded approved assets, release lock. Production and autonomous enforcement remain out of scope until institutional approval and issue #91 acceptance.

## Judge flow

0–25s problem, 25–65s attendance/temporal proof, 65–95s camera-trust abstention, 95–130s item-specific infrastructure verification, 130–170s human review and evidence, 170–200s offline sync and normal control. This is a rehearsal target; later phases must implement measured replay and live offline tests before those claims are used.

## Controlled demo integrity

Synthetic registers and scripted scenario counts are labelled. Recorded detector output is shown only when an exact licensed clip/model/run receipt exists. Simulated action never freezes grants, issues official notices or impersonates government integration. Camera obstruction produces unknown, not zero. Missing equipment visibility is not proof of missing physical assets. Privacy-safe edge processing; no face recognition or real trainee identification. Keep later-stage claims explicitly pending.
