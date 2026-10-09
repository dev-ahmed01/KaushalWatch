# Protected API and evidence access — fail-closed boundary

KaushalWatch is a **synthetic SIH demo**, not a government-ready identity platform. The server now denies unauthenticated access to sensitive APIs and retained evidence when `KAUSHALWATCH_ENV` is `staging`, `pilot`, `prod` or `production`. This closes an important gap: previously, only officer-review writes and edge-sync writes required a token, while unauthenticated users could query case histories, images, reports and assistant data.

## Exact server behavior

- Protected: all `/api/*` routes except the two exceptions below, `/evidence/*` (including retained JPG files), and API schema/docs paths.
- `GET /api/health`: deliberately public for non-sensitive health checks.
- `GET /api/review-access`: exposes only `mode`, `required` and `prototype_only`, never tokens or actor IDs.
- `POST /api/edge/sync`: uses its **separate device-token authorization**. An edge token does not grant read access; an officer token does not authorize edge sync.
- An authenticated officer bearer key, resolved by `KAUSHALWATCH_REVIEW_TOKENS_JSON`, allows the protected API request. Missing/malformed credentials return **401**; missing/insecure officer key configuration returns **503**. Protected responses include `Cache-Control: private, no-store`; denied responses use `no-store`.
- Development remains open **only for local synthetic walkthroughs**, unchanged for the existing Chromium E2E and five-centre UI.

Example test-only protected server setup (generate unique high-entropy tokens in your real environment):

```dotenv
KAUSHALWATCH_ENV=staging
KAUSHALWATCH_REVIEW_AUTH_MODE=token
KAUSHALWATCH_REVIEW_TOKENS_JSON={"officer-test-01":"REPLACE_WITH_32_PLUS_UNIQUE_RANDOM_CHARACTERS"}
KAUSHALWATCH_EDGE_SYNC_AUTH_MODE=token
KAUSHALWATCH_EDGE_SYNC_TOKENS_JSON={"centre-edge-test-01":"REPLACE_WITH_A_DIFFERENT_32_PLUS_CHARACTER_SECRET"}
```

Use `curl` or a controlled API client to verify a protected read:

```bash
curl -H "Authorization: Bearer <OFFICER_SECRET>" http://127.0.0.1:8000/api/cases
```

**Important limitations.** The existing Next.js browser UI does not yet have a secure session/login flow for general authenticated data reads. Its standard `fetch` calls and `<img>` evidence elements do not attach an officer bearer token. As a result, **the protected environment is intentionally locked against the current browser UI** until a secure BFF/session proxy is implemented. This is safer than leaving records public; do not describe it as a completed staging/pilot rollout. Do not put keys in `NEXT_PUBLIC_*`, image URLs, browser local storage, application source or screenshots.

Bearer keys are not a replacement for per-centre least-privilege RBAC, secure cookies with CSRF protection, HTTPS, credential rotation, real officer identity, scoped evidence retention or database-backed audit transactions. For any real deployment, build and test those capabilities before connecting private footage or real-centre data. In particular, a valid officer token here is **not centre-scoped** and can access all demo centres.

## Validation

```bash
pytest -q backend/tests/test_protected_data_boundary.py
pytest -q backend/tests/test_review_access.py backend/tests/test_edge_offline_safety.py
```

The regression suite checks reports, settings, case evidence, runtime data, upload writes, assistant, protected API docs, static evidence, key failures and role separation. It also confirms that local demo endpoints are unaffected. Tests contain synthetic credentials and no real recordings.
