# KaushalWatch — Verified build and release status

## Current product-release addendum — 20 October 2026

**Redesign R1–R10 has been merged into `main`**, ending at commit [`a8e4442`](https://github.com/dev-ahmed01/KaushalWatch/commit/a8e44427fad37782351b2c1e7bf4954203dcec1b). The primary Next.js workflow now uses **Overview, Issues, Insights, Centre Desk and Chatbox**, plus the secondary `/demo/mission` evidence walkthrough. R10 PR-head CI passed all seven application jobs ([run](https://github.com/dev-ahmed01/KaushalWatch/actions/runs/39447509289)); its release-container job also passed ([run](https://github.com/dev-ahmed01/KaushalWatch/actions/runs/39447506489)). Those PR-head checks alone do not establish a post-merge-`main` run.

**Release acceptance is still open:** full local Windows start/rebuild, visual matching at four viewports, the actual hardware microphone test, server-side Gemini configuration when needed, production Chatbox identity/storage and independent institutional model/field accuracy. Centre Desk and Chatbox are implemented for **local controlled synthetic operations**; they do not constitute live cross-centre deployments. See [redesign release acceptance](docs/redesign-release-acceptance.md).

The remaining research-qualification detail below is a **historical 15 October baseline**, not the current navigation or latest commit inventory. Its privacy, source-licensing and independent-validation cautions still apply.

---

**Historical research review date:** 15 October 2026  
**Source:** [main](https://github.com/dev-ahmed01/KaushalWatch/tree/main), verified baseline commit `b9c0b60ba9c9ace15013175326913ea31b5b868e` (before this housekeeping merge).

> **Release decision: engineering prototype, NOT independently validated for real training-centre compliance or approved for a production pilot.** A green synthetic integration build must never be represented as a field-accuracy qualification.

## Working product

- FastAPI / PostgreSQL backend; Next.js officer interface with KaushalAI, Centres, Insights and Actions; reviewable cases, reports and privacy-transformed evidence.
- Frozen OpenVINO person detector and anonymous temporal attendance counting; practical activity, infrastructure equipment proposal and visually apparent motion workflows.
- Protected browser with HttpOnly sessions, CSRF and same-origin API proxy. Encrypted shared Redis REST session store supports multi-instance session revocation; validated against a **synthetic loopback emulator**, not a production provider.
- Strict PostgreSQL storage, simulated object-store integration and signed synthetic identity/role/tenant tests. Actual external IdP/MFA and production private-cloud security acceptance still pending.
- Last verified Phase 3C suite (PR #59): **480 backend tests passed, 30 skipped; 7/7 CI jobs green**, including protected browser and OIDC synthetic acceptance. See [CI #38689322260](https://github.com/dev-ahmed01/KaushalWatch/actions/runs/38689322260).
- Actual OpenVINO model executed on public/previously inspected EPFL media. The 6-second clip correctly abstains for insufficient evidence; the longer 15-second diagnostic yielded confirmed occupancy. **No institutional accuracy or fraud conclusion follows from this test.**

## Phase 3C qualification gate: current priority

The five independent field-accuracy pillars remain **0 of 5 qualified**:

| Pillar | Implemented gate | Independent institutional accuracy |
| --- | --- | --- |
| Attendance occupancy and discrepancy | Yes | Blocked: authorized untouched multi-scene footage and blind annotations missing |
| Practical activity and authorization | Yes | Blocked: independent activity labels and authorization records missing |
| Camera evidence usability / integrity | Yes | Blocked: independently labelled camera incidents and normal controls missing |
| Equipment presence and raw model counts | Yes | Blocked: blind labels, source permissions and live-detector ground truth missing |
| Apparent motion (ROI proxy only) | Yes | Blocked: independent stable-window visible-motion labels missing |

Phase 3C merged changes:
- [PR #56](https://github.com/dev-ahmed01/KaushalWatch/pull/56): real public EPFL temporal diagnostics and exact-clip regression.
- [PR #57](https://github.com/dev-ahmed01/KaushalWatch/pull/57): held-out engine uses all nine frozen attendance settings, not pipeline defaults.
- [PR #58](https://github.com/dev-ahmed01/KaushalWatch/pull/58): attendance emits `attendance_evidence_insufficient`, withholds unsupported counts and cases.
- [PR #59](https://github.com/dev-ahmed01/KaushalWatch/pull/59): five-pillar global recording/partition provenance preflight, never itself an accuracy pass.

**Experimental Camera Trust [PR #54](https://github.com/dev-ahmed01/KaushalWatch/pull/54) remains draft and unmerged.** Its development UHCTD results include false-alarm and missed-event limitations. Do not force-merge its divergent work into the frozen attendance/practical pipelines.

## Repository integration and cleanup

All four Phase 3C PRs listed above are already squash-merged into `main`. Their historical branch tips matched the recorded heads of merged PRs at this review. The repo has an existing SHA-locked, archive-before-prune workflow in `scripts/archive_merged_branches.py` and `.github/workflows/archive-merged-branches.yml`; it keeps `main`, protected branches, and the experimental Camera Trust branch. **Branch deletion is confirmed only by its own GitHub Actions outcome, not by merge status or script intentions.**

A read-only git-tree inspection at the baseline commit found 344 tracked files (407 tree entries), no obvious tracked CCTV/video clips, virtualenv, `node_modules`, `.next`, large binary model checkpoints or build caches. The existing `scripts/check_repo_hygiene.py` also rejects tracked media/model artifacts and oversized files during CI. Existing documentation/configuration source files are not garbage and must not be bulk-deleted.

See [Phase 3A historical reconciliation](docs/release/PHASE3A_BRANCH_RECONCILIATION.md), [main consolidation](docs/release/MAIN_CONSOLIDATION.md), and [historical STATUS archive](docs/release/STATUS_HISTORY_THROUGH_20261015.md) for past audits. Those older snapshots contain PR statements that have since changed.

## Next agreed milestone

1. Obtain documented institutional rights/permissions and privacy review **without checking raw CCTV, IDs or secrets into GitHub**.
2. Freeze independent recording IDs, training-centre/site and camera boundaries before label review; recruit blind annotators.
3. Run `evaluation/holdout_cohort_preflight.py` on SHA-pinned five-pillar manifests; it checks split integrity, **not accuracy**.
4. Execute all five actual frozen-model held-out evaluators; report per-site/camera count errors, case recall/false alarms, abstention/coverage, and the weakest scenarios, with no label leakage.
5. Only after acceptable independent results: production IdP, scoped RBAC, Redis/S3/KMS/IAM, backup/restore, secure edge transport and controlled centre pilot acceptance.

**Do not label the project pilot-ready based on code/test completion alone.**
