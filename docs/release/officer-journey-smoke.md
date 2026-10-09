# Release integration verification: officer journey and edge integrity

This checklist is intentionally distinct from the final real-world model evaluation. It validates code and workflow integration with **synthetic footage** and cannot be cited as detection accuracy.

## Synthetic API officer journey

`backend/tests/test_release_officer_journey.py` creates a short **fully black, locally generated AVI** in a temporary directory. The synthetic input is intentionally an *unusable camera*, not a spoofed training-centre scene.

The test runs a real FastAPI `POST /api/process-video` request and asserts:

1. The camera evidence is insufficient and the pipeline creates a `camera_integrity` review case rather than treating the video's zero detections as real zero attendance.
2. The case is persisted in an isolated temporary JSON store. The source video is not committed or retained by the API.
3. A privacy-blurred evidence image exists; the file's SHA-256 matches the retained integrity metadata.
4. Analysis history records a blocked attendance conclusion and the affected centre exposes camera attention.
5. The case-evidence pack includes the retained item.
6. A tokenless officer-review request fails with HTTP 401 without changing the case.
7. An authorized reviewer moves the case to `under_review`, then requests `virtual_verification`. Both transitions preserve server-derived reviewer attribution.
8. A new `CaseStore` instance reads the same status and two audit transitions.
9. The pending camera case appears in Actions. Insights, the deterministic non-provider assistant query, and the centre PDF endpoint respond.

The test never asserts the accuracy of person detection or real camera tampering; the only correct automated conclusion for the synthetic input is **insufficient evidence, needs officer review**.

### Run the focused checks

From repository root after installing `backend/requirements.txt`:

```bash
pytest -q backend/tests/test_release_officer_journey.py
pytest -q backend/tests/test_edge_review_integrity.py backend/tests/test_case_store_atomicity.py
python scripts/check_frontend_api_contracts.py
```

These tests run as part of `pytest -q backend/tests` in the GitHub Actions release PR as well.

## Offline edge replay integrity

`backend/tests/test_edge_review_integrity.py` verifies that:

- A new imported edge case starts **open**, even if a payload incorrectly claims that it is `confirmed`; edge inference is never an officer decision.
- A replay with the **same event ID** is idempotent.
- A second event with a **different event ID but an already-existing case ID** is acknowledged without replacing the stored case, its status, note, or officer audit trail.
- Such skipped updates are explicitly reported in `skipped_existing_case_ids` for operator diagnostics and will not be applied to case storage.
- A case resolved by a human remains resolved and no longer appears in the active officer action queue after the stale edge replay.

`backend/tests/test_case_store_atomicity.py` additionally verifies that interrupted file replacement does not truncate existing case records, and that two competing officer transitions in **one process** cannot silently overwrite one another.

**Boundaries:** The JSON store and `edge_events.json` are not a transactional, multi-process, multi-machine database. Network authentication for edge sync, signed event provenance, transactional event + case commits, retry/reconciliation observability, and centre-specific authorization are still needed before pilot deployment.

## Exact demonstration media: not yet qualified

The above tests use generated synthetic test input. They do **not** substitute for the user's actual final attendance, practical-work, infrastructure, apparent-operability, or camera-quality clips.

Before claiming real-video readiness, the operator must:

1. Keep actual footage locally under `data/raw/`, never in Git.
2. Record its license/privacy basis and independent timestamped ground truth.
3. Verify that the reviewed equipment cache exactly matches the source clip hash.
4. Run `python scripts/prepare_demo_vision.py --install` using the same runtime as the API.
5. Run `python scripts/check_demo_readiness.py --video <exact-source-clip> --final`.
6. Run `python scripts/run_final_demo_rehearsal.py --video <exact-source-clip>`.
7. Run `evaluation/evaluate_final_demo.py` with separately labelled actual annotation CSVs and report only supported metrics.
8. Inspect the real browser path, including denied access, missing provider credentials, and offline edge replay.

For the operator runbook, see `docs/final-demo-runbook.md`. For the milestone acceptance tracking, see `docs/release/SIH_MVP_TRACKER.md`.
