# Protected officer browser — session/BFF rehearsal

This is an opt-in **single-process** browser integration for the SIH prototype, not a government-grade identity deployment. It connects a Next.js officer session to the existing protected FastAPI read/write/evidence boundary without storing the officer bearer key in browser local storage, JavaScript state after login, or image URLs.

## Design and boundaries

1. The officer enters a pre-provisioned bearer key on the `/login` page. The browser sends the key **once**, same-origin, to `POST /api/auth/login` over HTTPS on a real deployment. It is not logged or retained in local storage.
2. The Next.js route checks a strict `Origin` header, then calls the backend's **protected-only** `GET /api/officer-validate` with that key. That endpoint refuses to validate in development/demo mode or when the backend is missing token authentication.
3. A valid key creates an **opaque, 32-byte random session ID** and a separate CSRF secret retained in an encrypted, shared Redis REST store for a maximum of 30 minutes when durable mode is enabled. The browser receives only a short-lived `HttpOnly`, `SameSite=Strict`, `Secure`-in-production session cookie; the bearer key remains on the Next.js server.
4. The protected frontend build sets `NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY=true`. This public value is a feature switch, **not a credential**. Browser API/evidence requests use same-origin `/api/proxy/api/...` and `/api/proxy/evidence/<id>.jpg` endpoints. The Next.js server forwards only allowlisted application endpoints, attaches the officer bearer in its server-to-server request, and filters outgoing response headers to deny caching or accidental cookie forwarding. Video uploads are streamed rather than buffered in memory.
5. Mutations require the session CSRF token supplied in `X-KaushalWatch-CSRF` and a matching `Origin`. The token comes from `GET /api/auth/status`, and does **not** carry officer credentials. The browser app adds it automatically. An edge-device token cannot read officer case data; the officer proxy blocks edge-sync routes.
6. `POST /api/auth/logout` requires matching origin and CSRF, revokes the session server-side, and clears the cookie. Expired or lost sessions block further reads rather than falling back to local-demo permissions.

**Session update:** The original single-process memory map is now a synthetic-staging-only explicit fallback. A configurable encrypted Redis REST session store supports shared, expiring, revocable browser sessions across Next.js instances. See [distributed-session-store.md](distributed-session-store.md) for setup and test boundaries. There is still no real pilot identity provisioning, administrator revocation, centre-scoped RBAC, login throttling, full read audit or end-to-end security certification. **Do not deploy against real-centre data.**

## Local protected smoke (synthetic only)

Use an isolated local demo-data environment, not real CCTV clips or attendance records. The protected FastAPI process must be configured for `staging`, officer `token` mode, and unique random test secrets:

```bash
# Backend runtime: set these via a private environment file or secret manager.
KAUSHALWATCH_ENV=staging
KAUSHALWATCH_REVIEW_AUTH_MODE=token
KAUSHALWATCH_REVIEW_TOKENS_JSON='{"officer-test-01":"REPLACE_WITH_A_UNIQUE_32_PLUS_CHARACTER_TEST_SECRET"}'
KAUSHALWATCH_EDGE_SYNC_AUTH_MODE=token
KAUSHALWATCH_EDGE_SYNC_TOKENS_JSON='{"edge-test-01":"REPLACE_WITH_A_DIFFERENT_32_PLUS_CHARACTER_TEST_SECRET"}'

python scripts/prepare_demo_state.py --yes
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8011
```

In a second terminal, build and run the protected web server using the same synthetic backend:

```bash
cd web
NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY=true npm run build
KAUSHALWATCH_WEB_AUTH_MODE=protected KAUSHALWATCH_API_INTERNAL_URL=http://127.0.0.1:8011 npm run start -- -H 127.0.0.1 -p 3001
```

For actual network traffic, expose the browser only through **HTTPS** and use HTTPS between servers unless both are on local loopback. Do not copy a real officer secret into a test, issue it through `NEXT_PUBLIC_*`, put it in a query parameter, or print it in support logs.

CI now includes a separate `protected-browser` workflow job that boots synthetic records in protected FastAPI mode, compiles the proxy-enabled Next.js build, verifies direct backend authorization and executes `web/e2e/protected-session.spec.ts`. It tests wrong keys, cross-site login, opaque HttpOnly cookie, protected API reads, retained evidence JPEG, missing/forged CSRF, denial of edge sync through officer proxy, logout revocation, and the officer audit browser path. The existing 20+ browser tests still run in independent **development demo mode** without real provider credentials.

## Pilot blockers

- A centralized or securely managed identity provider with real users and actor/centre-scoped RBAC.
- A real hosted Redis REST deployment/security review and a verified CSRF policy behind the intended reverse proxy (synthetic multi-instance protocol check implemented).
- Login throttling, strong audit/access logs, TLS, credential rotation and session management.
- A transactional backend database, media encryption/retention policy, legal data provenance.
- Final licensed video, held-out annotations and actual model evidence scores.

This phase makes a protected synthetic browser walkthrough possible; it is **not** production authentication certification.
