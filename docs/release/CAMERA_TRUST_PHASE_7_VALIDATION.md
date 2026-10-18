# Camera Trust — Phase 7 independent validation framework

**Status:** Evaluation SOFTWARE implemented. Real-world field acceptance remains **BLOCKED**. No source media, face/person tracking, physical camera truth, or operational alerts are produced.

## Fixed nine-phase roadmap

| Phase | Scope | State |
|---|---|---|
| 1 | Research foundation and architecture | Implemented |
| 2 | Source-pinned research workstation | Implemented |
| 3 | PostgreSQL, protected officer roles and audit | Implemented |
| 4 | Private Drive worker, hashes and diagnostic proxies | Implemented |
| 5 | Camera Trust operator dashboard and reviews | Implemented |
| 6 | Security, synthetic video, PostgreSQL, E2E and Docker CI | Implemented |
| 7 | Frozen independent holdout evaluation software | Implemented; external holdout missing |
| 8 | Controlled deployment and live-source shadow pilot | Requires target environment and approval |
| 9 | Independently adjudicated field validation, acceptance and handover | Requires independently verified field evidence |

Phase count is a project-management milestone indicator, **not** measured detector accuracy. A successful pipeline build never establishes real-camera tamper detection quality.

## Zero recurring chat-upload workflow

1. The existing private worker records SHA-pinned, numeric-only diagnostics in PostgreSQL. No manual JSON upload to ChatGPT is necessary.
2. A separate physical adjudicator freezes a **private** label manifest before comparisons. Manifest schema: `KW_CAMERA_INDEPENDENT_LABELS_V1`; required top-level fields: `schema`, `split: "untouched_external_holdout"`, `evaluation_policy_sha256` (64 lowercase hex characters), `labels_frozen_at` (timezone-aware ISO timestamp), and `cases`.
3. Each case refers to the **existing job UUID** as `case_id`, the original centre ID as `site_id`, camera UUID as `camera_id`, `source_sha256`, `label` (`normal`, `covered`, `defocused` or `moved`), `duration_seconds`, `stratum`, distinct `independent_labeler_id`, `source_custodian_id`, `inference_operator_id`, `custody_record_id`, `label_adjudicated_at`, `label_blinded_to_predictions: true`, and `independent_capture: true`. These are **unverified declarations**; software cannot prove adjudicator independence or camera custody from claims in JSON.
4. On the **authorized PostgreSQL host**, generate the matching numeric snapshot directly:

   ```bash
   python scripts/export_camera_trust_holdout.py --labels /private/locked-labels.json --output /private/numeric-snapshot.json
   ```

   Export joins only named job UUIDs to centre/camera/source hashes, requires completed jobs, verifies each numeric trace and **allowlists** fields to exclude any unexpected image, source alias or unrelated DB JSON. The output binds to the canonical SHA-256 digest of the frozen label manifest.

5. Evaluate without touching source videos, rerunning inference or changing policy:

   ```bash
   python scripts/evaluate_camera_trust_holdout.py --labels /private/locked-labels.json --predictions /private/numeric-snapshot.json --output /private/holdout-evaluation.json
   ```

   Results are created with no overwrite and restrictive file permissions. Missing rows, duration conflicts, mismatch of hashes, invalid frame positions, unblinded labels, conflicting human roles or unsupported production claims fail closed. A no-input status command is also available:

   ```bash
   python scripts/evaluate_camera_trust_holdout.py --status
   ```

## How to interpret reported metrics

- `positive_clip_candidate_rate`: among independently labeled positive **clips**, proportion with at least one numeric review candidate in **sparsely decoded** frames. It is not event-level physical tamper recall.
- `normal_clip_candidate_rate`: among independently labeled normal clips, proportion with any numeric review candidate. It is **not** a false-alarms-per-camera-hour estimate.
- Stratification is by class, site and recording condition, with Wilson 95% binomial intervals and explicit normal-footage duration as **exposure context**, not an alert-rate denominator. Count/position failures are not imputed or silently ignored.
- These results do not train or tune detector thresholds, and cannot be used to promote the unvalidated policy on the same holdout.

Every evaluated report contains `qualified_for_autonomous_enforcement: false`, `false_alarms_per_camera_hour_established: false`, `label_independence_cryptographically_verified: false`, and `field_release: "BLOCKED_EXTERNAL_ACCEPTANCE_REQUIRED"`. This is intentional. For real field qualification, an external authority must verify physical custody, independent annotation/blinding, sufficient normal camera-hours, night/IR/movement/partial-cover conditions, candidate-to-operator-alert conversion, measured alert burden, latency, operator review and a signed acceptance decision. The existing Day 3/Day 4 recordings do not satisfy those conditions by themselves.

**Do not commit** private label manifest, numeric export, credentials or original source media to the public repository. No report upload to this conversation is part of the defined evaluation workflow.
