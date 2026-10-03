# Build Status

This file is the source of truth for what is verified, scaffolded, or still pending.

## Implemented in the current build branch
- FastAPI API skeleton and CORS.
- Video upload vertical slice.
- OpenCV HOG baseline person detector.
- Occupancy smoothing and attendance-discrepancy logic.
- Temporal persistence before a compliance case is created.
- Camera-trust checks: dark, blur, frozen-frame and basic scene-shift signals.
- Case store and officer-review state workflow.
- Evidence metadata with SHA-256 and perceptual hash.
- Demo compliance manifest and cached equipment-detection adapter.
- Infrastructure expected-vs-observed comparison.
- Apparent-operability ROI motion proxy.
- Offline evaluation script for occupancy and case-level metrics.
- Privacy-preserving design note.
- Next.js command-centre source scaffold.

## Intentionally NOT claimed as complete
- HOG is a no-download baseline, not the final SIH person detector.
- GroundingDINO is not yet validated live in this repository; cached detections are the demo fallback.
- Demo infrastructure quantities are synthetic until replaced with the applicable official sanctioned specification.
- Example evaluation rows are synthetic. Real SIH metrics require annotated EPFL / controlled-demo footage.
- The Next.js dashboard must be explicitly validated with `npm install`, `npm run build`, and live API data before it is marked verified.
- Apparent operability means visual activity evidence only, never mechanical/electrical health.

## Next engineering milestones
1. Run a selected **single-camera** EPFL sequence through the attendance pipeline.
2. Replace HOG with the chosen lightweight person detector and measure count MAE / precision / recall.
3. **Validate the frontend:** complete `npm install`, run `npm run build`, launch the dashboard, and verify it renders live API data and case-review actions.
4. Validate GroundingDINO separately; precompute the exact demo-video equipment detections as a stage-safe fallback.
5. Connect infrastructure discrepancies and operability observations into the same persisted compliance-case/evidence workflow.
6. Record/prepare a controlled mock training-centre clip for final compliance TP/FP/FN/TN measurement.
7. Add offline event queue/sync and measure actual bandwidth reduction.
8. Replace any remaining illustrative operational values with either sourced values or explicit demo labels.
