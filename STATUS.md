# Build Status

**CI status:** backend pytest, Next.js production build, and Playwright browser E2E all pass on the active build branch.

This file is the source of truth for what is verified, scaffolded, or still pending.

## Implemented in the current build branch
- FastAPI API skeleton and CORS.
- Video upload vertical slice.
- OpenCV HOG fallback plus the **selected OpenVINO person-detection-retail-0013 demo detector**.
- Occupancy smoothing and attendance-discrepancy logic.
- Temporal persistence before a compliance case is created.
- Camera-trust checks: dark, blur, frozen-frame and basic scene-shift signals.
- Case store and officer-review state workflow.
- Evidence metadata with SHA-256 and perceptual hash.
- Demo compliance manifest and cached equipment-detection adapter.
- Infrastructure expected-vs-observed comparison.
- Apparent-operability ROI motion proxy.
- Offline evaluation scripts for person precision/recall/F1, occupancy MAE, and case-level metrics.
- Durable edge telemetry queue, sync endpoint, and measured byte-reduction utility.
- Privacy-preserving design note.
- Next.js command-centre UI connected to the live API, including officer review actions and demo manifest rendering.

## Intentionally NOT claimed as complete
- HOG is retained only as a no-download fallback. OpenVINO was selected from the real EPFL Camera 0 benchmark.
- GroundingDINO is not yet validated live in this repository; cached detections are the demo fallback.
- Demo infrastructure quantities are synthetic until replaced with the applicable official sanctioned specification.
- Example evaluation rows are synthetic. Real SIH metrics require annotated EPFL / controlled-demo footage.
- GitHub CI has verified the browser vertical slice with a running FastAPI backend and Next.js frontend.
- Apparent operability means visual activity evidence only, never mechanical/electrical health.

## Next engineering milestones
1. Validate GroundingDINO separately; precompute the exact demo-video equipment detections as a stage-safe fallback.
2. Attach real/cached infrastructure evidence and apparent-operability observations to the same persisted case/evidence workflow.
3. Record/prepare a controlled mock training-centre clip for final compliance TP/FP/FN/TN measurement.
4. Run the low-bandwidth measurement utility on that exact final demo clip and report only measured transfer reduction.
5. Replace remaining illustrative operational values with either sourced values or explicit demo labels.
6. Keep runtime footage, model binaries, generated evidence and benchmark outputs outside git; follow CONTRIBUTING.md and docs/architecture.md.
