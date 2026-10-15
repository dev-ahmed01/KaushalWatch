# Phase 3C — Five-pillar held-out cohort admission

**Date:** 15 October 2026  
**Scope:** Strict read-only metadata, provenance and split-contamination preflight. **Not a model evaluation; not accuracy qualification.**

## What changed

Individual evaluators already require a frozen manifest, pinned files and independent held-out annotations for attendance, practical activity, camera evidence, equipment and visible ROI motion. However, their calibration-vs-heldout separation was checked independently **within each evaluator**. A recording could inadvertently train/tune one subsystem while being called "untouched" by another, even if individual reports were green.

The attendance evaluator also lacked the explicit \`previously_inspected: false\` attestation already required by the other four evaluators. It now requires that field for held-out recordings and refuses known previously inspected development media (EPFL, WiseNET, UHCTD, MEVA, DOD_110930728). Marker checks and human attestations are warning barriers, **not** proof that footage was actually unseen.

## New metadata-only gate

Run after an institutional dataset has been lawfully prepared **outside Git**:

    python evaluation/holdout_cohort_preflight.py \
      --manifest "D:\private\cohort\frozen-cohort.json" \
      --out "D:\private\cohort\cohort-preflight-result.json"

Use PowerShell continuation/backtick for multi-line Windows commands, or keep the command on one line. The output contains no source paths, human names, images or annotation rows. A successful metadata-only result has status \`metadata_preflight_passed_not_accuracy_qualified\` and **always** \`qualified: false\`.

The parent frozen cohort manifest schema is:

    {
      "schema_version": 1,
      "status": "frozen",
      "fixture_only": false,
      "pillars": {
        "attendance": {"path": "attendance.json", "sha256": "<actual 64-char SHA-256>"},
        "practical_activity": {"path": "practical.json", "sha256": "<actual 64-char SHA-256>"},
        "camera_evidence": {"path": "camera.json", "sha256": "<actual 64-char SHA-256>"},
        "equipment": {"path": "equipment.json", "sha256": "<actual 64-char SHA-256>"},
        "roi_motion": {"path": "motion.json", "sha256": "<actual 64-char SHA-256>"}
      }
    }

The SHA placeholders above are explanatory only and are never accepted by the tool. Each referenced pillar file must itself be frozen, declare \`fixture_only: false\`, have nonempty calibration and heldout arrays, and contain pinned \`video.path\` + \`video.sha256\` references on each scene. Each scene needs consistent recording/site/camera/scene IDs and meaningful source-origin, license and privacy-basis descriptions. Each heldout scene must attest independently blinded review (\`blinded_review: true\`, stable reviewer ID) and \`previously_inspected: false\`.

The gate checks:

- Every manifest and source-media SHA-256 against **the actual local file bytes**.
- All five mandatory pillars; missing or duplicate manifests are blocking.
- Cross-pillar recording identity consistency. A recording ID cannot name two different media digests or cameras, and identical media cannot be renamed to a different ID.
- No overlapping **recording IDs, video SHA-256s, or site/camera pairs** between global calibration and global heldout collections, including overlaps across otherwise separate pillars. Same untouched source can legitimately appear as heldout in multiple pillars if its identity agrees throughout.
- Known development-source name/path markers are barred from allegedly untouched heldout recordings.
- Synthetic mode exists only in direct unit tests; ordinary CLI refuses \`fixture_only: true\` and exits with nonzero status.

## What this does not establish

- The content or completeness of independent human annotations, consent, actual blinded-review independence, or legal authority is not verifiable from declarations alone.
- This gate **does not decode recordings, load models, check accuracy numbers, or qualify a government institution's CCTV**.
- Every pillar's **separate** frozen runtime/annotation validator and independently measured model acceptance policy must still pass. A metadata green result is only permission to proceed to those checks, never approval to deploy.
- The current repository has no lawfully authorized, untouched, independently labelled institutional cohort. As of this change, **all five real field accuracy gates remain blocked**.
- Camera Trust experimental PR #54 remains unmerged. The existing vision profile/model thresholds remain unchanged.

## Test coverage

Synthetic file bytes plus invented IDs are constructed inside temporary CI directories; they are not real recordings. Tests exercise global recording/camera/source alias leakage, missing fifth pillar, missing untouched attestation, tampered hash, known development marker, private-path-safe output, and the invariant that synthetic preflight can never yield a qualified result.

## Next stage

Arrange institutional recording permissions; freeze original recording IDs with site/camera boundaries *before model review*; independently annotate untouched scenes with privacy and retention constraints. Run this metadata preflight followed by all five actual evaluators, human error review and secure staging. Do not modify the frozen detector/profile to match new labels without a new independent heldout split.
