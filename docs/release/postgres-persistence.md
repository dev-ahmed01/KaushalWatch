# Protected PostgreSQL persistence — release validation

This is a **transactional structured-data storage option** for the SIH
prototype. PostgreSQL replaces process-local JSON for cases, officer review
audit history (embedded in case records), analysis history, centre settings and
edge-event receipts. It does **not** make local video/evidence media,
inference workers, assistant conversation memory or the overall application
production-ready.

## Storage selection

Default local development keeps the existing single-worker JSON walkthrough.
No local database is required:

```text
KAUSHALWATCH_ENV=development
KAUSHALWATCH_STORAGE_BACKEND=json
```

On a protected backend, configure PostgreSQL in the **backend server environment**:

```text
KAUSHALWATCH_ENV=staging
KAUSHALWATCH_STORAGE_BACKEND=postgres
KAUSHALWATCH_DATABASE_URL=postgresql://APP_USER:SECRET@DB_HOST:5432/APP_DB?sslmode=verify-full
```

Do not expose the database URL through `NEXT_PUBLIC_*`, browser logs,
API responses or a committed `.env`. Use TLS certificate validation and
database credentials issued to this application, preferably via a secret
manager. Production/pilot requests fail closed when PostgreSQL storage is
not enabled. The synthetic staging/browser test retains a deliberately
non-production JSON option; this does not certify that mode for pilots.

## Explicit migration

Never run migrations inside application startup or against an unknown
database. Back up the target database and run with a migration-capable
credential, then grant the runtime role only required DML:

```bash
python scripts/migrate_postgres.py --apply
python scripts/migrate_postgres.py --check
```

Migration `backend/sql/0001_initial.sql` creates versioned schema metadata,
case records, analysis history, centre settings and edge receipts. It adds
unique primary keys and an edge-event uniqueness constraint. Reapplying
migration v1 is idempotent. The app does not silently load or convert old
JSON fixtures into the database; the PostgreSQL tables begin empty.
Production data migration, encryption/backups/restore and retention policy
must be planned separately.

## Transaction boundaries

- A case is identified by a unique case ID. Incoming inference writes are
  insert-only: colliding IDs cannot overwrite existing officer decisions.
- Officer state transitions run under `SELECT ... FOR UPDATE`. Two workers
  cannot both finalize the same case using a stale state; its review history
  and final status commit in one row update.
- Analysis rows get database-generated monotonically increasing IDs, with an
  optional unique edge event ID preventing duplicate analysis acknowledgments.
- Centre settings updates serialize per centre to prevent lost updates from
  concurrent processes.
- Edge ingestion acquires a cross-worker PostgreSQL advisory transaction lock.
  Event receipts, derived cases and history rows use the same connection and
  transaction. Any failure rolls back all three. The existing safe
  normalization and device-token restrictions still apply.
- Each normal operation opens its own transaction/connection. Connection
  pooling and high-volume retention are separate engineering tasks.

## Verification

The dedicated `postgres-persistence` GitHub Actions job launches an
isolated PostgreSQL 16 service, explicitly applies/checks the migration and
runs `backend/tests/test_postgres_storage.py`. Tests include independent
connections, racing review transitions, repeated edge deliveries, transaction
rollback on induced failure, scoped officer reads and settings durability.

The normal backend suite skips these DB-only integration tests when no
`KAUSHALWATCH_DATABASE_URL` and no `KAUSHALWATCH_TEST_DATABASE` are
configured. For safety, destructive test fixtures **refuse** any database
without the explicit `KAUSHALWATCH_TEST_DATABASE=isolated_ci` marker and a
database URL containing `kaushalwatch_ci`. Never run them on your deployed
database.

## Outstanding before pilot

1. Durable, centrally hosted **evidence image/video storage**, access checks
   and encrypted retention, not the present local `data/evidence` directory.
2. Real identity provider, provisioning, audit/credential lifecycle and login
   throttling; static synthetic officer bearer configuration is not an IdP.
3. Centralized logs, monitoring, connection pooling, backup/restore drills,
   fault injection and operational failover tests.
4. Independently annotated licensed camera footage with held-out accuracy
   thresholds and exact final demonstration rehearsal.
5. A secure migration path from existing JSON records if any records must
   be carried forward. No automatic migration is performed.

**Claims:** The new system is a validated structured-data persistence layer
with synthetic PostgreSQL CI, not a government-certified compliance datastore.


## v3 Camera Trust restore coverage (isolated CI)

The release CI PostgreSQL dump/restore test now compares all ten v3 protected
tables plus \`kw_schema_migrations\` (11 total), not only the original six.
It plants **synthetic-only** Camera Trust registry, approved reference,
completed job, reviewed observation and chained audit records; then verifies
their structure, digest chain and the immutable audit trigger after restoration.
The original reviewed officer case sentinel is also checked.

Results are nonsecret row counts and booleans only. This still does **not**
validate real hosted backups, S3 evidence bytes, KMS keys, deployment downtime,
physical camera performance or actual disaster-recovery RPO/RTO. The tool
only accepts a local, disposable \`kaushalwatch_ci\` database with an explicit
CI marker and rejects alternate libpq destination overrides. Real recovery
work requires a separately approved and isolated operator procedure.
