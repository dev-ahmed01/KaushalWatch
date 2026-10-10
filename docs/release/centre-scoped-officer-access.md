# Centre-scoped officer access — synthetic protected release

Status: **implemented as a configuration-backed, server-enforced prototype**.
This is not an external identity provider or government production RBAC.

## Authorization model

| Role | Centre scope | Reads | Review/settings/centre video analysis | Network-wide AI chat |
| --- | --- | --- | --- | --- |
| `network_admin` | All centres | All protected routes | Yes | Yes |
| `centre_reviewer` | Explicit assigned centre IDs | Only own centres, cases, evidence, reports and scoped summaries | Only assigned centres | Denied until tool-level scoped AI is certified |
| `centre_viewer` | Explicit assigned centre IDs | Only own centres, cases, evidence, reports and scoped summaries | No | Denied |

All protected identities have a unique server-owned actor ID and bearer key.
`KAUSHALWATCH_OFFICER_PERMISSIONS_JSON` is an exact map from **each**
`KAUSHALWATCH_REVIEW_TOKENS_JSON` actor to a role and centre IDs. Every
configured actor must be present exactly once. Only listed demo centres
are accepted in the current registry. Network admins use `centres: []`;
no wildcard strings are accepted.

Synthetic example (all strings below are placeholders; never deploy these keys):

```json
{
  "officer-admin": {"role": "network_admin", "centres": []},
  "centre-reviewer": {"role": "centre_reviewer", "centres": ["DEMO-KA-104"]},
  "centre-viewer": {"role": "centre_viewer", "centres": ["DEMO-KA-112"]}
}
```

Export this JSON under `KAUSHALWATCH_OFFICER_PERMISSIONS_JSON` in the
**protected FastAPI server**, separate from the secret bearer mapping.

## Server enforcement

- Protected middleware authenticates the bearer token and resolves the actor's
  role on **every** sensitive request; malformed or missing grant mappings
  return 503 rather than treating the caller as an administrator.
- Centre URL and case ID routes are checked **before** handlers run.
  Unassigned centre and case reads return 404 to minimize enumeration.
- Centre viewer writes return 403. Form upload endpoints verify submitted
  `centre_id` before decoding or persisting video-derived observations.
  JSON assistant queries enforce the requested centre independently.
- Collection endpoints `/api/cases`, `/api/centres`,
  `/api/analysis-history` and `/api/dashboard` are filtered to assigned
  centre IDs, with authorization **before** history paging.
  Network briefs, insights and action queues derive from filtered cases,
  history and centre records instead of trimming completed global metrics.
- Static `/evidence/<id>.jpg` reads resolve the evidence ID to a persisted
  case's centre, then enforce that same scope. Unknown/orphan IDs are denied.
  Evidence-pack and centre report/PDF paths share the same check.
- A centre-scoped officer is denied unknown and unaudited routes. The global
  assistant chat, including tool calls that can reach national aggregates, is
  intentionally network-admin-only. A deterministic centre-targeted
  `/api/assistant/query` remains available in the assigned centre.
- `/api/officer-context` exposes only the caller's role/assigned centre IDs
  and capabilities. It is never public and never returns a bearer token.
  The browser hides final-decision controls from viewers, independently of
  server-enforced 403 responses.

## Test requirements

Run `pytest -q backend/tests/test_centre_permissions.py`.
The new regression set checks scoped collections, cross-centre reports/PDF,
case IDs and evidence references, read-only review rejection, uploaded-form
spoofing, assistant boundaries, unknown routes, malformed identity grants,
and unchanged protected direct access. The protected browser CI additionally
logs in as a distinct synthetic centre viewer and verifies read-only case
review and a forged proxy write denial.

## Limitations / next blockers

The demo fixtures are not a real centre registry. Identity, claims, approvals
and centre memberships are sourced from static protected environment config,
not a managed IdP/database. The backend still uses prototype JSON case
stores, a single-instance assistant memory and lacks transactional multiworker
officer audit, login throttling, credential lifecycle and a reviewed HTTPS
deployment. System-wide API documentation and unscoped video operations
remain inaccessible to centre-scoped roles.

Do not interpret the synthetic authorization and CI checks as proving real
scheme-integration identity, personal-data compliance, governmental security,
field detection accuracy, licensed video, or a production pilot.
