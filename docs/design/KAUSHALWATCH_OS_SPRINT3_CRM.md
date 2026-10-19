# KaushalWatch OS Sprint 3 — CRM-inspired officer desk

This sprint makes the existing four-module operations OS usable as a training-centre **casework CRM**, without treating trainees as sales leads or collecting individual identities.

## Officer information architecture

- **KaushalAI:** priorities and network-wide brief.
- **Centres:** structured centre records with verified counts, sanctioned equipment, camera/evidence state and chronological source history.
- **Actions:** searchable officer worklist. Filter by case stage or priority, inspect any task in a non-destructive right-hand pane, then open the centre, evidence, case audit or centre PDF with a click.
- **Insights:** analysis and one selected-centre PDF workspace, replacing multiple repeated report buttons.

## Review states and provenance

Open, under review and virtual-verification case stages are supplied by the backend, not inferred by frontend clicks. The stage selector never mutates an officer decision. The case detail remains the only write surface; CSRF, OIDC, centre RBAC, note requirements and immutable audit history are not bypassed. A read-only officer can navigate centre evidence and generate their own reports but cannot write case reviews. PDFs/JSON centre report endpoints now explicitly check that the authenticated officer can read that centre.

Server-side action queues and network report catalogues use **all authorised real centre IDs**, while preserving the original curated five-demo-centre submission fixture. An officer never receives another centre's cases, history, or download link from these collections.

## Design decisions

Poppins body and Bricolage Grotesque headings from Sprint 1. No additional top-level modules. One worklist, one contextual inspector, one centre-report picker; expandable queue breakdown and evidence detail. Narrow viewport stacks rather than introducing horizontal navigation overflow.

## Acceptance

- Fast search by centre, case ID, task and details; priority/stage filters with clear reset and no optimistic status mutation.
- Contextual centre, evidence, exact case audit and PDF links.
- Case page offers immediate centre-record and report navigation.
- Insights supports selected centre, period-preserving PDF link and read-only facts; missing observed values remain unavailable.
- Both raw report formats enforce centre grants, including viewers.
- Real centres appear in action and reporting results without reopening the old demo hard-code.
- Full CI: frontend, backend, PostgreSQL, hygiene, Playwright browser, protected session, OIDC; no unreviewed merge.

The next planned Sprint 4 is low-bandwidth/offline polish, mobile accessibility and full-site release hardening (issue #86). No claim of field-certified tamper detection is made by this CRM UX.
