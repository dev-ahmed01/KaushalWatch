# Phase 3C — Attendance evidence sufficiency and safe abstention

**Date:** 15 October 2026  
**Scope:** Runtime correctness and risk reduction. Independent accuracy and pilot readiness are **NOT** qualified.

## Failure found

The attendance engine previously computed an internal zero occupancy when no trusted post-warmup counts existed. Its decision path could then fall through to `compliant`, even though no countable evidence supported that conclusion. Late raw detections that could not satisfy the frozen one-second confirmation requirement could also trigger an attendance discrepancy against a reported register. Phase 3C's already-inspected EPFL six-second example demonstrated exactly the latter temporal-coverage issue; no real fraud or competency inference is justified.

## Correction

A small post-warmup evidence gate now rejects:

1. No observations after the frozen registration warmup.
2. Trusted post-warmup coverage below the **existing** configured minimum trusted ratio.
3. Fewer than two usable post-warmup samples.
4. A usable post-warmup observation span shorter than the configured track confirmation (or registration) interval.
5. Raw person detections with no countable confirmed (or registered) tracks during the usable window.

The abstention decision is `attendance_evidence_insufficient`. Its summary withholds the official-seeming occupancy estimate and discrepancy percentage (`null`), retains only diagnosis-oriented sample traces and provides a reason plus post-warmup trust support. It produces **no attendance discrepancy case**. The existing `camera_integrity_exception` and `detector_unavailable` remain higher priority; neither is silently converted to `compliant`. Adequately observed genuinely empty views remain allowed to report zero. All frozen model, confidence, trust, confirmation and persistence parameters remain unchanged.

The held-out evaluator recognizes the new decision as a **case abstention** and withholds count accuracy scoring for insufficient-evidence scenes. Such abstentions lower case/count coverage instead of inflating true-negative claims.

## Verification

- Synthetic deterministic regressions cover no post-warmup data, late raw detections without confirmation, loss of post-warmup camera trust despite adequate global trust, and a sufficiently observed empty room.
- Synthetic held-out scoring verifies that an insufficient scene lowers coverage and may not report eligible count samples.
- The real, public EPFL six-second replay is explicitly required to abstain, while the unchanged 15-second replay must retain positive confirmed/smoothed occupancy.
- These tests **do not** establish held-out institutional detection accuracy, and the EPFL clip remains an inspected development baseline.

## Remaining boundaries

Independent authorized, blinded, multi-camera training-centre footage is not present. Camera Trust candidate PR #54 stays separate. Do not promote the release until all attendance, practical, camera-usability, equipment and apparent-motion heldout checks and production identity/storage controls are independently accepted.
