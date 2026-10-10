# Redis REST officer sessions — protected browser

This is the next release **engineering slice** after the single-process protected
browser. Centre-scoped permissions and pilot identity management are **not**
completed by this session change.

## Behaviour

- `KAUSHALWATCH_SESSION_STORE=redis-rest` uses an Upstash-compatible Redis
  REST origin. Each random 256-bit browser session ID is keyed only by its
  SHA-256 digest in Redis, never its raw cookie.
- The server encrypts the officer's upstream bearer key **and** the CSRF secret
  with AES-256-GCM, a fresh nonce, and an authenticated storage-key binding
  before writing the shared store. The encryption key is a private environment
  secret and must be identical across all Next.js instances.
- `SET ... EX 1800 NX` enforces a fixed 30-minute TTL. The server also checks
  the payload expiry on reads. `DEL` revokes the shared session when logging out.
  All instances resolve the session from the same Redis data store, not from
  process memory. A successful logout from one instance affects the others.
- Redis failures, missing secrets, malformed responses and decryption failures
  produce an unavailable response (503), **not** anonymous/demo fallback.
- The older in-memory mode is available only with BOTH
  `KAUSHALWATCH_SESSION_STORE=memory` and
  `KAUSHALWATCH_ALLOW_EPHEMERAL_SESSIONS=true` in explicit local/test/staging
  environments. It is always rejected in production/pilot.
- Sessions are **not** a replacement for scoped backend authorization, officer
  identity provisioning, credential rotation or security assessment.

## Private runtime configuration

Set on every protected **Next.js server**, not in `NEXT_PUBLIC_*` variables:

```bash
KAUSHALWATCH_WEB_AUTH_MODE=protected
KAUSHALWATCH_SESSION_STORE=redis-rest
KAUSHALWATCH_SESSION_REDIS_REST_URL=https://YOUR-REDIS-REST-ENDPOINT
KAUSHALWATCH_SESSION_REDIS_REST_TOKEN=YOUR_SERVER_ONLY_REDIS_REST_TOKEN
KAUSHALWATCH_SESSION_ENCRYPTION_KEY=YOUR_BASE64_OF_32_RANDOM_BYTES
```

Use a Redis REST **read/write** token in an isolated database or keyspace.
Generate the encryption key in a private secret manager; never commit it,
reuse a CI key, or log it. Configure TLS and restrict access to the upstream
FastAPI network. Key replacement invalidates existing sessions unless a
separate key-rotation mechanism is implemented.

## Test coverage and boundaries

The protected-browser CI job runs an explicitly synthetic, loopback-only
Redis REST protocol emulator with two independently started Next.js instances.
The browser logs into instance A, reads cases from B, logs out on B and
verifies that A rejects the old cookie. The mock supports only GET, SET/EX/NX
and DEL and contains no genuine identity or media data.

This is protocol-level **synthetic integration**, not validation against
Upstash in an external network, a multi-region latency benchmark, an outage
recovery audit or evidence of full production deployment security.

## Still required before a pilot

- Centre-scoped officer RBAC across reads, evidence, reports, queries and writes
- Durable backend case/audit/edge storage and transaction boundaries
- Brute-force protection, credential rotation/revocation and real identity
- Redis operational hardening, store monitoring, full HTTPS and reverse-proxy review
- Independent licensed footage, ground-truth accuracy and clean-machine rehearsal
