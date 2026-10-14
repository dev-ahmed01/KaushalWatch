# KaushalWatch RC1 — Release Integration Audit

**Historical snapshot notice (14 October 2026):** This document records the state *before* consolidation. PR #53 and PR #55 have since been merged into `main` (merge commits `5b2dc7c` and `62f7a67`). PR #54 remains experimental and unmerged. See `docs/release/MAIN_CONSOLIDATION.md` for the current disposition.

**Date:** 14 October 2026  
**Source branch:** `release/kaushalwatch-sih-mvp` (draft PR #55)  
**Direct target:** `restructure/kaushalai-first-v1` (PR #53, still unmerged)  
**Default branch:** `main` — not modified by this audit  
**Other draft:** `fix/uhctd-camera-trust-v2` (PR #54)

## Scope and branch reconciliation

GitHub comparisons at audit start:

| Comparison | Relationship | Commit gap | Changed files |
| --- | --- | ---: | ---: |
| `main` → restructuring branch | strictly ahead | 143 | 63 |
| restructuring branch → release | strictly ahead, mergeable | 222 | 120 |
| restructuring branch → Camera Trust candidate | strictly ahead | 53 | 34 |
| Camera Trust candidate → release | **diverged** | release +222 / camera +53 | separate |

PR #55 currently reports mergeable (no GitHub merge conflict), but it is
**draft and not reviewed**. The absence of a merge conflict does not prove
functional or behavioral compatibility with a later PR #53 merge into main.

PR #54 and #55 touch two shared modules:
`backend/app/services/video_pipeline.py` and
`backend/app/services/practical_activity_pipeline.py`. The other 32 PR #54
files are not in #55. The camera candidate must stay isolated pending
independent, held-out ground-truth verification; a text-level auto-merge
would be scientifically misleading.

Review/comments at audit start: no published PR #55 review threads or
discussion comments. Human approval has not been obtained.

## Cross-system acceptance coverage

Previous CI covered these paths separately:

- PostgreSQL case decisions, review history, edge receipts, storage migration,
  SQL recoverability and private evidence index, using temporary PostgreSQL
  and simulated S3, with synthetic staging access keys.
- OIDC code+PKCE browser login, signed RS256 access tokens, Redis session
  issuance/logout and centre-restricted browser queries, using JSON fixtures.

The release audit adds **one shared strict-staging runtime** test in
`backend/tests/test_release_integration.py` which exercises:

1. Ephemeral RS256 JWT claims verified against pinned issuer, audience and
   JWKS, with server-provisioned subject→officer role and centre grants.
2. Real PostgreSQL persistence for cases and immutable officer review
   histories; the admin/reviewer/viewer receive distinct authorization.
3. Private object image upload metadata in PostgreSQL and simulated
   conditional, KMS-labelled object storage, then retrieval through
   `/evidence/{id}.jpg` only after authenticated case/centre checks.
4. Cross-centre image denial **before the S3 read**, read-only viewer write
   denial regardless of spoofed JWT groups, and an authorized centre review
   persisted in a separate database connection.
5. Revoked subject denial on the next request, corrupt image SHA fail-closed,
   wrong audience and unprovisioned subject denial, and strict-staging
   `/api/ready` validation.
6. No real people's images or personal information. All image frames are
   generated in memory, keys are ephemeral, and PostgreSQL is the disposable
   `kaushalwatch_ci` database only.

The new tests are added to the `postgres-persistence` CI job. Their success
proves *application-level cross-stack integration under synthetic cloud and
identity conditions* — **not** actual S3 encryption, deployed IAM/KMS policy,
real IdP MFA, real Redis availability, independent vision accuracy, or
live camera acquisition.

## Release gate

Do not mark release integration “merge approved” unless:

- Latest PR #55 head has completed all CI jobs successfully, including
  backend, PostgreSQL cross-stack, two existing browser suites, signed OIDC
  browser suite, dependencies and hygiene.
- Any open PR review threads and branch conflicts have been resolved after
  reviewing the final diff.
- Human maintainers decide the proper sequencing for PR #53 vs PR #55.
  Only then update PR #55 from draft and merge into its reviewed target.
- Do not merge the scientifically unvalidated Camera Trust PR #54 into
  a claims-bearing release automatically.
- Real CCTV efficacy / pilot use has its own distinct evidence gates;
  synthetic CI completion never authorizes those claims.

### Security and operational boundaries

- **Known design limitations:** The app still uses a fixed
  `DEMO_CENTRES` allowlist for officer grant validation, no live operator
  provisioning UI or MFA enforcement, an in-memory conversational history
  and local model inference state. Real-centre onboarding needs a durable
  centre registry and lifecycle controls.
- **Public cloud tests not performed:** No real IAM/KMS bucket introspection
  or failover drill, and no live external IdP was contacted.
- **Vision claims not qualified:** No independently labeled real-centre
  attendance, practical-work or equipment benchmarks passed here.
- **Operational scope:** This is a repo-level CI audit and merged-code
  integration seam test, not a clean-machine multi-region pilot rehearsal.

## Follow-on release tasks

1. Close any failed CI issues, rerun all relevant jobs, update PR #55 with
   verifiable results and seek human review.
2. Decide whether to merge PR #53 first into main; release PR #55 should
   only be promoted after target integration approval.
3. Continue independent camera-dataset qualification without importing
   unvalidated PR #54 outputs.
4. Perform live, documented provider/cloud staging acceptance and
   redacted operator signoff before any real-person-footage pilot.

**Never delete or force-merge historical branches based solely on this report.**
