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
- OpenVINO includes an overlapping 2×2 tiled inference mode plus an exact-clip calibration sweep for crowded/occluded fixed-camera scenes. The final SIH attendance demo profile is now frozen at confidence 0.45 + tiled inference + confirmed-track occupancy + 3-sample median. On the manually counted five-worker calibration clip it returns 5/5, 0% discrepancy, `compliant`, no case, 100% trusted samples and zero detector failures. On the separate dynamic held-out clip, smoothed-count MAE improved from 1.5556 to 0.6667 and exact-count rate from 22.22% to 55.56% without changing detector confidence or the 15% compliance threshold.
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
- Apparent-operability ROI motion proxy with ACTIVE / INACTIVE / UNCERTAIN states, including optional scenario/API time windows so camera cuts can be excluded from the motion score without trimming the source evidence video.
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
- GroundingDINO final-clip precompute now supports automatic duration-safe sampling, prompt overrides, metadata sidecars and annotated review JPGs so short clips can be human-reviewed before cache promotion.\n- The DOD_110930728 electrical-training clip has now been run through GroundingDINO on seven wide-shot timestamps and human-reviewed: one workbench and one training panel were accepted, chairs/drill were confirmed absent, and the 10 s drill proposal was rejected as a false positive. The reviewed cache preserves raw model confidence separately from review confidence and is SHA-1-bound to the exact source clip.

- Single-agent Kaushal Assistant with direct analysis/case/readiness tools, bounded multi-turn memory, structured source links, and configuration-safe failure states. The agent uses Gemini 3.8 Flash through Google's OpenAI-compatible endpoint; voice uses Groq Whisper Large V3 Turbo and Orpheus with WAV playback. Provider calls are contract-tested with mocks; live free-provider verification still requires operator-supplied `GEMINI_API_KEY` and `GROQ_API_KEY`.

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
- Formal equipment precision/recall has **not** yet been measured. The DOD_110930728 infrastructure clip has been human-reviewed for stage use, but that review is not a substitute for a labelled equipment benchmark.
- Current equipment **quantities** remain simulated. Current CSDCI V5 confirms relevant equipment types but its module equipment lists do not provide per-item sanctioned quantities; legacy PMKK quantity guidance is not being silently treated as current.
- Example final-evaluation rows are synthetic templates, not SIH accuracy results.
- Final compliance-case TP/FP/FN/TN has not yet been measured on the controlled demonstration dataset.
- Held-out dynamic attendance remains a small, scene-specific evaluation: with the frozen confirmed-track + 3-sample median profile, smoothed-count MAE is 0.6667, median absolute error 0, max absolute error 3, mean bias -0.4444, and exact-count rate 55.56% across the nine post-warm-up annotated timestamps. These values are not a general CCTV benchmark.
- Final low-bandwidth percentage has not yet been measured on the exact controlled demo clip.
- Apparent operability is visual activity evidence only, never mechanical/electrical health.
- Practical-work activity quality has not yet been benchmarked on the final controlled workshop clip. A HOG fallback may support preview metrics but remains non-authoritative and is displayed as a blocked/withheld verification state.
- The repository now contains the authoritative OpenVINO preparation path, but a deployed/demo backend is only authoritative after that runtime/model preparation has actually been run in the same environment that starts the API.
- AEBAS/SIDH integrations remain simulated because the prototype does not have production government credentials.

- Kaushal Assistant conversation memory is process-local for V1; API restarts or multiple workers do not share sessions. Named-worker answers are unavailable because the privacy-preserving vision pipeline does not retain worker identity.

## Remaining final-demo milestones
1. Keep the frozen attendance/practical clips and the reviewed DOD infrastructure clip mapped to their exact demo steps.
2. Annotate the exact stage clips for attendance, equipment and apparent operability.
3. Run `evaluation/evaluate_final_demo.py` and report only the measured results.
4. Run the bandwidth measurement utility on the exact clip/events and report only the measured reduction.
5. If a current applicable source with explicit per-item quantities is obtained, attach it item-by-item; otherwise keep the demo quantities visibly simulated.
6. Run the final browser rehearsal with the exact stage assets and preserve the claim boundaries above.
