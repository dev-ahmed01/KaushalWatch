# Organization OIDC identity — protected API and browser code flow

The authenticated officer API and Next.js browser now support organization
SSO using OAuth 2.0 Authorization Code + PKCE (S256). No government identity
provider is configured by this commit, and no production login is claimed.

## Deployment modes

**Development/SIH demo:** `KAUSHALWATCH_ENV=development`,
`KAUSHALWATCH_REVIEW_AUTH_MODE=demo`. No SSO dependency.

**Synthetic protected staging:** `KAUSHALWATCH_ENV=staging`,
`KAUSHALWATCH_REVIEW_AUTH_MODE=token`, matching synthetic officer grants;
`KAUSHALWATCH_WEB_IDENTITY_MODE` omitted. Existing officer-key tests and
distributed server-side sessions continue to work.

**Pilot/production:** `KAUSHALWATCH_ENV=pilot` or `production`,
`KAUSHALWATCH_REVIEW_AUTH_MODE=oidc`,
`KAUSHALWATCH_WEB_AUTH_MODE=protected`,
`KAUSHALWATCH_WEB_IDENTITY_MODE=oidc`. Static bearer-key mode fails closed
on protected API routes regardless of whether old keys remain configured.
In addition to identity, pilot still requires PostgreSQL, private S3 and
valid KMS configuration. Use the settings in backend and web `.env.example`
as secret-manager references, not as committed deployment secrets.

## Identity contract

The API's `KAUSHALWATCH_OIDC_ISSUER` is the literal, pinned OIDC issuer.
`KAUSHALWATCH_OIDC_AUDIENCE` must designate the **KaushalWatch backend
API**, not the browser OAuth client. The pinned
`KAUSHALWATCH_OIDC_JWKS_URL` must be HTTPS on the *same trusted host and
port* as the issuer; no dynamic redirect/discovery URLs are accepted.
Tokens must have an RS256 signature with exactly one matching RSA JWKS
`kid`, verified `iss`, `aud`, `sub`, `iat`, `nbf`, `exp`, an
access-token type (not an ID token), and lifetime at most one hour.
The API never trusts client-provided officer names or roles.

Each verified `sub` must appear in an operator-managed, server-only
`KAUSHALWATCH_OIDC_GRANTS_JSON`, mapping subject to:
```json
{
  "unique-issuer-subject-123": {
    "actor": "officer-operations-01",
    "role": "centre_reviewer",
    "centres": ["DEMO-KA-104"]
  }
}
```

This map is deliberately provisioned separately from IdP email, groups
or profile attributes. Role and centre membership must be approved by an
administrator. Subjects not in the registry receive 403 even if signed and
otherwise valid. Removal from the registry takes effect on the next API
request, without waiting for a browser session to expire. Untrusted,
expired, forged or wrong-audience tokens receive 401.

**Provider compatibility:** The IdP must issue an RS256 JWT **access token**
for the configured API audience and a token type of `Bearer`.
Some providers use opaque access tokens or different token use claims.
Configure the issuer's access-token policy accordingly; do not loosen
signature/audience validation to accommodate an opaque token.

## Browser sign-in

The server-only `web/app/api/auth/oidc/start` route constructs a fixed
authorization URL with PKCE S256 and a random state, and writes an
AES-256-GCM encrypted, HttpOnly five-minute transaction cookie. The cookie
uses SameSite=Lax so the IdP can redirect to the callback; it contains no
bearer token.

The callback rejects invalid/expired state, missing authorization codes,
unexpected IdP redirects, or unsuccessful token exchange. It exchanges the
code server-side at the pinned HTTPS token endpoint using the original
PKCE verifier and exact redirect URI. It sends the access token only to the
internal FastAPI `/api/officer-validate` endpoint. After signed token
validation and provisioning approval, it stores the token in the existing
AES-256-GCM encrypted server-side Redis REST session and sets a short-lived,
HttpOnly, SameSite=Strict browser cookie. Session TTL is capped by the
provider access token's lifetime; access tokens never go into client-side
storage or a browser URL.

Logout invalidates the local distributed session. It does not currently
perform OIDC RP-initiated logout against the IdP; a new SSO sign-in may be
immediately approved if the organization's browser IdP session is still
active. Obtain a provider-specific sign-out/revocation design before
claiming global session revocation.

## Boundaries and operational obligations

- Use a dedicated **confidential HTTPS deployment** for the browser and a
  restricted backend network; never deploy Redis/API credentials as
  `NEXT_PUBLIC_*`.
- Register exactly the callback URL at the chosen provider and request the
  appropriate API-audience JWT using provider-specific configuration.
- Test provider JWKS rotation, MFA/conditional access, subject lifecycle,
  clock drift, role revocation, expired access-token logout, and HA session
  storage under the actual production IdP.
- Limit external admin access, enforce upstream identity-provider login
  throttling and MFA, and protect FastAPI directly against public traffic.
  This phase does not implement per-IP/server-side credential stuffing
  rate limiting at the IdP or production identity lifecycle provisioning.
- The current role registry recognizes only configured demo-network centre
  IDs. A deployment with real centres needs a durable, operator-managed
  centre registry, migration, administrative grant workflow and audits.
- Avoid inferring government certification from synthetic RS256 tests.
  Cryptographic CI tests use new ephemeral RSA keys, never production keys.

**Verification:** Backend `test_oidc_identity.py` checks signed tokens,
spoofed group/role claims, wrong issuer/audience, expired and wrong-type
tokens, forged signing key, unsupported algorithms, invalid JWKS URLs,
unprovisioned subjects and immediate grant revocation. Next.js build verifies
that the browser sign-in/callback compile; a live provider end-to-end
authentication rehearsal remains outstanding.
