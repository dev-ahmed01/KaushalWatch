# KaushalWatch — SIH MVP Release Tracker

**Baseline:** `restructure/kaushalai-first-v1` at `c66a4eb447d682cfd85ad0b2ccec18267ba912eb` (PR #53, not merged to main).  
**Release branch:** `release/kaushalwatch-sih-mvp` (integration work only).  
**Excluded research branch:** `fix/uhctd-camera-trust-v2` (draft PR #54, not merged).  
**Release objective:** one reproducible, privacy-preserving and evidence-backed officer workflow. Five primary demo centres. No punitive or identity-level conclusions from unsupported visual evidence.

## How progress is measured

Five release milestones, with checkboxes for **evidence-backed acceptance criteria**, not percentages inferred from commit count. The earlier 85% demo / 55% pilot / 35% government estimates are historical planning opinions, not independently measured completion percentages.

A task is DONE only if its acceptance evidence is recorded and applicable tests pass. CI and the synthetic demo are necessary but not sufficient for the final-stage-video gate.

### Milestone 1/5 — Scope freeze, contracts, integration

- [x] Confirm main and AI-first branch relationship; PR #53 is unmerged and 143 commits ahead of main.
- [x] Inspect Camera Trust draft PR #54 and isolate its unvalidated detection changes from release baseline.
- [x] Audit `README.md`, `STATUS.md`, build workflow and available runtime modules for claim boundaries.
- [x] Catalogue current UI-to-API route contracts; introduce a fail-fast, read-only route/method drift check.
- [x] Get the **new release branch CI** passing (backend, static contract gate, frontend build, browser E2E). Release branch PR #55 had a full successful CI run at commit `7acbd329`; subsequent CI for the new isolated release tests must also pass before these are certified.
- [ ] Complete an exact clean-environment operator bootstrap, including required model/runtime preparation.
- [ ] Verify full officer roles/permissions and all negative-state transitions on a running candidate; an optional server-mapped reviewer write key is now implemented, but complete RBAC and sensitive read protection remain pending.
- [ ] Trace an **actual selected stage video** -> analysis -> persisted evidence -> case -> officer action -> audit -> assistant. A separate synthetic-video API-level integration test now covers this path using generated black camera footage and no external model accuracy claims; exact stage media remain pending.

**Exit gate:** all 8 items checked; no critical officer-path blocker, and the release base remains unmerged.

### Milestone 2/5 — Final demo assets and annotation

**Engineering gate implemented (not final-media acceptance):** `scripts/verify_release_assets.py`, `backend/app/services/release_assets.py` and `backend/tests/test_release_assets.py` check five clip roles, independent annotation CSV schema, SHA-256 source integrity, reviewer attestations, source/privacy/licensing metadata, camera-cut-safe ROI, and reviewed equipment cache binding. `check_demo_readiness.py --final` and `run_final_demo_rehearsal.py --final` now refuse missing or mismatched frozen assets. The checked-in `demo/release-assets.example.json` is intentionally incomplete and **cannot** pass final qualification. See `docs/release/final-media-freeze.md`.


- [ ] Freeze exact attendance clip and its annotated reported/observed counts.
- [ ] Freeze practical-work clip, zones, authorization inputs, and held-out labels.
- [ ] Freeze infrastructure source clip; verify SHA-bound reviewed DOD cache and equipment manifest align to the same footage.
- [ ] Freeze apparently-operating equipment ROI/time window, excluding any camera cuts.
- [ ] Select a conservative degraded-camera review clip without claiming unvalidated tamper recall.
- [ ] Record clip licenses, source URLs, immutable digests, privacy basis and scenario-to-centre mappings.
- [ ] Confirm all referenced video files are available **locally**, not committed to Git.

**Exit gate:** reproducible scenario, hash-matched reviewed data and independent annotations for every claimed metric.

### Milestone 3/5 — Defensible final evaluation

**Practical activity + external authorization receipt implemented (synthetic verification only):** `PracticalActivityPipeline.run(observation_sink=...)` optionally emits a frame-complete, privacy-safe timeline from the actual camera-trust, anonymous tracking, registration and zone-motion gates. `evaluation/practical_activity_trace.py` requires an exact frozen clip, SHA-pinned work-zone profile, pipeline parameters, and a separate SHA-frozen operator-reviewed **external authorization record**; qualifying capture requires OpenVINO. The final scorecard accepts `--practical-receipt` and optional `--practical-case-sample-id`; it verifies decoded frame SHA and complete sampling cadence, model/profile/authorization artifacts, activity fractions and final case type, rejecting low-trust video and unknown authorization as binary compliance outcomes. **This is not proof of the official schedule/authorization's accuracy, nor a field benchmark or a validated legal violation.** Tests use only synthetic fixtures. See `docs/release/practical-activity-trace.md`.


**Apparent-operability motion replay implemented (not a physical-health test):** `backend/app/services/operability.py:trace_apparent_motion` is now the single shared ROI sampling/measurement function for the infrastructure case and independent evaluator. `evaluation/operability_motion_trace.py` runs it against the exact frozen operability clip, ROI, window, item, threshold and frame cap; it retains decoded-frame SHA-256 values but no pixels. The `--operability-receipt` option on the final scorecard re-decodes the video and verifies the complete receipt and the sole bound annotation row before writing. Synthetic CI covers case-path parity, changed videos/labels/windows and receipt tampering. `equipment_mechanical_health_verified=false` is explicit, and independent real-footage labels and representative active/inactive/uncertain coverage remain pending. See `docs/release/operability-motion-trace.md`.


**Equipment reviewed-cache prediction trace implemented (NOT live detector validation):** `evaluation/equipment_cache_trace.py` binds equipment scoring opportunities to exact second/item entries of the SHA-frozen GroundingDINO review cache, its reviewed metadata and the exact DOD source hash. It explicitly separates `model_count` original proposals from human-corrected `count`, refusing ambiguous timestamps, missing review attestations or blended scoring bases. `evaluation/evaluate_final_demo.py --final --equipment-receipt ...` revalidates the receipt before writing a report. `model_inference_execution_verified=false` by design: we have **not** rerun the source GroundingDINO model or proved those cached proposals came from the recorded weights. Independent annotations, final video presence and any box-localization scores remain outstanding. See `docs/release/equipment-cache-trace.md`.


**Whole-video attendance case matching implemented (synthetic CI only):** `evaluation/attendance_case_decision_verification.py` checks a single explicit `attendance_discrepancy` opportunity against the full privacy-safe decision timeline and frozen clip/centre/batch/reported-count mapping, then independently recomputes trust ratio, warmup eligibility, median occupancy, mismatch persistence, and the attendance exception. This cannot score a camera-insufficient video as a compliant attendance negative and refuses counting the same source clip twice. Final scorecards accept `--attendance-case-sample-id` only with an operational receipt. See `docs/release/attendance-case-decision-trace.md`. It is **not** evidence that the entire multi-type case confusion matrix is inference-grounded.

**Operational attendance pipeline trace implemented (not yet validated on the final real clips):** `VideoCompliancePipeline.run(observation_sink=...)` emits an optional privacy-safe sample trace from the same detector, tracker, registration/smoothing and mismatch pass used by the product. `evaluation/capture_operational_attendance.py` verifies frozen inputs and OpenVINO model/profile hashes and explicitly withholds untrusted, warmup or unavailable samples. `evaluation/evaluate_final_demo.py --final --operational-attendance-receipt ...` checks decoded frame hashes, sample/frame alignment, model files, predicted smoothed counts and eligible per-sample mismatch flags. CI tests are synthetic. The unsigned receipt does not establish independent ground-truth or final officer case metrics. See `docs/release/operational-attendance-trace.md`.

**Attendance frame prediction trace implemented (not a real benchmark):** `evaluation/capture_attendance_inference.py` can run the frozen source through the actual OpenVINO person detector at independently selected zero-based `frame_index` samples, preserving source/model/profile hashes and withholding untrusted camera frames. `evaluation/evaluate_final_demo.py --final --attendance-receipt ...` rejects mismatched raw counts or model artifacts. This is **raw frame count only**, not tracker/registration attendance or proof that other columns were generated by the engine. Tests use explicitly nonqualifying synthetic detectors. See `docs/release/attendance-inference-trace.md`. Actual filmed clips, true count annotations and live OpenVINO runs are still pending.

**Scorecard-engineering checks implemented (not actual measured results):** `evaluation/final_scorecard_guard.py` and `evaluation/evaluate_final_demo.py --final --asset-manifest` now bind every input CSV to the local frozen media manifest, validate sample uniqueness and scoring domains, and record file/manifest SHA-256 provenance. Development-mode reports are explicitly marked unqualified. Undefined precision, recall, false-positive rates and abstention-only operability accuracy are `null`, not fabricated zeros. Crucially, frozen prediction columns **do not by themselves prove a particular model generated them**. See `docs/release/frozen-scorecards.md`.

- [ ] Run frozen OpenVINO profile on exact target/hold-out clips; record occupancy MAE, count agreement and evidence trust.
- [ ] Evaluate practical-work case outputs against pre-labelled, independent ground truth.
- [ ] Evaluate equipment per-class TP/FP/FN and report coverage, including classes absent from the clip.
- [ ] Evaluate apparent-operability visual proxy as ACTIVE/INACTIVE/UNCERTAIN, not machinery health.
- [ ] Evaluate compliance case TP/FP/FN/TN including **negative case opportunities**.
- [ ] Measure camera visibility/insufficient-evidence outcomes without promoting experimental displacement metrics.
- [ ] Measure offline payload/bandwidth against the exact video; verify duplicate delivery is idempotent.
- [ ] Publish observed results, reproducible commands and known limits; leave unsupported claims pending.

**Operator command (after final asset qualification, not on placeholder data):** `python evaluation/evaluate_final_demo.py --final --asset-manifest demo/release-assets.local.json --attendance data/annotations/attendance.csv --equipment data/annotations/equipment.csv --operability data/annotations/operability.csv --cases data/annotations/cases.csv --out-dir evaluation/output/final-demo`.

**Exit gate:** every presented metric has a labelled source, exact configuration and reproducible result.

**Edge history retry idempotence (single-worker synthetic CI):** `AnalysisHistoryStore.append_edge_once` locks and atomically writes analysis rows with a unique edge event ID. If history persisted but the edge receipt ledger failed, a retry returns the prior history row rather than adding a duplicate. Corrupt history JSON fails closed instead of being replaced by an empty history. Tests inject receipt-ledger crashes and interrupted audit writes. This closes a known **single-worker repeat-history gap**, but there is still no cross-store distributed transaction or exactly-once guarantee across independent server processes.

**Camera-insufficient + offline sync release safety (implemented, synthetic CI only):** Edge attendance summaries now report `blocked` when camera trust or detector evidence is insufficient; the central ingestion layer independently normalizes unverified `compliant` claims against the declared decision, trusted ratio, authoritative detector and failure count. Incoming events are normalized to bounded aggregate fields and sanitized evidence SHA digests; raw-video/identity payloads and unsupported event types are rejected. Protected environments require a server-configured device token; local demo mode is development-only. Edge queues and receipt ledger use atomic replace plus per-process locks, and duplicate sync cannot overwrite an officer-reviewed case. Test cases cover privacy, race/replay, interrupted writes, invalid acknowledgements and staging authentication. **Not** a cryptographically authenticated model or a multi-process exactly-once event stream. See `edge/README.md`.

### Milestone 4/5 — End-to-end officer journey

**Protected API/evidence boundary (engineering implemented, protected browser UI not complete):** `backend/app/services/protected_access.py` requires a server-mapped officer bearer key for every sensitive `/api/` route, `/evidence/` frame, PDF/report path and API schema in staging/pilot/production. Only health, limited review-access status and independently device-authenticated edge sync remain exempt. Unknown/misspelled deployment environments fail closed. These checks are tested on synthetic keys and cases in `backend/tests/test_protected_data_boundary.py`. **The existing Next.js UI has no login/session BFF for protected reads and images; it will deliberately be blocked in protected mode. This is a data-exposure safety gate, not pilot readiness.** See `docs/release/protected-data-access.md`.

**Evidence-path privacy on API JSON (implemented, synthetic test coverage):** The server strips local `frame_path` and raw/local video path keys recursively from case listings, evidence review packs, case-review results, dashboards and upload response JSON. Opaque evidence IDs/SHA remain for supported client views; original internal paths remain for audit integrity and recovery. `backend/tests/test_api_evidence_redaction.py` and the updated synthetic officer journey verify this distinction. This is an additional data-minimization safeguard, not a guarantee that arbitrary unreviewed metadata can never contain sensitive content.

**API attendance disposition fail-closed:** `/api/process-video` now requires the whole-video decision, authoritative detector, zero detection failures and enough trusted samples before writing `compliant` to analysis history. Previously detector authority alone could be mistaken for clean attendance. `backend/tests/test_attendance_api_fail_closed.py` exercises eight synthetic cases without claiming model accuracy.



**Atomic officer outcomes + browser failure states implemented (synthetic CI):** the case store and review API can now process an open-to-final decision with *one* atomic JSON replacement while preserving both audit transitions. The case page sends a single POST, preventing a failed final request from leaving a half-updated officer review. Concurrency, disk-interruption and key-denial tests are in `backend/tests/test_atomic_review_action.py`. Browser tests in `web/e2e/offline-integrity.spec.ts` exercise one-click confirmation/audit reload, network failures, offline action-queue recovery and camera-trust uncertainty. Evidence screens no longer interpret missing camera-trust measurement as a positive trust observation. Note: this is a **single-process prototype atomicity guarantee**, not pilot-grade distributed audit storage.


- [ ] Browser test: select centre -> monitor -> analyze/inspect -> discrepancy -> anonymized evidence.
- [ ] Browser test: officer reviews -> decision persisted -> audit trail -> escalation if warranted.
- [ ] Browser test: Insights, report export, history and evidence-grounded KaushalAI answer.
- [ ] Failure matrix: no clip, unreadable clip, low confidence, provider unavailable, backend failure, duplicate evidence, permission denied, offline sync failure.
- [ ] Ensure simulated vs measured vs unavailable is always visibly distinct across the journey.
- [ ] Confirm responsive/mobile and keyboard navigation without blocking overlays or silent dead ends.

**Exit gate:** recorded E2E passing run on the candidate and no unresolved critical failures.

### Milestone 5/5 — Reproducible release/rehearsal

**Synthetic recovery rehearsal tooling implemented (not judge-machine acceptance):** `scripts/demo_recovery.py` snapshots only clearly simulated cases, histories, approved evidence images and offline queue/settings with an allowlisted ZIP manifest and SHA-256 digests, excluding raw footage. Restore requires a *new* directory, checks every archive entry and rebases verified evidence paths. `backend/tests/test_demo_recovery.py` checks restored audit/event/evidence continuity, archive tampering, path traversal and non-simulated input refusal. See `docs/release/demo-recovery-runbook.md`. The release still requires a real clean-environment operator rehearsal and real-footage validation before final signoff.


- [ ] Clean checkout installation instructions and environment template work on the demo machine.
- [ ] One-command model/profile preparation and readiness outcome are recorded.
- [ ] Seed preparation is deterministic, reversible and visibly simulated.
- [ ] Final video, scenario, manifest, annotation and evidence checks pass.
- [ ] Full judge walk-through and recovery/fallback rehearsal passes.
- [ ] Record tag/commit, startup commands, limitations, metrics and operator guide.
- [ ] Leave PR open for human approval; do not merge main automatically.

**Exit gate:** a reviewer can reproduce the demo from documented assets and commands.

## Source-audited feature status (not full system certification)

| Feature | Source-audited state | Required final verification |
| --- | --- | --- |
| AI-first shell, five centres, Insights, Actions | Implemented with responsive browser E2E on PR #53 | Candidate browser run |
| FastAPI, analysis history, case/evidence persistence, officer review | Implemented: atomic audit, mapped officer write actor; staging/pilot API/evidence read boundary rejects unauthenticated requests | Secure browser sessions, scoped RBAC, transactional database, real officer vertical slice |
| Frozen OpenVINO attendance profile | Benchmarked on *limited* EPFL Camera 0 sequence | Exact demo clip and held-out counts |
| Practical activity | Development held-out unauthorized example in `STATUS.md` | Stage clip/zone labels and independent benchmark |
| Infrastructure presence | Reviewed DOD cache with SHA-256-bound source | Source availability, exact hash, formal per-class evaluation |
| Apparent operability | Motion proxy, not machinery-health proof | Annotated ROI/window measurement |
| Camera Trust | Basic checks included in baseline; experimental v2 isolated | Conservative insufficient-evidence/officer handling |
| AEBAS / SIDH | Simulated | Do not claim government live integration |
| Edge queue and sync | Implemented; new tests verify same-event replay, different-event same-case suppression and non-overwrite of officer audit | Offline reconnection + exact bandwidth measurement |
| KaushalAI text/voice | Mocked contract tests and UI path | Real provider credentials/connectivity on presentation environment |
| Evaluation and demo utilities | Scripts exist and synthetic smoke runs documented | Final ground truth, exact assets and real outputs |

## Critical boundaries and known blockers

1. **Final media are not shipped in Git.** The repository has a reviewed DOD equipment cache and example annotations, not a complete versioned set of real demonstration videos.
2. **Equipment quantities are simulated.** Source documentation covers job-role equipment types, not validated per-item sanctioned quantities. The new asset verification can confirm source consistency, but does not validate the sanctioned quantity specification or accuracy.
3. **Formal equipment and overall case metrics are pending.** A synthetic example CSV is not a model accuracy benchmark. The evaluator now distinguishes example-mode math from SHA-bound final-input scoring; actual inference provenance, independent timestamped annotations and correct negative-case opportunities still require evidence.
4. **Camera Trust experimental PR #54 is not promotion-ready.** It includes promising selected-event results alongside previously observed severe false alarms; do not merge based solely on CI.
5. **Provider readiness is environment-dependent.** Gemini/Groq calls need operator keys and a live test; typed/offline monitoring must remain usable without them.
6. **Privacy/authority:** automated visual findings are review inputs; unknown visibility cannot become a healthy or punitive conclusion.
7. **Officer identity and protected data:** `docs/release/officer-review-access.md` covers server-side mapped bearer-key actor attribution; `docs/release/protected-data-access.md` covers the new all-sensitive-route read/write/evidence denial in staging/pilot/production. Only explicitly local environments can use demo access; unknown settings fail closed. **This is not full RBAC, and the browser lacks a protected-session/login proxy**. Every valid bearer key currently has broad demo-centre access, so government/real-centre deployment remains out of scope.
8. **Durable case status:** an edge event with an existing case ID no longer overwrites that case (even under a different event ID); untrusted edge source statuses are never treated as human decisions. `CaseStore` writes now use in-process locking and atomic file replacement. These controls do **not** provide multi-process transactions, signed edge event provenance, or a production audit ledger.

## Release checks

From repository root:

```bash
python scripts/check_repo_hygiene.py
python scripts/validate_vision_profile.py
python scripts/check_release_readiness.py
python scripts/check_frontend_api_contracts.py
pytest -q backend/tests
cd web && npm ci && npm run build && npm run test:e2e
```

The **route contract gate** verifies 22 required frontend helper ↔ FastAPI route/method pairs without starting a model or API. It does not validate JSON schemas, permissions, HTTP behavior, provider readiness or vision accuracy. The existing CI includes backend and Playwright testing for those supported integration paths. New backend tests now also exercise a **synthetic** camera-upload → privacy evidence → persisted camera-review → actor-audited officer action → Insights/report/non-provider assistant path. See `docs/release/officer-journey-smoke.md`. This is integration verification, not an accuracy evaluation.

On the judge machine, after safely configuring local assets and provider credentials, also run:

```bash
python scripts/verify_release_assets.py --manifest demo/release-assets.local.json
python scripts/prepare_demo_vision.py --install
python scripts/check_demo_readiness.py --video <exact-primary-source-clip> --final --asset-manifest demo/release-assets.local.json
python scripts/run_final_demo_rehearsal.py --video <exact-primary-source-clip> --final --asset-manifest demo/release-assets.local.json
```

Do **not** execute `prepare_demo_state.py --yes` on a runtime with unsaved officer work: that action resets the mutable demo seed. Keep actual footage, local model binaries, generated evaluation reports and credentials out of source control.

## Officer journey to sign off

**KaushalAI -> Centres -> Centre intelligence -> Analyze/inspect -> Evidential discrepancy -> Anonymized proof -> Officer case review -> Persistent audit -> Actions/escalation -> Insights/report -> Grounded assistant follow-up.**

The initial baseline PR #53 recorded 14/14 passing browser tests and green CI. This records historical baseline verification only. The release branch needs its **own** successful CI, plus the final-media and live-environment gates above before it can be called SIH-ready.
