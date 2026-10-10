# Milestone 5 — Offline and judge-day recovery rehearsal

The SIH release provides a **synthetic-only** demo-state snapshot and isolated restoration CLI. It intentionally **does not** back up real-centre data, real footage, private model weights, connected provider credentials or complete government-grade state. Its purpose is to rehearse a failure/restart without risking the local demo state or overclaiming production recovery.

## Supported files and limits

`scripts/demo_recovery.py` backs up an allowlisted subset of local mutable demo state:

- `cases.json`, `analysis_history.json`, `centre_settings.json`, `evidence_index.json`, `edge_events.json`
- `edge/queue.json`, `edge/schedule-state.json` when present
- Simulated retained evidence images under `evidence/` with approved extensions

The tool refuses all non-simulated case, history and evidence entries, symlinks, unsafe path traversal, files larger than 25 MiB, aggregate data over 100 MiB, and more than 300 files. It **never** copies `data/raw/` or the actual video library. Because JSON case/evidence stores contain absolute image paths, isolated restore rebases them to the new directory and validates image SHA-256 digests before promotion.

**The archive is not encrypted.** Keep it restricted to synthetic demo records, outside public hosting and Git. Real centre data needs encrypted, access-controlled, retention-limited storage and a transactional database backup policy.

## Rehearsal sequence (PowerShell)

Use a folder containing explicitly generated *synthetic* data, not your live operational dataset. To create a disposable state:

```powershell
python scripts/prepare_demo_state.py --data-dir .rehearsal/demo-data --yes
```

Create a snapshot in a separate directory:

```powershell
python scripts/demo_recovery.py snapshot `
  --data-root .rehearsal/demo-data `
  --archive .rehearsal/demo-backup.zip `
  --yes
```

Verify the restore into a **NEW** location:

```powershell
python scripts/demo_recovery.py restore `
  --archive .rehearsal/demo-backup.zip `
  --destination .rehearsal/restored-demo-data `
  --yes
```

The restore fails if the destination already exists, even if empty. This prevents accidental destruction of existing work. The manifest inside the ZIP binds each allowlisted file to its original SHA-256 and size, and the restore refuses any extra or altered member. Image path changes are intentional and recorded in the restored JSON.

Finally inspect the restored `cases.json`, `analysis_history.json`, `edge/queue.json` and `evidence/` files, then follow [officer journey smoke](officer-journey-smoke.md) in the *isolated* demo backend. Never run the reset script against a directory containing real observations.

## CI acceptance evidence

`backend/tests/test_demo_recovery.py` uses actual deterministic SIH demo seed generation, records an officer's two-step audit, queues an offline event, writes a fake raw-video file that must stay outside the archive, snapshots state and restores to a separate directory. It checks the exact officer audit, evidence image SHA and local queued event identity. Negative tests reject archive tampering, path traversal, missing synthetic markers, external evidence references and attempts to overwrite a destination.

`backend/tests/test_atomic_review_action.py` separately verifies final officer decisions and their two audit events are committed **in one** case-store file replacement. If a disk write fails, the original open case remains unchanged. The frontend submits a single review POST. The browser regression suite verifies this and the absence of false healthy queue/camera indicators.

## Outstanding release blocks

- This proof does not support backup of real footage or private training-centre data.
- Multi-worker, cross-process or distributed backend transactions are **not implemented**; JSON ledgers are strictly one-worker prototype storage.
- A backup is not a disaster-recovery plan without configured secrets, identity management, retention rules, tested restore of the target production database and real hardware.
- Final licensed stage footage, independent labels and frozen model scoring still require local operator execution and review.
- A full clean-machine rehearsal and sign-off must still be performed on the judge-day target environment.

The synthetic recovery gate strengthens the reproducibility of the SIH demo. It does **not** certify production readiness.
