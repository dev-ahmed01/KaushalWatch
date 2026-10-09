# Final Controlled Demo Runbook

Use `demo/scenarios/final-demo.example.json` as the checklist, then copy it locally and replace example values/timestamps with the exact recorded scenario.

## Camera
- One fixed camera only.
- Camera remains stationary throughout normal observations.
- Frame the people area and selected large equipment together where practical.
- Record the final ROI coordinates for the drill/activity proxy.
- If the source clip contains a hard scene cut, keep that cut outside the operability interval and record the stable interval as `operability_window`; equipment-presence sampling may still use the wider clip.

## Ground truth before recording
Write down:
- exact number of people physically present,
- simulated AEBAS/reported attendance,
- exact visible count of each demo equipment class,
- which equipment item is deliberately absent,
- which apparent-operability state is deliberately demonstrated,
- every compliance-case opportunity that should or should not create a case.

Never derive "ground truth" from the AI output after the fact.

For clips where only part of the video is stable enough for the ROI-motion proxy, add:

```json
"operability_window": {
  "start_sec": 14.0,
  "end_sec": 33.0
}
```

The infrastructure pipeline will then use the full reviewed detector cache for equipment presence while restricting apparent-operability motion scoring to that stable interval.

## Required sequences
1. Normal trustworthy camera view.
2. Persistent attendance mismatch.
3. Persistent missing-equipment condition.
4. Visible activity inside one equipment ROI.
5. Camera obstruction/tamper condition.
6. Offline event queue + later sync.
7. Duplicate-evidence test through the test path.

Record at least one **negative case opportunity** for the case types you want to score. For example, include a trustworthy interval where attendance matches the reported value, an infrastructure interval with no persistent deficit, and a healthy camera interval. Without negative opportunities, final FP/TN/FPR measurements are not meaningful.

## After recording
1. Save raw footage locally under `data/raw/` (gitignored).
2. Precompute GroundingDINO equipment observations with automatic in-bounds timestamps and inspect every generated review image before promoting the cache.
3. Annotate attendance/equipment/operability ground truth.
4. Annotate compliance-case opportunities in `data/annotations/final-demo-cases.csv` using `evaluation/final_demo_cases.example.csv` as the schema.
5. Run `evaluation/evaluate_final_demo.py` with all four annotation files.
6. Run `evaluation/measure_bandwidth.py` on the exact clip/events.
7. Keep generated outputs under `evaluation/output/` (gitignored).
8. Copy only verified metric summaries into the SIH deck and `docs/benchmarks.md`.

## Stage safety
Before presentation, precompute the reviewed equipment cache for the exact video. Live equipment inference is optional; the evidence/case workflow must remain demoable using the cache.


## Equipment clip suitability gate

Before treating equipment metrics as final, confirm that the exact camera view genuinely contains the manifest classes you intend to score. Attendance/practical-work footage can still be useful even when it is not an appropriate Construction Electrician infrastructure scene. Do not turn unrelated industrial machinery into a "training panel" or "drill machine" merely to obtain a positive detection.


## Judge-day release sequence

Run these from the repository root before the UI walkthrough:

```bash
python scripts/prepare_demo_state.py --yes
python scripts/validate_vision_profile.py
python scripts/check_release_readiness.py
```

Then start the calibrated backend:

```bash
python scripts/start_demo_backend.py
```

In a second terminal:

```bash
cd web
npm run dev
```

The release-readiness command is non-destructive: it creates its own temporary runtime state and verifies the five-centre AI-first scope, deterministic network states, action ranking, duplicate-evidence fixture and frozen vision profile.

The `prepare_demo_state.py --yes` command clears only mutable runtime files (`cases.json`, `analysis_history.json`, `centre_settings.json`, `edge_events.json`, `evidence_index.json` and generated `data/evidence/` contents) and writes the marked-simulated judge seed. It **does not** delete `data/raw/`, manifests or reviewed detector assets.

Expected **primary five-centre** story after preparation:
- Bengaluru TC-04 — NEEDS REVIEW (attendance)
- Mysuru TC-12 — VERIFIED
- Tumakuru TC-07 — UNCERTAIN (camera integrity)
- Hubballi TC-03 — NEEDS REVIEW / regional escalation (infrastructure)
- Belagavi TC-09 — VERIFIED

A legacy Mangaluru unavailable fixture remains in backend demo data for compatibility testing, but it is intentionally excluded from the redesigned KaushalAI/Centres/Insights/Actions primary scope.

The prepared seed includes synthetic integrity evidence only for demonstrating SHA-256 and duplicate detection. It is watermarked and tagged simulated; it must never be described as real centre footage.

### Strict real-video gate

Preparing the UI seed and passing the release-readiness check do **not** validate the final camera footage or create accuracy claims. Start by freezing every actual clip, all four independently labelled CSVs, equipment-cache/source SHA, camera-cut-safe ROI, copyright/privacy basis and centre/batch mappings using `docs/release/final-media-freeze.md`.

When the authoritative OpenVINO runtime and exact reviewed demo video are present, run:

```bash
python scripts/verify_release_assets.py --manifest demo/release-assets.local.json
python scripts/check_demo_readiness.py --video <exact-video> --final --asset-manifest demo/release-assets.local.json
```

For the reviewed DOD infrastructure clip, the SHA-bound equipment cache must continue to match the exact source video.

### 60-second judge path

1. **KaushalAI** — explain what changed and which centre needs attention first.
2. **Centres → Bengaluru** — show the six verification engines and Activity timing.
3. **Evidence** — show Reported vs Observed, Temporal Proof, SHA-256 and duplicate handling.
4. **Officer review** — record a decision and show the persistent audit trail.
5. **Insights** — show attendance variance, activity heatmap, camera trust and report exports.
6. **Actions** — show why Hubballi ranks first, then Tumakuru, Bengaluru attendance and the low-activity follow-up.
7. **Run analysis** — expand Technical details only if asked; show the frozen vision profile and runtime alignment.

Close with: **“Track position, not identity. Missing or untrusted evidence never becomes a verified conclusion. AI surfaces evidence. Officers decide.”**
