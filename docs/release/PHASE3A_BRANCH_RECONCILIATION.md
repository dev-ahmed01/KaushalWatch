# Phase 3A — Final historical branch reconciliation

**Date:** 14 October 2026  
**Repository:** `dev-ahmed01/KaushalWatch`  
**Before this pass:** `main` at `c6e92ab`; 13 live branch refs, including 12 non-main heads; open PRs #25, #31, #34 and experimental #54.

## Review outcome

PR #53 (restructuring) and PR #55 (integrated release) were already merged with passing CI. Their presence in main does **not** imply all historical commits from all remaining divergent branches are in main. Each of the following eleven refs has independently diverged ancestry and distinct older-version diffs. The original head SHA will therefore be archived **without claiming it was merged**.

| Branch | Disposition and reason |
| --- | --- |
| `agile/auditability-cycle-8` | PR #25: superseded monolithic dashboard; current route-based protected review and audit features are in main. Old PR has unresolved P1 browser strict-locator feedback. Close as superseded, archive exact head. |
| `redesign/full-command-centre-v3` | PR #31: legacy animated progress component and reports routes differ from current app. Open P2 review identifies progress regressing to 25% during long processing. Close rather than merging an outdated progress overlay. |
| `redesign/portfolio-review-report-v3` | PR #34: former outcome/history/assistant layouts were replaced by newer centre and insights routing. Two P2 review issues remain: contextual suggested questions route to generic response and sidebar escalation counts do not refresh. Close as superseded; preserve history. |
| `agile/demo-operations-cycle-4` | Older staged demo API and review flow; retained release includes newer protected officer review, PostgreSQL audit and dedicated tests. Archive for possible historical comparison; do not transplant old code. |
| `agile/product-clarity-cycle-2` | Older monolithic dashboard and vision-pipeline shape, superseded by current route-based frontend and separately qualified evaluation framework. Archive. |
| `audit/full-ui-visual-check` | Historic Playwright visual-audit workflow only; useful test ideas may be recovered from tag later, but it was not validated against the current Next.js routes. Archive rather than silently installing stale selectors. |
| `cycle/grounding-cache-hardening` | Old grounding cache and precompute trial. New release includes reviewed cache diagnostic and optional offline model inference; original trial must not override the frozen profile. Archive original. |
| `cycle/operability-window` | Older ROI-window experiment. Main now has a separately frozen multi-video visual-motion evaluation; old experiment remains available under tag for reproductions. |
| `experiment/dod-grounding-review` | Exploratory GroundingDINO workflow. Contains remote-download/test assumptions not accepted as a qualified model. Preserve under archive tag; do not auto-enable it on main. |
| `feature/free-ai-providers` | Previous alternative assistant/voice provider experiment. The current protected assistant code has different authentication and isolation guarantees; do not reintroduce unaudited provider/network calls. Recover by archived tag if separately approved. |
| `redesign/product-v2-polish` | Prior activity, attendance and infrastructure page refinements. Current product uses different centre evidence tabs, so cherry-picking stale UI is not justified. Archive. |

**Retained as live branch:** `fix/uhctd-camera-trust-v2`, draft [PR #54](https://github.com/dev-ahmed01/KaushalWatch/pull/54). Its 34 changed files include camera trust engine/diagnostics and intersect the released vision pipeline. Its previously inspected UHCTD recordings are not untouched held-out evidence. Do not merge, close or delete until independent qualification and explicit code review.

## Technical cleanup method

One-time `scripts/reconcile_legacy_branches.py` with
`.github/workflows/reconcile-legacy.yml` runs only when its own files
are pushed to main. It uses a literal allowlist of eleven branch names and
their 40-character SHAs. The workflow is **not** a wildcard pruning job.

1. Verify the exact triggering main SHA, all expected branch tips and
   existing legacy PR heads.
2. Create and read back lightweight, immutable Git tags at
   `archive/reconciled-20261014/<original-branch>`. If any tag fails
   verification, stop before closing PRs or deleting any branch.
3. Add an explanatory comment to PR #25, #31 and #34; close them as
   *superseded*, **not merged**. Preserve their archived source commits.
4. Refetch open PR heads. Delete an audited branch only when its tip
   still matches the pinned SHA, its archival tag resolves to that SHA,
   and it has no open PR or protection rule.
5. On a retry, verify archive tags for any already-deleted refs.
   GitHub Actions run summaries report exactly how many refs were archived,
   PRs closed and branches deleted. Errors fail the workflow.

This process **does not import unique old experiments into main**. Archival
tags retain exact historical content and enable a future targeted restore.

## Tracked files and safety

The post-merge repository's tracked tree was previously checked for local
videos, model snapshots, `node_modules`, virtual environments, built
`.next` files and private credentials; no obvious tracked junk was found.
Its `.gitignore` prevents future additions of those categories.

Deleting old experiments' *branches* must not be confused with deleting
working source files from `main`. No file is deleted purely because its
name looks unused. This phase adds small, auditable reconciliation code and
tests; existing protected officer workflows and model pipelines are untouched.

## Verification and remaining release work

**Verified branch reconciliation:** [GitHub Actions run #38602907177](https://github.com/dev-ahmed01/KaushalWatch/actions/runs/38602907177)
completed successfully. All eleven fixed-SHA legacy branches were archived at
`archive/reconciled-20261014/<branch>`, then removed. The previously open
legacy PRs #25, #31 and #34 were closed as superseded, **not merged**.
GitHub now reports only `main` and the unmerged Camera Trust candidate.
Total across the two cleanup passes: **59 deleted branch refs**, all archived.

**CI after first reconciliation commit:** [GitHub Actions run #38602907134](https://github.com/dev-ahmed01/KaushalWatch/actions/runs/38602907134).
The real-world evaluation and pilot readiness gates remain separate; consult
the workflow run for its latest pass/fail status.

Real-camera accuracy (attendance, camera evidence, practical activity,
equipment and visual motion) and live IdP/AWS pilot acceptance are still
unqualified. Finishing Git housekeeping does **not** advance those gates.
