# Staging deployment acceptance — security rehearsal and evidence gates

This phase adds an integrated **synthetic OIDC browser rehearsal** and a
credential-free HTTPS deployment preflight. Neither substitutes for testing
against an actual identity provider, AWS KMS/S3 or authorized centre footage.

## Automated CI rehearsal

The dedicated `oidc-browser-acceptance` GitHub Actions job creates an isolated
synthetic environment on loopback addresses only:

- Fresh RSA signing key and a mock authorization-code provider at
  `127.0.0.1:8371`, with one-use S256 PKCE-bound grants and short-lived
  access JWTs, never production IdP credentials.
- A synthetic staging FastAPI instance at `127.0.0.1:8013`, with
  `KAUSHALWATCH_REVIEW_AUTH_MODE=oidc` and exact actor/centre subject grants.
- A Next.js protected browser at `127.0.0.1:3003`, encrypted shared session
  data in a synthetic Redis REST process at `127.0.0.1:6398`.
- Playwright sign-in through the **actual browser callback and API signature
  verifier**; case authorization, logout, forged state denial, unprovisioned
  subject denial, wrong-audience denial, and a viewer attempting to use
  self-claimed administrator role.
- Public-only `scripts/check_protected_staging.py` checks liveness, readiness,
  denied unauthenticated API/proxy reads, OIDC-only modes and PKCE redirect
  with an HttpOnly short-lived cookie.

The mock provider and mock Redis never persist users or real login secrets,
never communicate outside loopback, and never certify IdP MFA/conditional
access. Browser evidence is synthetic; no real CCTV video is used.

## Explicit synthetic transport guard

Only when **ALL** are true:

```
KAUSHALWATCH_ENV=staging
KAUSHALWATCH_ALLOW_LOOPBACK_OIDC_TEST=true
KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT is NOT true
```

can the web and backend accept a plain HTTP identity endpoint, and then
**only** when its host is exactly `127.0.0.1`. This is strictly for the CI
mock issuer. It cannot be enabled in pilot/production, and it is not permitted
under strict staging acceptance. The API still rejects forged signatures and
wrong audience; the test uses a real ephemeral RSA key.

Do not run a synthetic identity provider on a publicly reachable interface
or configure publicly reachable staging services to trust one.

## Real HTTPS staging requirements

Operator-supplied configuration (no values should enter Git):
```text
KAUSHALWATCH_ENV=staging
KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT=true
KAUSHALWATCH_REVIEW_AUTH_MODE=oidc
KAUSHALWATCH_STORAGE_BACKEND=postgres
KAUSHALWATCH_EVIDENCE_BACKEND=s3
KAUSHALWATCH_DATABASE_URL=<TLS-validated DB URL>
KAUSHALWATCH_EVIDENCE_S3_BUCKET=<private bucket>
KAUSHALWATCH_EVIDENCE_S3_REGION=<region>
KAUSHALWATCH_EVIDENCE_KMS_KEY_ID=<actual key>
KAUSHALWATCH_OIDC_ISSUER=<pinned https issuer>
KAUSHALWATCH_OIDC_JWKS_URL=<pinned https issuer-host JWKS>
KAUSHALWATCH_OIDC_AUDIENCE=<dedicated API audience>
KAUSHALWATCH_OIDC_GRANTS_JSON=<approved subject grants>
KAUSHALWATCH_WEB_AUTH_MODE=protected
KAUSHALWATCH_WEB_IDENTITY_MODE=oidc
KAUSHALWATCH_OIDC_AUTHORIZATION_ENDPOINT=<https authorization URL>
KAUSHALWATCH_OIDC_TOKEN_ENDPOINT=<https token URL>
KAUSHALWATCH_OIDC_REDIRECT_URI=<https application callback>
KAUSHALWATCH_OIDC_CLIENT_ID=<client id>
KAUSHALWATCH_SESSION_STORE=redis-rest
KAUSHALWATCH_SESSION_ENCRYPTION_KEY=<shared 32-byte base64 key>
```

In strict staging, **static officer keys and JSON/local image storage cannot
satisfy protected access**. `/api/ready` requires database/schema, evidence
configuration and OIDC grant configuration. Readiness is not a cloud IAM
attestation: do not expose a new deployment to real users merely because the
endpoint returns 200.

Run **from a secured operator workstation**, supplying the actual HTTPS URLs:

```bash
python scripts/check_protected_staging.py \
  --api https://api-staging.example.org \
  --web https://console-staging.example.org
```

The preflight performs no authenticated requests or writes. It checks only
non-sensitive readiness, anonymous denial, server-selected OIDC mode and
PKCE-redirect properties, then prints a machine-readable pass/fail report
without access tokens, private data or object keys. It requires HTTPS
unless `--synthetic-loopback` is **explicitly** selected for CI. That CI
mode is labelled `synthetic_transport_check_only`, never accepted as
real-world readiness.

## Manual real deployment acceptance

A deployment operator still must document all of the following **outside the
code repository** before marking a pilot eligible:

1. **Identity:** Verify actual IdP authorization, MFA enforcement,
   group/subject lifecycle, JWKS rotation, browser logout semantics, role
   revocation and MFA bypass tests against the chosen provider.
2. **AWS security:** Independently inspect bucket public-access block,
   TLS-only object policy, least-privilege IAM, SSE-KMS key policy, KMS
   decrypt denied for unauthorized principals, and audit logs.
3. **Persistence:** Use two actual FastAPI instances concurrently to verify
   committed case decisions, edge replay rejection, evidence access, DB
   disconnect behavior and retry recovery.
4. **Recovery:** Restore a real encrypted PostgreSQL backup and protected S3
   metadata/media under an authorized isolated disaster-recovery exercise.
   Record realistic RPO and RTO, not CI completion time.
5. **Retention/privacy:** Approve officer-only evidence policies, legal holds,
   retention periods, deletion reconciliation and DSAR workflow before
   real-person footage collection.
6. **AI accuracy:** Complete independently annotated held-out validation
   against the actual training-centre camera footage, counting and compliance
   decisions with documented false-alert tolerances.

If any item is missing, call the deployment **not pilot-accepted**.
The integrated mock browser tests and preflight improve confidence in the
application boundary, not real infrastructure certification.

## Release discipline

- Do not merge PR #55 without review and successful CI.
- Never put real account secrets, private identity-provider tokens, footage
  or identifiable evidence into GitHub Actions logs or synthetic mocks.
- Protect all future acceptance claims with a timestamped operator-owned
  checklist; keep real third-party results outside the repository unless
  redacted and authorized.
