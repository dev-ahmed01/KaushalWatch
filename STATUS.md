# Build Status

**Verification checkpoint:** core backend tests, final-evaluator smoke test, Next.js production build, Playwright browser E2E, EPFL detector benchmark, and isolated GroundingDINO image smoke inference all pass on the active core build.

This file is the source of truth for what is verified, scaffolded, or still pending.

## Verified in the current core build
- FastAPI API, configurable browser-origin CORS, evidence serving and persisted compliance cases.
- Video upload vertical slice.
- **OpenVINO person-detection-retail-0013 selected from the real EPFL Laboratory Camera 0 benchmark.**
- Auto detector selection now prefers the prepared benchmarked local OpenVINO model before YOLO, using a repository-root model path rather than the API process working directory.
- `python scripts/prepare_demo_vision.py --install` provides a one-command preparation/check for the OpenVINO runtime and checksum-verified model pair.
- Anonymous short-lived positional tracking integrated into the attendance runtime.
- Attendance returns time-synchronized anonymous candidate/confirmed/registered track boxes for the local review overlay; these session-local labels are not identities and non-authoritative fallback overlays remain diagnostic only.
- OpenVINO includes an overlapping 2×2 tiled inference mode plus an exact-clip calibration sweep for crowded/occluded fixed-camera scenes. On the manually counted five-worker industrial clip, the selected SIH demo profile is confidence 0.45 + tiled inference: stable occupancy 5/5, registered-count MAE 0.36 after warm-up, raw-count MAE 0.7143, zero detector failures, and a compliant decision when reported attendance equals the manual count. A live API rerun confirmed attendance 5/5 with 0% discrepancy and no case, while Practical Work remained authoritative with 5 peak stable workers, 2 active cells and no case. Held-out validation is still pending.
- Occupancy smoothing, reported-vs-observed discrepancy logic and temporal persistence.
- Camera-trust checks for darkness, blur, frozen feed and basic scene shift.
- Camera-integrity cases suspend attendance conclusions when the feed is not trustworthy.
- Evidence SHA-256 integrity metadata and perceptual duplicate-evidence detection.
- Attendance and infrastructure evidence paths anonymize detected person regions before central retention.
- Officer-review workflow with timestamped status-transition audit history.
- Structured case evidence-pack endpoint.
- Construction Electrician-LV (CON/Q0603) demo compliance manifest with current CSDCI V5 role/item-type provenance and quantities explicitly marked simulated.
- Infrastructure expected-vs-observed comparison with **Temporal Proof** using per-item persistence ratios.
- Evidence-backed infrastructure video pipeline using a replaceable cached/live detector adapter.
- Apparent-operability ROI motion proxy with ACTIVE / INACTIVE / UNCERTAIN states.
- Durable edge telemetry queue, executable offline edge agent, idempotent sync endpoint, dashboard sync visibility and bandwidth measurement utility.
- Final demonstration evaluator for attendance occupancy/cases, count-derived equipment precision/recall/F1 by class, apparent-operability coverage/accuracy, and overall/per-case-type compliance-case TP/FP/FN/TN with derived precision/recall/F1/FPR/FNR.
- Strict final-demo readiness validation for readable video metadata, ROI bounds, required scenario events, non-example final assets, OpenVINO selection/model assets, and manifest/cache alignment that excludes officer-only items.
- Privacy-preserving design note matching the PS conditional on individual identification.
- Next.js Command Centre connected to the live API.
- Practical-work verification now reuses the shared person-detector abstraction plus anonymous short-lived tracking; it can process clips without a hard Ultralytics dependency, while non-authoritative detector modes explicitly withhold the final conclusion.
- Held-out practical-work verification on the separate industrial unauthorized clip passed with the frozen calibrated OpenVINO profile: `unauthorized_practical_activity`, 6 peak stable workers, 3 active work cells, 54.39% practical-activity fraction, authoritative detector, zero detector failures, and a high-severity authorization case with retained privacy-transformed evidence.
- Practical-work fixed-camera zones are exposed by the API and rendered as video overlays; retained attendance/practical/infrastructure evidence is surfaced directly in verification/review screens with integrity metadata.
- Playwright browser flow covering attendance upload, case evidence, review, infrastructure evidence, operability state, evidence-pack retrieval **and synchronized edge-event visibility**.
- Isolated GroundingDINO environment/inference smoke test on a CC0 electrical-workroom image.

## Verified benchmark
EPFL Laboratory six-person sequence, Camera 0 only, 113 labelled frames, IoU 0.50:

| Detector | Precision | Recall | F1 | Occupancy MAE | Max count error |
| --- | ---: | ---: | ---: | ---: | ---: |
| HOG fallback | 43.82% | 9.11% | 15.09% | 3.000 | 6 |
| **OpenVINO person-detection-retail-0013** | **91.45%** | **89.95%** | **90.69%** | **0.327** | **2** |

See `docs/benchmarks.md` for methodology and limits.

## GroundingDINO status
The optional `IDEA-Research/grounding-dino-tiny` path now installs and performs inference successfully in its isolated GitHub Actions smoke workflow. On the CC0 electrical-workroom smoke image it returned six prompt-grounded detections at the configured smoke threshold. **This validates the inference path only; it is not equipment accuracy validation.**

GroundingDINO remains outside the core API dependency set and the stage demo retains a reviewed cached-detection fallback.

## Verified low-bandwidth architecture
- `edge/agent.py analyze` processes footage locally and queues sanitized compliance telemetry.
- `edge/agent.py sync` sends JSON events only after connectivity returns; raw video is not part of the sync request.
- Local evidence paths, identity data and raw frames are excluded from the central telemetry payload.
- The central API stores accepted edge events idempotently and the Command Centre exposes the synchronized-event count.
- Browser E2E verifies a synchronized edge event appears in the dashboard.

## Intentionally NOT claimed as complete
- Final equipment quality has **not** been measured on the exact controlled training-centre demo video.
- Current equipment **quantities** remain simulated. Current CSDCI V5 confirms relevant equipment types but its module equipment lists do not provide per-item sanctioned quantities; legacy PMKK quantity guidance is not being silently treated as current.
- Example final-evaluation rows are synthetic templates, not SIH accuracy results.
- Final compliance-case TP/FP/FN/TN has not yet been measured on the controlled demonstration dataset.
- Exact held-out attendance count accuracy on dynamic-occupancy footage has not yet been scored against timestamped manual annotations; a dedicated timestamped evaluator is now available so dynamic footage is not incorrectly reduced to one constant ground-truth count.
- Final low-bandwidth percentage has not yet been measured on the exact controlled demo clip.
- Apparent operability is visual activity evidence only, never mechanical/electrical health.
- Practical-work activity quality has not yet been benchmarked on the final controlled workshop clip. A HOG fallback may support preview metrics but remains non-authoritative and is displayed as a blocked/withheld verification state.
- The repository now contains the authoritative OpenVINO preparation path, but a deployed/demo backend is only authoritative after that runtime/model preparation has actually been run in the same environment that starts the API.
- AEBAS/SIDH integrations remain simulated because the prototype does not have production government credentials.

## Remaining final-demo milestones
1. Record/prepare the controlled fixed-camera training-centre demo described in `docs/final-demo-runbook.md`.
2. Run GroundingDINO offline on that exact clip, visually review the detections, and freeze the stage-safe cache.
3. Annotate the exact clip for attendance, equipment and apparent operability.
4. Run `evaluation/evaluate_final_demo.py` and report only the measured results.
5. Run the bandwidth measurement utility on the exact clip/events and report only the measured reduction.
6. If a current applicable source with explicit per-item quantities is obtained, attach it item-by-item; otherwise keep the demo quantities visibly simulated.
7. Validate the selected attendance tiled profile on at least one held-out fixed-camera clip, then freeze the presentation/demo configuration and perform the final browser rehearsal.
