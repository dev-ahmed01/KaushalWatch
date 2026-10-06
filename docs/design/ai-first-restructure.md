# KaushalWatch AI-first restructure

This branch restructures the product around a simpler mental model:

**KaushalAI tells the officer what changed. Centres explain why. Insights show the pattern. Actions tell the officer what to do next.**

## Build phases

### Phase 1/9 — Product shell and information architecture
- Replace Network / Cases / Reports with KaushalAI / Centres / Insights / Actions.
- Establish low-clutter shell, date-range control and global Ask KaushalAI entry point.
- Keep old URLs as redirects.
- Restrict the new experience to five demonstration centres.
- Establish first-pass screens for all four destinations.

### Phase 2/9 — KaushalAI daily brief
- Add a backend network briefing endpoint/tool.
- Ground daily/weekly summaries in recorded analysis, cases, camera trust and evidence integrity.
- Add AI recommendations with links to source evidence.
- Add graceful unconfigured state.

### Phase 3/9 — Centres and centre overview
- Rework centre detail into the clicked-centre experience.
- Add six engine summaries: attendance, practical, infrastructure, camera, evidence and apparent operability.
- Add contextual KaushalAI centre brief.
- Add centre metadata/contact model.

### Phase 4/9 — Activity intelligence
- Add time-bucketed practical activity aggregation.
- Calculate busiest and least-active periods from trusted evidence only.
- Build Activity & evidence sub-screen.
- Add centre-head follow-up suggestion without automatic enforcement.

### Phase 5/9 — Evidence and officer review
- Consolidate evidence viewer, reported-vs-observed facts, Temporal Proof and integrity checks.
- Preserve human review state machine and audit history.
- Keep raw detector metrics under technical details only.

### Phase 6/9 — Insights
- Add real visual aggregations for attendance, activity, infrastructure, camera trust and case outcomes.
- Replace temporary CSS visualizations with real data-driven charts.
- Keep the page chart-led and low text density.

### Phase 7/9 — Actions
- Build a grounded action recommendation service.
- Rank evidence-backed actions by urgency and evidence quality.
- Add follow-up scheduling and centre contact workflow.
- AI recommends; officers decide.

### Phase 8/9 — Vision and dataset hardening
- Expand fixed-camera validation datasets for attendance, practical activity and infrastructure.
- Add explicit validation gates for each engine.
- Keep source-bound reviewed infrastructure evidence.
- Improve generalization without overstating model performance.

### Phase 9/9 — QA, accessibility, performance and demo hardening
- Browser/a11y review, keyboard navigation, reduced motion, loading/error/empty states.
- Validate responsive hierarchy.
- Rehearse the full judge path on prepared demo data and reviewed footage.
- Squash and release only after full CI is green.

## UX rules locked for this restructure
- One hero per screen.
- At most two supporting modules above the fold.
- 40%+ breathing room target.
- One filled primary action per view.
- No raw ML metrics on primary screens.
- No decorative alert colors.
- Status, reason, action: that is the default card hierarchy.
- KaushalAI stays informative and actionable, not chat-first.
- Missing or untrusted evidence never becomes a verified conclusion.
- AI surfaces evidence. Officers decide.
