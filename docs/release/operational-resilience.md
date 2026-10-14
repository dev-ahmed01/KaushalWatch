# Operational resilience — evidence inventory, DB readiness and restore drill

Implemented in the release branch. This phase tests *structured-data
recoverability and consistency signals*, not live AWS failover, actual KMS
access, geographically redundant storage or a fully approved retention policy.

## 1. Health and routing

`GET /api/health` remains process **liveness only**. It returns 200 when the
server is running even if its database is down. Do not use it as the load
balancer readiness check.

`GET /api/ready` is a separate, public, **non-diagnostic readiness** probe.
The response is exactly `{"ready": true}` (HTTP 200) or
`{"ready": false}` (HTTP 503), with `Cache-Control: no-store`.
No credentials, table names, errors, bucket paths or DB hosts are exposed.

In pilot/production it verifies:
- PostgreSQL and private S3 modes have been explicitly selected.
- Officer permission mapping and private evidence KMS/bucket **configuration**
  are present.
- A PostgreSQL connection works, schema migrations v1/v2 exist, and required
  tables are present.

`/api/ready` **does not perform an AWS write/read**, verify key policy or
prove media disaster recovery. Configure external cloud monitoring for those.
For local demo the readiness probe checks only process viability; a green
local probe is not a pilot readiness result. Synthetic staging test setups
remain separate from strict pilot requirements.

## 2. Read-only retained-evidence inventory

Run from a secured, private operator environment with *read-only* DB role,
permission to list the private S3 evidence prefix, and application settings:

```bash
python scripts/audit_private_evidence.py \
  --out /secure/ops/evidence-audit-20261014.json \
  --limit 50000
```

The command refuses to overwrite an existing report and creates the report
with user-only permissions. It exits 0 on a completed consistent inventory
and 2 on an incomplete or inconsistent inventory. Its report includes
**counts only**, not faces, pictures, object names, hashed credentials, case
IDs or per-person observations.

It checks:
- S3 objects under the fixed `evidence/v1/` prefix with no matching DB index.
- Metadata rows not linked to any persisted case evidence.
- Case evidence records missing a metadata row.
- Metadata rows pointing to an object absent from the completed S3 listing.
- Key/centre/SHA identity mismatches and malformed inventory keys.
- Duplicate references to an evidence ID in multiple cases.

The audit uses S3 pagination and refuses to claim completion if it reaches
the operator's object bound or a continuation token fails. It intentionally
does **not** delete any data or emit a suggested list of objects to erase.

**Consistency limitation:** PostgreSQL and S3 are not one transactional
snapshot. Concurrent legitimate uploads may be reported as temporary
orphaned objects. Run again after the upload window and investigate with an
authorized officer. An automatic deletion policy is not implemented: obtain
legal retention and evidence-hold requirements first.

## 3. Safe disposable backup and restore

The CI PostgreSQL job now tests *real native pg_dump/pg_restore tools*, using
an isolated database named `kaushalwatch_ci` on 127.0.0.1:5432. It:
1. Seeds a synthetic officer-reviewed case with audit history.
2. Snapshots hashes of cases, analysis history, settings, edge receipts,
   evidence metadata and migration tracking.
3. Runs `pg_dump` with no credentials on argv and writes an archive only to a
   temporary directory.
4. Creates a **separate** random-name disposable database, restores the dump,
   compares every table snapshot digest and explicitly checks officer review
   history.
5. Drops only that newly created disposable database and removes the archive.

Script: `scripts/drill_postgres_restore.py`.

The script refuses every DB outside the exact named localhost test database
or without `KAUSHALWATCH_TEST_DATABASE=isolated_ci`. **Never** run it
against production. A real rollout needs encrypted scheduled backups and
offsite restore testing with correct RPO/RTO and approved retention. This CI
drill does **not** back up S3 images, Redis sessions, upload queues, model
weights, KMS keys or regional infrastructure.

## 4. Cross-process consistency

The PostgreSQL integration suite launches a **separate Python process** that
reads and validates a reviewed case written in the original test process.
Existing tests concurrently finalize a case and synchronize edge receipts
using independent database connections. This verifies transaction-backed
cross-process visibility, but it is not an application load test or proof of
multi-instance S3/IAM network failover.

## 5. Verification and remaining blockers

Dedicated GitHub Actions job runs:

```bash
python scripts/migrate_postgres.py --apply
python scripts/migrate_postgres.py --check
pytest -q backend/tests/test_postgres_storage.py backend/tests/test_s3_evidence.py
python scripts/drill_postgres_restore.py
```

The private S3 tests use an in-memory object-service stand-in, not live AWS.
They cover inventory consistency, orphan/missing-object identification,
tampered metadata, bound-limited scanning, and the new readiness checks.

**Before a real pilot:** external identity provisioning, AWS bucket IAM/KMS
security acceptance, a separately approved legal-retention schedule and
purge/hold process, encrypted backups for object storage, emergency restore
and failover exercises against a real deployment, rate limiting, monitoring,
and independently labelled real training-centre footage.

Do not present any of these CI successes as production disaster-recovery
certification or measured CCTV accuracy.
