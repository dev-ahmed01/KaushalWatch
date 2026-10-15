# KaushalWatch Phase 3C main-integration audit — 15 October 2026

## Evidence checked before housekeeping

- Baseline main: `b9c0b60ba9c9ace15013175326913ea31b5b868e`.
- Exactly one open pull request: [PR #54](https://github.com/dev-ahmed01/KaushalWatch/pull/54), the **draft, unvalidated Camera Trust experiment**. It has not passed untouched camera-heldout promotion and must not be merged.
- Four stale source refs from **already merged** Phase 3C pull requests. Each branch tip was independently confirmed equal to that PR's exact recorded head:

| Merged PR | Exact source branch head SHA | Status before cleanup |
| --- | --- | --- |
| [#56](https://github.com/dev-ahmed01/KaushalWatch/pull/56) | `9b21fc5a698d1a43e6b19981db9a73e883ef8b80` | source branch remains |
| [#57](https://github.com/dev-ahmed01/KaushalWatch/pull/57) | `0cf7334da7ac316feb5ebb70704e27593ea8c851` | source branch remains |
| [#58](https://github.com/dev-ahmed01/KaushalWatch/pull/58) | `3a49987625d34f8a749b901bc1f27e4642338ae4` | source branch remains |
| [#59](https://github.com/dev-ahmed01/KaushalWatch/pull/59) | `98064aefb7fa79047998c7ffe1ce9be38ea20bf2` | source branch remains |

Their Git commit ancestries diverge from main because of squash merging; comparison commit counts alone **do not indicate unmerged feature code**. In a SHA tree comparison, branch #59's 344 tracked files exactly matched main's content; older Phase 3C branches differed only where later merged PRs subsequently updated source. No Phase 3C branch has unique tracked files missing from main.

## Repository hygiene

Main's recursive git tree at the audited baseline contained **407 entries / 344 tracked files**; no committed video, OpenVINO model binaries, virtual environments, `node_modules`, `.next`, or large binary files appeared. No broad source-file deletions are warranted. Current `scripts/check_repo_hygiene.py` and CI already reject generated/binary artifacts.

Historical root `STATUS.md` incorrectly claimed there were only two branches and described older PR #53/#55 as draft; this housekeeping effort archives those historical snapshots and replaces root status with current Phase 3C state. The README's outdated single-process session claim is corrected to describe the opt-in encrypted Redis REST shared store and its real deployment limitations. A duplicate ignored runtime path is removed.

## Controlled source-branch cleanup

The existing [archive workflow](../../.github/workflows/archive-merged-branches.yml) runs after a push to main that changes `scripts/test_archive_merged_branches.py`. The new regression tests pin the four exact merged PR heads and require protection of `fix/uhctd-camera-trust-v2`.

**Deletion is not attested here.** The workflow must:
1. Verify current main SHA and every candidate's unchanged tip against the exact merged PR head SHA.
2. Verify no open PR references the branch and GitHub reports it unprotected.
3. Create an immutable `archive/merged-branches/<branch>` tag and read back its exact tip.
4. Only then delete the source branch through its authenticated GitHub Actions token. Fail closed if SHA, protection, main, tag or authorization changed.

The resulting Actions run summary is the only authoritative cleanup receipt. Never merge/delete PR #54 or its branch. The housekeeping branch itself can be pruned by the same strict process after its PR is merged, with its head archived.

## Next agreed milestone

Prepare lawfully obtained, appropriately consented and privacy-governed independent institutional recordings, establish blind annotations and untouched calibration/holdout splits, run the new five-pillar global cohort preflight, then run all five real model qualification gates before production security and a controlled pilot. **None of these institutional field accuracy gates are presently qualified.**
