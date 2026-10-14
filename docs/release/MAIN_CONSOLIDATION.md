# Main consolidation and protected historical-branch cleanup

**Executed 14 October 2026.** Repository: `dev-ahmed01/KaushalWatch`.

## Consolidation completed

- PR [#53](https://github.com/dev-ahmed01/KaushalWatch/pull/53) — KaushalAI restructuring — **merged into main** with commit `5b2dc7c59d30bad749567ea418ae246e89ece098`.
- PR [#55](https://github.com/dev-ahmed01/KaushalWatch/pull/55) — integrated SIH release — **merged into main** with commit `62f7a671eb173598049352109abb0edfdf6eb424`.
- Before merging, corrected three review findings in both branches: temporal evidence must use the case's exact centre, batch and bounded time window; practical-analysis time is captured before inference; and unobserved intervals must not be counted as sustained low activity. Added explicit regression tests.
- Restructuring CI **4/4 jobs passed** and release CI **7/7 jobs passed** on their corrected heads. Neither CI result is approval for real-world AI or government compliance claims.

## Branch inventory

At the start of cleanup GitHub reported **61 branches**, **six open PRs**, and **387 tracked tree entries** on the release head. Only PR #53 and PR #55 had passed the scoped merge readiness audit.

Open work to preserve: Camera Trust [PR #54](https://github.com/dev-ahmed01/KaushalWatch/pull/54) is experimental and has not passed fresh held-out camera qualification. Legacy [PR #25](https://github.com/dev-ahmed01/KaushalWatch/pull/25), [PR #31](https://github.com/dev-ahmed01/KaushalWatch/pull/31), and [PR #34](https://github.com/dev-ahmed01/KaushalWatch/pull/34) were already conflicted and have independent history; their changes were **not** forcibly rebased or merged. Non-PR branches may also contain unique work.

Many historical branches differ in commit ancestry from main because past PRs were squash-merged. A positive `behind_by` count **alone does not justify deleting a branch**, even if its feature appears in current main.

## Safe archival and deletion policy

`scripts/archive_merged_branches.py` and
`.github/workflows/archive-merged-branches.yml` implement controlled
GitHub Actions cleanup. The workflow is triggered by the initial script
commit to main and can be rerun manually. It requires `contents:write`.

A branch is eligible for deletion **only when ALL** of these hold:

1. The branch is not the default branch, is not GitHub-protected, and is not the separate Camera Trust candidate.
2. No open pull request points to that branch.
3. An already-merged PR **from the same repository** records that exact source branch and the current branch tip SHA matches the merged PR's head SHA.
4. The current main SHA matches the push that triggered cleanup and did not change during the operation.
5. Before deletion, a lightweight Git tag under `archive/merged-branches/<original-branch>` is created and read back. Its target **must** equal the original branch tip. Existing mismatched tags are never overwritten.
6. The remote branch tip is checked again immediately before deletion. Failure, mismatch, or missing permissions stops deletion of that branch.

This preserves historical commits without retaining cluttered remote branches. Unmerged, orphaned, conflicted, currently open and moved branches remain available for inspection. The workflow writes its exact list of archived/deleted/skipped branches and any failures to the GitHub Actions run summary. **Do not claim a branch was deleted unless that run confirms it.**

## Tracked file hygiene

The release tree was inspected for generated virtual environments, `node_modules`, `.next`, binary model checkpoints, person-identifiable recordings and build outputs. None of those unwanted artifacts were detected in tracked files. Existing configuration examples, reviewed demo JSON, source files and audit documentation are retained intentionally; speculative bulk file deletion could break the working release.

`.gitignore` now additionally excludes private model snapshots, video inputs, temporary databases, local environment secrets, logs, browser reports and cache outputs. Historical audit documents are clearly labelled as snapshots instead of being silently discarded.

## Remaining acceptance blockers

- Independent, lawfully obtained and fully annotated camera datasets must still pass the frozen attendance, camera evidence, practical activity and equipment qualification gates.
- Real identity-provider MFA, S3/KMS/IAM configuration, high availability and recovery must be separately tested.
- PR #54 cannot be presumed safe merely because release CI is green.
- Reconcile and either close or separately integrate conflicted legacy PR #25/#31/#34 after inspection, rather than erasing unverified history.
