# KaushalWatch Calm Command Centre Redesign

Product direction is unchanged: trusted visual compliance for PMKVY training centres. Reported, Required and Observed states are reconciled into evidence-backed cases. AI surfaces evidence; officers decide. Position is tracked, not identity.

## Stage A — design system

- Page `#F7F8FA`; surface `#FFFFFF`; primary text `#172033`; secondary text `#667085`; border `#E6EAF0`.
- Accent `#2563EB` only for the single primary action and current navigation/tab.
- Verified `#067647 / #ECFDF3`; review `#B54708 / #FFFAEB`; critical `#B42318 / #FEF3F2`; unavailable `#475467 / #F2F4F7`.
- Geist/Inter-style system stack; five sizes only: 40, 28, 20, 16, 14. Weights 400/500.
- 8px grid; page padding 40px; max content width 1200px; 48–64px section spacing; 24px card gaps; 24–32px card padding.
- Radius 16px; hairline borders; shadow `0 1px 2px rgba(16,24,40,.04)`.
- Status semantics: VERIFIED, NEEDS REVIEW, UNCERTAIN, OFFICER REVIEW, ANALYSIS UNAVAILABLE, RESOLVED.
- Operability terms are limited to PRESENT, APPARENTLY ACTIVE, APPARENTLY INACTIVE, UNCERTAIN and OFFICER VERIFICATION REQUIRED.
- Components: StatusPill, five-pillar strip, quiet metric/fact, case row/card, EvidenceFrame, PersistenceTimeline, EmptyState, AssistantDrawer, AnalysisModal and Toast.
- Motion is 150–200ms and removed under `prefers-reduced-motion`.

## Stage B — sitemap

Primary navigation has exactly three destinations:

```text
Network
  └── Centre
      ├── Cockpit
      ├── Attendance
      ├── Practical
      ├── Infrastructure
      └── Evidence
Cases
  ├── Review Queue
  ├── Escalations
  └── Case Detail
Reports
  ├── History
  └── Analytics
```

### Old → new mapping

| Old screen | New location | Decision | Reason |
|---|---|---|---|
| Network Overview | Network | Redesign | Map is the hero; exceptions stay secondary. |
| Centres | Network / List toggle | Merge | A separate centre directory duplicates the network. |
| Centre Overview | Centre / Cockpit | Redesign | One decision surface with five pillars. |
| Attendance Verification | Centre / Attendance | Keep as tab | Evidence and reported-vs-observed belong together. |
| Practical Work Verification | Centre / Practical | Keep as tab | Same evidence pattern; no separate sidebar item. |
| Infrastructure Verification | Centre / Infrastructure | Keep as tab | Same evidence pattern; operability language stays bounded. |
| Evidence galleries | Centre / Evidence + Case Detail | Merge | Integrity/provenance should be inspectable without another nav destination. |
| Review Queue | Cases / Review Queue | Move | Human decisions are a primary task. |
| Escalations | Cases / Escalations | Merge | Escalation is a case priority, not a separate product area. |
| History & Audit | Reports / History | Merge | Audit history and generated reports share the same evidence record. |
| Analytics | Reports / Analytics | Merge | Analytics is supporting context, not primary navigation. |
| Final Outcome | Centre Cockpit + Case Detail | Merge | Centre state and officer case outcomes already express the result. |
| Centre Analysis | Analysis modal | Merge | Running analysis is an action, not a destination. |
| Settings | Removed from primary product | Remove | It does not help the officer decide faster in the SIH demo. |
| Permanent AI panels | Assistant drawer | Replace | Assistant supports evidence review without competing for screen space. |

## Stage C — wireframes

### Network — 58 interface words

Hero: Karnataka map. Supporting elements: needs-attention list (max 3), quiet network count line. Primary action: **Open priority centre**.

```text
┌ Network                         [Open priority centre] ┐
│ Exceptions first across Karnataka training centres.   │
│                                                       │
│ ┌────────────────────────────── [Map | List] ───────┐ │
│ │                    KARNATAKA                       │ │
│ │          • Belagavi       • Hubballi              │ │
│ │                • Tumakuru                         │ │
│ │       • Mysuru             • Bengaluru            │ │
│ │          • Mangaluru                              │ │
│ └───────────────────────────────────────────────────┘ │
│                                                       │
│ Needs attention                  Network summary      │
│ Bengaluru TC-04  NEEDS REVIEW    2 verified           │
│ Tumakuru TC-07   UNCERTAIN       2 need review        │
│ Hubballi TC-03   NEEDS REVIEW    1 uncertain          │
└───────────────────────────────────────────────────────┘
```

Empty: “No centres need attention. All available checks are verified.” Loading: map skeleton only. Error: “Live summaries unavailable. Showing simulated demo states.” Uncertain: grey marker and explicit reason.

### Centre Cockpit — 92 interface words

Hero: Needs your decision case card. Supporting: five-pillar strip, last/next analysis line, evidence + temporal proof one fold below. Primary: **Run analysis now**.

```text
Bengaluru TC-04              [Ask assistant] [Run analysis now]
Construction Electrician - LV · ELEC-2026-08
NEEDS REVIEW · Last 14:30 · Next 15:30 · Simulated records

[Cockpit] [Attendance] [Practical] [Infrastructure] [Evidence]

Attendance      Practical       Infrastructure   Camera     Evidence
NEEDS REVIEW    VERIFIED        VERIFIED         VERIFIED   VERIFIED
Presence gap    Activity seen   Assets aligned   Clear view Original retained

Needs your decision
┌ Attendance needs review ───────────────────────────────┐
│ Reported 28. Sustained visual evidence shows 19.      │
│ Persisted across 3 analysis periods.                  │
└────────────────────────────────────────────────────────┘

[Evidence]                          [Temporal Proof]
```

Empty: “All checks verified. No open evidence-backed cases for this centre.” Camera error: dependent pillars become UNCERTAIN, never compliant. Loading: title plus one strip skeleton.

### Attendance — 57 interface words

Hero: retained evidence. Supporting: Reported, Observed, Status. Primary: **Run analysis now**.

```text
Attendance                     [Ask assistant] [Run analysis now]
Reported presence compared with sustained visual evidence.

[Cockpit] [Attendance] [Practical] [Infrastructure] [Evidence]

┌ Evidence player ───────────────┐  Reported  28 · Simulated
│ People anonymized             │  Observed  19
│ Camera trusted                │  Status    NEEDS REVIEW
└───────────────────────────────┘

Temporal Proof: ●──●──●──●
Discrepancy persisted across multiple analysis periods
[Technical details ▾]
```

Practical and Infrastructure reuse this structure. Practical observed wording is APPARENTLY ACTIVE / APPARENTLY INACTIVE / UNCERTAIN. Infrastructure uses PRESENT and OFFICER VERIFICATION REQUIRED; it never claims a machine “works”.

### Cases — 48 interface words

Hero: review queue. Supporting: Review Queue/Escalations tabs, priority filter, quiet open-case count. Primary: **Open highest priority**.

```text
Cases                              [Open highest priority]
Evidence-backed discrepancies awaiting officer decisions.

[Review Queue] [Escalations]                Priority [All ▾]

Attendance discrepancy   Bengaluru TC-04   OPEN          ›
Infrastructure gap       Hubballi TC-03    OPEN          ›

2 open review items · Escalation never confirms an outcome automatically.
```

Empty: “No cases to review.” Loading: three list-row skeletons. Error: retains simulated preview when live cases cannot load.

### Case Detail — 81 interface words

Hero: evidence. Supporting: one-paragraph summary, review controls, collapsed audit trail. Primary: **Confirm**.

```text
Attendance discrepancy
OPEN · DEMO-KA-104 · ELEC-2026-08

┌ Evidence player ──────────────┐  Plain-language summary
│ retained frame               │  Persistent mismatch created
│ camera trusted               │  a case; no automatic decision.
└───────────────────────────────┘

Officer note
[ Record the reason for your decision... ]

[Confirm] [False positive]
[Virtual verification] [Resolve]

Audit trail · 2 events ▾
```

Final outcomes require an officer note. Open cases transition through Under Review in the persisted audit trail before terminal actions.

### Reports — 63 interface words

Hero: Centre Verification Report preview. Supporting: date chips, centre selector, History/Analytics tabs. Primary: **Download PDF**.

```text
Reports                                      [Download PDF]
Auditable centre verification across a selected date range.

[History] [Analytics]                 [Bengaluru TC-04 ▾]
[Today] [7 days] [30 days] [Custom]

┌ Centre Verification Report ─────────────────────────────┐
│ Bengaluru TC-04 · Last 7 days             OFFICER REVIEW│
│ Analysis runs  Open cases  Evidence integrity           │
│ Attendance          NEEDS REVIEW                        │
│ Practical Activity  VERIFIED                            │
│ Infrastructure      VERIFIED                            │
│ Camera Integrity    VERIFIED                            │
│ Evidence Integrity  VERIFIED                            │
└──────────────────────────────────────────────────────────┘
```

No-data: report preview remains but says “No recorded analyses fall inside this date range.” Custom range requires both dates before download.

### Assistant Drawer — 51 interface words

Hero: current conversation. Supporting: three starter questions. Primary: Send button.

```text
                         ┌ KaushalWatch Assistant       × ┐
                         │ Ask about available evidence.  │
                         │                               │
                         │ What happened today?          │
                         │ Why was attendance flagged?   │
                         │ Which equipment is repeatedly │
                         │ missing?                      │
                         │                               │
                         │ [ Ask about this centre… ] [↑]│
                         │ AI surfaces evidence.         │
                         │ Officers decide.              │
                         └───────────────────────────────┘
```

Unconfigured state stays inside the drawer: “Assistant unavailable. Evidence review remains available throughout KaushalWatch.”

### Analysis modal — 58 interface words

Hero: four real processing steps. Supporting: selected evidence file, simulated reported attendance. Primary: **Start analysis**.

```text
Run analysis
One recording, four auditable steps.

Visual evidence [choose file]     Reported attendance 28 · Simulated

1 Manifest reading      ✓ Construction Electrician - LV
2 Visual evidence       ↻ Reviewing retained evidence
3 Temporal Proof        · Persistence is evaluated across time
4 Case evidence         · Preparing evidence-backed cases

[Technical details ▾]                       [Start analysis]
```

No invented percentage is shown. A failed checkpoint is marked unavailable and its dependent conclusion is suspended.

## Cut decisions

- Separate Centres screen: duplicates Network.
- Permanent assistant: competes with evidence.
- Notification UI: not part of the decision workflow.
- Settings navigation: not required for the SIH officer demo.
- Vanity KPI cards and charts: do not change a review decision.
- Raw detector confidence/backend labels: technical details only.
- Dark dashboard chrome: increases perceived monitoring intensity without adding meaning.
