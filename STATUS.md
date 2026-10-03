# Build Status

**Verification checkpoint:** core backend tests, final-evaluator smoke test, Next.js production build, Playwright browser E2E, EPFL detector benchmark, and isolated GroundingDINO image smoke inference all pass on the active core build.

This file is the source of truth for what is verified, scaffolded, or still pending.

## Verified in the current core build
- FastAPI API, CORS, evidence serving and persisted compliance cases.
- Video upload vertical slice.
- **OpenVINO person-detection-retail-0013 selected from the real EPFL Laboratory Camera 0 benchmark.**
- Anonymous short-lived positional tracking integrated into the attendance runtime.
- Occupancy smoothing, reported-vs-observed discrepancy logic and temporal persistence.
- Camera-trust checks for darkness, blur, frozen feed and basic scene shift.
- Camera-integrity cases suspend attendance conclusions when the feed is not trustworthy.
- Evidence SHA-256 integrity metadata and perceptual duplicate-evidence detection.
- Attendance and infrastructure evidence paths anonymize detected person regions before central retention.
- Officer-review workflow with timestamped status-transition audit history.
- Structured case evidence-pack endpoint.
- Construction Electrician - LV (CON/Q0603) demo compliance manifest with quantities explicitly marked simulated.
- Infrastructure expected-vs-observed comparison with **Temporal Proof** using per-item persistence ratios.
- Evidence-backed infrastructure video pipeline using a replaceable cached/live detector adapter.
- Apparent-operability ROI motion proxy with ACTIVE / INACTIVE / UNCERTAIN states.
- Durable edge telemetry queue, idempotent sync endpoint and bandwidth measurement utility.
- Final demonstration evaluator for attendance cases, equipment counts and apparent-operability coverage/accuracy.
- Privacy-preserving design note matching the PS conditional on individual identification.
- Next.js Command Centre connected to the live API.
- Playwright browser flow covering attendance upload, case evidence, review, infrastructure evidence, operability state and evidence-pack retrieval.
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

## Intentionally NOT claimed as complete
- Final equipment quality has **not** been measured on the exact controlled training-centre demo video.
- Current equipment quantities in the demo manifest remain simulated until the applicable official specification table is verified item-by-item.
- Example final-evaluation rows are synthetic templates, not SIH accuracy results.
- Final compliance-case TP/FP/FN/TN has not yet been measured on the controlled demonstration dataset.
- Final low-bandwidth percentage has not yet been measured on the exact controlled demo clip.
- Apparent operability is visual activity evidence only, never mechanical/electrical health.
- AEBAS/SIDH integrations remain simulated because the prototype does not have production government credentials.

## Remaining final-demo milestones
1. Record/prepare the controlled fixed-camera training-centre demo described in `docs/final-demo-runbook.md`.
2. Run GroundingDINO offline on that exact clip, visually review the detections, and freeze the stage-safe cache.
3. Annotate the exact clip for attendance, equipment and apparent operability.
4. Run `evaluation/evaluate_final_demo.py` and report only the measured results.
5. Run the bandwidth measurement utility on the exact clip/events and report only the measured reduction.
6. Verify or replace remaining simulated manifest quantities where an applicable official lab specification is available.
7. Freeze presentation/demo configuration and perform the final browser rehearsal.
