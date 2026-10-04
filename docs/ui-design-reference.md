# KaushalWatch UI / UX Design Reference

Design lock date: 2026-10-04

KaushalWatch is designed as a multi-page operational command centre, not a single long scrolling dashboard. The current implementation is an original interface informed by established monitoring, security-operations, SaaS and enterprise workflow patterns.

## Approved product structure

### Network level
1. Network Overview
2. Centres directory
3. Escalations
4. Reports
5. Analytics
6. Settings

### Selected-centre level
1. Centre Overview
2. Centre Analysis launcher
3. Attendance Verification
4. Practical Work Verification
5. Infrastructure & Asset Verification
6. Review Queue
7. Final Review Outcome
8. History & Audit

The left navigation must change routes/pages. It must not behave like a single page with sections that only scroll downward.

## Approved layout language

- Dark navy operational sidebar
- Light neutral workspace
- Blue primary actions
- Green = compliant / complete
- Amber = attention / officer review
- Red = confirmed exception / critical issue
- Purple = evidence-integrity / duplicate-evidence signal
- Persistent AI assistant on the right side of selected-centre workspaces
- Sticky top bar with search, monitoring state and officer identity
- Large readable headings, restrained metadata, generous whitespace
- One visually dominant primary action per page
- Technical overrides hidden under Advanced controls
- Subtle motion only: page entrance, card lift, running step pulse, assistant typing and state changes

## Centre workflow

The centre workflow is visually represented as:

Attendance -> Practical Work -> Infrastructure -> Review Outcome

Each step can be:
- Pending
- In progress
- Completed
- Needs review
- Blocked

A blocked step is not treated as a genuine zero or failure result. For example, an unavailable attendance detector must withhold the decision rather than silently reporting zero occupancy.

## AI assistant

The assistant is an evidence-grounded compliance copilot, not an independent vision model.

It may answer:
- What happened today?
- What happened last week?
- Why was this flagged?
- Which work zone was active?
- Which infrastructure item is missing?
- What requires officer verification?
- Why is this centre escalated?
- Create a report summary.

Assistant answers must be based on structured KaushalWatch outputs: analyses, cases, authorization state, camera trust, escalation state and analysis history.

The assistant should use plain language. Example:

Bad:
> stable occupancy median = 3, discrepancy = 0%

Preferred:
> 3 people were consistently visible. The centre reported 3 trainees, so attendance matches.

## Multi-centre operation

KaushalWatch is not a single-centre product.

The Network Overview must show multiple training centres and make it possible to drill into one selected centre for detailed verification. Demo data may focus on Bengaluru TC-04 while still portraying a wider network.

Network-level views should surface:
- total centres
- compliant centres
- centres requiring review
- high-priority centres
- camera issues
- escalation concentration
- centre status table / directory

## Manual and automatic analysis

Normal deployment is automatic scheduled monitoring.

Manual Start Analysis remains available for:
- demonstrations
- rechecks
- uploaded recordings
- officer-triggered verification

The centre overview and analysis launcher should show:
- automatic vs manual mode
- monitoring schedule
- next run
- Run analysis now
- Recent Analysis
- Generate Report

## No-feed / no-photo states

Centre imagery is optional. A missing centre photo must show a clean neutral placeholder, not a broken image.

A missing camera feed must show:
- No Video Feed Available
- Retry connection
- Upload recorded video
- clear statement that analysis can run on a recording

No-feed states must not look like system failure unless camera integrity itself is the issue.

## Attendance page

Primary question:
> Does stable physical presence match the submitted attendance record?

Layout:
- video / evidence area
- compact result panel
- reported count control
- recent analysis
- AI assistant

Do not show detector failure as zero attendance.

## Practical Work page

Primary question:
> Is sustained practical activity visible, and does external authorization support it?

Vision establishes:
- stable anonymous worker presence
- work-cell association
- worker-centric motion

Authorization remains external context.

Advanced zone JSON should never be required for the default demo.

## Infrastructure page

Infrastructure must visibly preserve the three verification tiers:

1. Camera-verifiable
2. Partially verifiable
3. Officer-only

The system must never imply that officer-only items were camera verified.

The current demonstration uses stage-safe demo telemetry for equipment counts while uploaded video supplies review imagery / optional motion evidence. This limitation should remain visible.

## Review Queue

The Review Queue is a split operational workspace:
- case list on the left
- selected case and evidence in the centre
- AI assistant on the right

Final decisions require:
1. evidence inspection
2. active review / virtual verification
3. officer rationale
4. final decision

Duplicate evidence must have a distinct integrity treatment separate from the main compliance finding.

## Escalation

Escalation depends on recurrence, severity, unresolved duration and independent signals rather than raw discrepancy count alone.

Examples:
- repeated attendance discrepancy -> regional attention
- unresolved case beyond SLA -> escalation
- attendance + infrastructure issue -> higher priority
- duplicate evidence + compliance discrepancy -> multi-signal escalation

## Reports and history

Recent Analysis gives fast access to completed centre runs.

History must support:
- Yesterday
- Last 7 days
- Last 30 days
- analysis-type filtering

The AI assistant can answer questions about historical periods and send the officer to a report.

Reports must include:
- executive summary
- recent analyses
- pending cases / escalation
- privacy note
- system limitations

Browser print / Save as PDF is the current stage-safe report export.

## Privacy and bandwidth

Locked rules:
- no facial recognition for attendance
- anonymous positional tracking
- raw continuous video is not required centrally
- edge processing can sync summaries and exception evidence only
- camera-trust failures suspend affected conclusions
- AI does not issue penalties
- human review remains mandatory for final case resolution
