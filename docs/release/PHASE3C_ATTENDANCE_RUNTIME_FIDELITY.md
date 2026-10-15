# Phase 3C — Frozen Attendance Runtime Fidelity

**Date:** 15 October 2026
**Scope:** Qualification integrity hardening, NOT a new real-world accuracy claim.

## Defect prevented

The original attendance held-out evaluator called the actual VideoCompliancePipeline with only sample cadence, count source, and smoothing window from the frozen candidate profile. Six other attendance options were supplied only by the pipeline's internal defaults: mismatch percentage, persistence ratio, trusted-camera ratio, track-confirmation seconds, registration warmup seconds, and track-grace seconds.

The baseline frozen profile happened to equal those defaults. No evidence shows that its previous numerical outcomes were wrong. But a later valid profile change could cause a held-out result to silently measure a different runtime configuration from the hashed profile named in the qualification receipt.

## Implementation

- One small runtime-options contract lists all nine frozen attendance settings and validates presence, numeric finiteness/bounds, accepted count source and positive smoothing window.
- The attendance registration warmup must equal the existing locked qualification policy's registration warmup. This prevents independent count annotations being sampled on a different warmup horizon from the actual pipeline.
- The loader validates settings before loading/claiming a real held-out protocol. The actual inference path forwards **all nine options explicitly** to the production video engine.
- Parameter-forwarding regression uses a mocked spy solely to test configuration. All synthesized fixtures remain explicitly NON-QUALIFYING.
- Model selection, threshold values, final accuracy policy, identity/security rules, privacy transformations, and Camera Trust PR #54 are unchanged.

## Qualification boundary

Independent lawful training-centre recordings, blinded labels and external attendance/authorization remain unavailable. The existing five-pillar readiness inventory stays blocked. Real held-out attendance metrics are not claimed by this hardening work. Running code/unit tests or prior EPFL research footage cannot promote the release.

**Required next:** institution-authorized untouched multi-centre recordings under pinned privacy controls, independent annotations, and evaluation on held-out splits frozen before model scoring.
