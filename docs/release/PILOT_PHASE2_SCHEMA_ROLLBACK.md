# Pilot readiness contract — PostgreSQL v3 and candidate-specific probing

The KaushalWatch Phase 2 release uses separate public **process liveness** and **operational readiness** signals. Never interpret an HTTP 200 from the API process as confirmation that a protected centre is safely operational.

- \`GET /api/health\`: process liveness only, independent of database and private source availability.
- \`GET /api/ready\`: protected pilot/prod (and strict staging) returns **503** unless protected OIDC officer configuration, private S3 evidence configuration, all PostgreSQL migrations **1, 2 and 3**, and all ten required tables are present. This is still only a dependency/configuration check; it does **not** independently attest real KMS policy, IdP MFA, custody or camera accuracy.
- \`python scripts/migrate_postgres.py --check\`: requires complete PostgreSQL v3 tables, without mutating SQL. The migration-only identity applies schema separately.
- \`python scripts/check_camera_trust_deployment.py --probe-database\`: probes the **exact DSN supplied in the candidate preflight environment**, not any unrelated shell/database connection. Reports named checks with no passwords, DB endpoints, SQL records or source media.
- \`python scripts/check_pilot_rollout.py ... --probe-database\`: combines exact candidate-DB checks, signed independent field evidence and an actual HTTPS staging contract without activating autonomous enforcement.

## Deployment and rollback rules

1. Freeze a specific audited commit SHA and image digest for both API and web containers; never deploy a floating \`latest\` tag. Keep the last known-good **compatible** API/web image digests in operator-controlled release records outside Git.
2. Back up PostgreSQL and verify a restore **to an isolated environment** before running a versioned migration. Use a migration-only role and \`scripts/migrate_postgres.py --check\`. Neither the API container nor CI applies migrations automatically.
3. After any deployment, a failing \`/api/ready\` must **stop traffic/pilot activation**. Health probes may still return 200; that is not a successful rollout. Do not bypass the readiness failure or insert synthetic centre records.
4. Roll back API/web images only if compatible with the currently migrated database. If a database rollback is required, it must follow an independently reviewed restore plan—not automatic reverse migrations or destructive schema changes.
5. Keep all private camera media and field dossiers on approved private storage and maintain officer permissions. The source video worker continues under shadow/manual review; neither restored services nor a passing technical preflight authorizes automatic sanctions.
6. Operator acceptance requires actual HTTPS OIDC/MFA, private S3/KMS custody and access audit, PostgreSQL restore drill, source-authorized camera worker, and independently signed blind field measurements.

The CI tests in \`backend/tests/test_pilot_schema_readiness.py\` use entirely synthetic database connections to verify v2 and incomplete v3 remain unready, that all ten v3 tables are required, that real receipts never include candidate DSNs, and that local demo readiness remains unaffected. CI passing is **not** evidence of a real centre rollout.

## Protected browser session readiness (Phase 2 follow-up)

The Next.js BFF has a separate public, read-only `GET /api/auth/readiness` dependency check.
HTTP **200** with exactly `{"ready":true,"mode":"protected"}` means the deployed
BFF has accepted a harmless Redis REST `GET` with its configured server-side
credentials. HTTP **503** is returned for absent/invalid configuration, ephemeral
memory sessions, an unavailable Redis network connection, or an invalid response.
No officer session, token, Redis endpoint, key, or private evidence is returned.
Responses always use `Cache-Control: no-store`.

**Do not mistake `GET /api/auth/status` for Redis readiness.** It may truthfully
return unauthenticated HTTP 200 for a no-cookie visitor without a storage lookup.
`scripts/check_protected_staging.py` now requires the durable session readiness
endpoint in addition to API readiness, OIDC redirect, cookie, and anonymous
access denial. The endpoint proves a live read-only dependency interaction,
not session durability across regions, user revocation, IdP MFA or field approval.
CI explicitly checks missing configuration, synthetic memory, and unreachable
Redis all fail closed; a separate synthetic Redis/OIDC integration proves the
positive path. No real cloud session service is asserted by these tests.
