# KaushalWatch OS — Sprint 2: Centre verification cockpit

The centre overview now presents evidence-linked factual counts from the existing centre intelligence endpoint: attendance, equipment quantity, practical work cells, camera status and retained evidence/review workload. Centre navigation and existing detailed tabs remain unchanged.

## Trust and origin
- A numeric observation must derive from a centre-matched active case or analysis history row. Never copy another site's latest analysis.
- Camera status `uncertain` or `unavailable` suppresses reported/observed visual comparisons, not merely the status pill.
- Missing analysis and unknown equipment quantities remain blank/—. No default attendance, fabricated equipment totals or demonstration-only fallback values are inserted.
- Each presented pair includes whether its source is a case or analysis and whether it is simulated.
- These are historic aggregate quantities, not live person-level surveillance or an authorization to make automated sanctions. Officers click the actual case or evidence link for the audit trail and decision.
- UI retains Poppins/Bricolage Grotesque and four primary destinations from Sprint 1.

## Acceptance
- Bengaluru's source-backed attendance case 28/19; other site's infrastructure case never leaks into Bengaluru.
- Hubballi's source-backed equipment case 12/9; separate attendance analysis 26/25.
- Tumakuru with camera obstruction never shows 'healthy' or trusted observed counts.
- Mangaluru empty centre never inherits another centre's analysis history.
- Browser tests verify case navigation, unknowns and narrow-screen viewport; backend tests verify centre isolation and provenance.
- Existing protected officer authorization and immutable case-review workflow unchanged.
