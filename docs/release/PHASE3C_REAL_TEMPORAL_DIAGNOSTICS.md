# Phase 3C — Reproduced Real OpenVINO Temporal Diagnosis

**Date:** 15 October 2026
**Scope:** Inspected public development baseline only. Independent compliance accuracy is NOT qualified.
**Run:** https://github.com/dev-ahmed01/KaushalWatch/actions/runs/38674265976 — successful
**Artifacts:** epfl-real-pipeline-diagnostic.json and epfl-real-pipeline-15s-diagnostic.json, within the short-lived EPFL benchmark artifact.

## Question and method

The established EPFL detector benchmark (91.45% precision / 89.95% recall over 113 sampled annotated frames) and the six-second zero confirmed occupancy were produced by different time windows and different measurement stages. We instrumented the actual attendance pipeline using its existing observation sink. No OpenVINO model, frozen profile, tracking thresholds, camera evidence gate, or production rules were changed.

| Observation | 6-second excerpt | 15-second excerpt |
| --- | ---: | ---: |
| Sampled frames | 30 | 75 |
| Eligible post-warmup samples | 20 | 65 |
| Camera-trusted samples | 30 | 75 |
| Detector failures | 0 | 0 |
| Eligible raw-positive samples | 4 | 48 |
| Confirmed-positive samples | 0 | 44 |
| Registered-positive samples | 0 | 39 |
| Smoothed-positive samples | 0 | 43 |
| First eligible raw detection | 5.2 seconds | 5.2 seconds |
| First confirmed track | None | 6.2 seconds |
| Estimated median occupancy | 0 | 1 |
| Sampled frames bearing EPFL person labels | 2 | 47 |

The previously used public EPFL annotation copy first marks a person at **frame 136 (approximately 5.44 seconds at 25 FPS)**. The six-second excerpt stops at sampled frame 145 (5.8 seconds): insufficient time to satisfy the frozen one-second confirmation rule after the late arrival. The 15-second diagnostic confirms a track at 6.2 seconds and shows positive occupancy, using the same detector and profile. The early raw detection at 5.2 seconds predates the first annotation and is not claimed to be a true positive.

**Conclusion:** The original zero was an artifact of the deliberately short clip and temporal confirmation window. This evidence does not establish an underlying tracker bug and does not justify loosening thresholds.

The trace contains only elapsed time, frame index, numeric counts and eligibility. It excludes images, tracks, frame hashes, names and bounding boxes; pre-warmup/untrusted numerical counts are withheld.

## Limits and release gate

Both attendance decisions compare with a deliberately synthetic attendance register of 3 and must not be interpreted as real fraud or attendance-case accuracy. EPFL was already used during model selection; it is not an untouched training-centre heldout. Practical authorization and training truth are unavailable. The combined model, camera, practical, equipment and ROI-motion outputs remain UNQUALIFIED.

Machine-readable data-status register: evaluation/phase3c_asset_readiness.json. It records five missing/blocked independent accuracy pillars and known nonqualifying development sources. Do not upload raw footage, credentials or model binaries to the repository or public CI artifacts.

## Next blocked dependencies

1. Secure lawful institution-authorized, untouched, independently reviewed multi-camera training-centre recordings outside Git.
2. Verify original recording/site/camera IDs, SHA-256, timestamps, independent labels, attendance registers and practical authorization; freeze calibration versus final holdout and model/policy revisions before scoring.
3. Run the existing five real model/evidence evaluators with per-scene, abstention and failure analysis. GroundingDINO predictions must not be replaced with human-corrected cache values for model-only accuracy.
4. Preserve experimental Camera Trust PR #54 as unmerged until separately qualified.
5. Move to production-like staging and officer pilot only after independent error/coverage thresholds, identity/MFA and private storage security checks actually pass.

**Status:** Phase 3C real anomaly diagnosis completed and reproduced; independent Phase 3C accuracy qualification remains blocked. Pilot readiness: FALSE.
