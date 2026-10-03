# Final Controlled Demo Runbook

Use `demo/scenarios/final-demo.example.json` as the checklist, then copy it locally and replace example values/timestamps with the exact recorded scenario.

## Camera
- One fixed camera only.
- Camera remains stationary throughout normal observations.
- Frame the people area and selected large equipment together where practical.
- Record the final ROI coordinates for the drill/activity proxy.

## Ground truth before recording
Write down:
- exact number of people physically present,
- simulated AEBAS/reported attendance,
- exact visible count of each demo equipment class,
- which equipment item is deliberately absent,
- which apparent-operability state is deliberately demonstrated,
- every compliance-case opportunity that should or should not create a case.

Never derive "ground truth" from the AI output after the fact.

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
2. Precompute/review GroundingDINO equipment observations.
3. Annotate attendance/equipment/operability ground truth.
4. Annotate compliance-case opportunities in `data/annotations/final-demo-cases.csv` using `evaluation/final_demo_cases.example.csv` as the schema.
5. Run `evaluation/evaluate_final_demo.py` with all four annotation files.
6. Run `evaluation/measure_bandwidth.py` on the exact clip/events.
7. Keep generated outputs under `evaluation/output/` (gitignored).
8. Copy only verified metric summaries into the SIH deck and `docs/benchmarks.md`.

## Stage safety
Before presentation, precompute the reviewed equipment cache for the exact video. Live equipment inference is optional; the evidence/case workflow must remain demoable using the cache.
