# Officer review access — SIH prototype boundary

KaushalWatch now supports a **server-enforced officer access check for case-review writes**. This is a deliberately small safeguard, **not full login, tenant authorization, RBAC, SSO, or government deployment security**. Reading evidence, analysis, exports, and other mutating API routes are *not* protected by this mechanism. Do **not** expose the current full application to an untrusted network with real personal or centre data.

## Local SIH/demo mode

Default settings are `KAUSHALWATCH_ENV=development` and `KAUSHALWATCH_REVIEW_AUTH_MODE=demo`. In this mode, case-review writes remain possible without an access key so the deterministic SIH seed and existing E2E walkthrough still work. Every resulting review event records the literal actor `prototype_officer`, and the review page labels this as **Local demonstration mode**. This actor label must not be presented as a verified human identity.

**Important:** The API will return HTTP 503 for review access and review writes if `KAUSHALWATCH_ENV` is `production`, `prod`, `pilot`, or `staging` while auth mode is `demo`. A missing/invalid token configuration also fails closed.

## Server-mapped reviewer keys (recommended for any nonlocal demo)

Generate one **different** high-entropy opaque key per officer on the operator's trusted machine:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set environment values **only in the backend environment** (never in `NEXT_PUBLIC_*`, the frontend bundle, sample data, or Git):

```dotenv
KAUSHALWATCH_ENV=staging
KAUSHALWATCH_REVIEW_AUTH_MODE=token
KAUSHALWATCH_REVIEW_TOKENS_JSON={"officer-01":"REPLACE_WITH_RANDOM_32_PLUS_CHARACTER_SECRET","officer-02":"REPLACE_WITH_ANOTHER_UNIQUE_RANDOM_SECRET"}
```

The key map is a JSON object of unique case-sensitive server-verified officer IDs to unique random bearer keys, each at least 32 ASCII nonwhitespace characters. Config errors, missing keys, duplicate keys, and invalid officer IDs produce HTTP 503 for review writes. An invalid or absent bearer produces HTTP 401 and **does not change a case**. The server only stores the associated officer **ID** in the review audit trail; it never stores the key.

Launch the API using the existing `--env-file` mechanism so all worker processes see the same environment:

```powershell
cd backend
python -m uvicorn app.main:app --env-file ..\.env --host 127.0.0.1 --port 8000
```

For a remote test, use **HTTPS, narrow CORS origins, restricted ingress, and synthetic records**. Do not expose this proof-of-concept API as a public production application.

## Reviewer workflow

1. Open **Actions → Case → Officer review**.
2. If token mode is active, enter the assigned access key in the password field.
3. Read the evidence, add a decision note, and choose an allowed case action.
4. The frontend sends the key **only** in the `Authorization: Bearer ...` header on officer-review POST requests. The key stays in React memory and is not stored in browser cookies, localStorage or sessionStorage.
5. The backend derives the actor from the configured token map and persists the case-state transition, timestamp, note and actor. Audits display **Recorded by: officer-01** or the applicable server-mapped actor.
6. Missing credentials, wrong credentials or a failed review-access status check block writes with a visible error. No failure should silently become a successful review.

`GET /api/review-access` exposes **only** `mode`, `required`, and `prototype_only`. It never returns a key or a list of authorised actors.

## API and security verification

```bash
python scripts/check_frontend_api_contracts.py
pytest -q backend/tests/test_review_access.py backend/tests/test_review_api.py
cd web && npm run test:e2e -- --grep "officer token-mode|review access endpoint failure"
```

The structural contract gate checks 22 method/path pairs, including `GET /api/review-access`. Backend tests cover 401/503 paths, identity spoofing, distinct actor attribution and no audit key disclosure. Browser tests cover no-key blocking and access-status failure.

### Remaining security work before any pilot

- Real identity provider, session expiry, per-centre authorization, least-privilege roles and reviewer membership.
- Authentication/authorization for **all** sensitive reads, evidence, PDF exports and writes—not just review updates.
- Immutable/transactional audit persistence and concurrent case-update protection (current JSON file store is a prototype).
- TLS termination, centrally managed secrets, key rotation, CSRF/CORS/deployment review, rate limits, security logging and penetration testing.

The token-mode check is a release hardening measure for a **controlled synthetic SIH demonstration**, not certification of production or real-centre security.
