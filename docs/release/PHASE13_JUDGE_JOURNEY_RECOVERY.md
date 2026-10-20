# Phase 13 — Judge journey continuity and fail-closed recovery

The controlled mission is a single product story: **reported facts → source evidence → officer case and audit → centre PDF**, with an explicit no-case normal control. This phase closes the two gaps found in the Phase 12 rehearsal: opening a saved officer case discarded the presenter's place, and an undecodable but hash-verified video could remain stuck on a loading mask.

No extra dashboard, route/module, production camera authority, live field metrics or new simulation case has been introduced.

## What changed

**Evidence → case → exact return.** In the controlled mission, a saved case link carries the current allowlisted scenario and selected evidence step. The actual saved case detail screen shows **Return to walkthrough** only when the case centre matches that known demo scenario, e.g. SIM-KA-104-ATT returns to DEMO-KA-104 attendance. Backward navigation resumes the actual selected step (0–3). No caller-supplied URL or cross-centre destination is used. Direct case links opened from Actions still behave as before. The only restored state is the chosen controlled scenario/step, not an officer session, audit mutation or active camera state.

**API failures are not empty cases.** A failed case ledger now shows **Case records unavailable** and **Retry case lookup**. The scenario remains inspectable as an authored example but the app does not claim that the centre has no saved case, nor does it invent a decision. If the case evidence pack is missing, the case screen presents a bounded recovery view with **Retry saved case** and a safe **Open walkthrough** link rather than an indefinitely animated skeleton. A case-pack response whose case ID differs from the requested case is explicitly rejected.

**Browser media recovery.** A procedural video whose signed manifest is verified but whose browser codec/metadata fails no longer displays **Preparing verified recording** forever. An opaque media fallback distinguishes source verification from decoder availability and offers **Retry recording** or **Continue with evidence** to the same mission's evidence trail. Playback/detection controls remain disabled while the video is undecodable. Retrying remounts the video and rechecks the existing source manifest; it never produces synthetic detections as a substitute.

**Judge-compatible narrative.** The four existing scenarios and the manual 60s/3m20s chapter routes are unchanged. The officer chain is the single saved-evidence path and the PDF link still references the real backend PDF endpoint. The existing standalone four-module product remains the source of truth.

## Verification

- Node admission tests: allowlisted mission scenarios, exact evidence-step restoration, safe case identifiers, invalid stage denial, rejection of cross-centre and external redirects.
- Playwright: attendance scenario → Decision → saved officer case → same scenario/step; denied case ledger → retry; missing evidence pack → recover; unavailable video codec → bypass; forged cross-centre case return withheld.
- Existing browser tests: officer evidence integrity and actual PDF bytes, no-case normal control, mobile viewport, OIDC/protected mode, source-locked replay.
- All standard backend, PostgreSQL, frontend, hygiene and protected release-container checks must pass on the PR and on the merged commit.

## Limits

These are controlled workstation reliability checks—not a guarantee of a specific Windows/GPU/browser combination. Browser video failure is never promoted into camera tampering. Saved synthetic cases remain unrelated to the procedural video, the independent field accuracy gate is unchanged, and [Issue #91](https://github.com/dev-ahmed01/KaushalWatch/issues/91) remains OPEN for actual institutional permission, real camera trials and human approval.
