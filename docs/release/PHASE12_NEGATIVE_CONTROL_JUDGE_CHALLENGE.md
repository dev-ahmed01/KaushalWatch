# Phase 12 — Negative-control challenge and judge continuity

## Objective

Earlier development on selected UHCTD Day-3 footage measured the original basic Camera Trust scorer as marking 35 of 120 normal/pre-event samples untrusted and 60 of 144 annotated-event samples untrusted. These counts refer to a basic older score, NOT to the separated Phase-10 research worker, field accuracy, continuous-stream false alarm rates, or camera-malicious-tamper classification.

The current milestone deliberately does NOT tune numeric thresholds to make previously inspected footage look better. Instead it makes difficult normal and pre-event evidence visible in the SAME private research experience and hardens the judge walkthrough to require a legitimate quiet outcome.

## Source-verified private challenge

Phase 11 already established a localhost-only, source-hash matched numeric research trace and research annotator event windows. Phase 12 derives descriptive, per-window counts from that verified, memory-only trace:
- normal-control plus pre-event sample count;
- number of samples withholding visual evidence in those windows;
- number of **possible** scene-interference flags in those windows;
- corresponding counts for selected annotated event intervals.

These numbers are aggregated in the browser from the validated private trace. They are not invented static metrics, not a new model, and not an independent generalization estimate. The challenge panel is invisible when private trace evidence is absent.

A seekable 1-FPS source-quality strip overlays separate cues:
- amber: the numeric heuristic is not provisionally observable;
- blue-green: provisionally observable sample (not field-approved);
- bottom marker: source annotation window from the research CSV.

The displayed sample uses a PAST-ONLY cursor (the most recent recorded sample at or before the playback timestamp). A seek to 5.8 seconds cannot display a 6.0-second observation. A clip/source SHA mismatch suppresses the trace. No remote video, private path, annotation filename, IAM credential, or raw frame is served.

A single "Examine normal control" action switches from annotated event clip to the existing Day-3 normal-control video; the result can show warnings in apparently normal footage. This is a **challenge** to evaluate, not a scripted success story.

## Judge rehearsal acceptance

The existing 60-second manual rail is unchanged in duration and steps:
1. attendance example is a review candidate, not a fraud decision;
2. obstructed camera abstains (unknown, not zero);
3. equipment not-visible is not established absent;
4. normal control creates **no** invented case.

New Playwright tests carry that sequence end-to-end on actual Next/FastAPI demo routes and verify mobile containment. The private research panel remains behind localhost development admission.

## Test gates

Node tests exercise past-only sample lookup and normal/pre-event burden aggregation, including zero-event and high-warning negative controls. Browser E2E confirms the research challenge panel and normal-control shortcut, and the judge rehearsal remains stable with no fictional field result. Full backend, PostgreSQL, frontend, protected browser, OIDC and container CI still required.

This is a controlled software demonstration. No thresholds are fitted to these reused clips; external pilot acceptance remains blocked on Issue #91. Next evidence step is blinded new-site normal hours and actual annotated event footage.
