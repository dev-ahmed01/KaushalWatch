# Phase 14 — Compact CRM navigation and responsive accessibility

This release is a focused visual/interaction-quality pass, NOT a fifth module or a redesign of the established light four-module KaushalWatch OS. The two fonts, four primary navigation destinations, centre sections, officer audit, saved evidence and controlled judge route are preserved.

## Interaction corrections

- The shared application title labels the controlled /demo/mission page as **Proof of Training** while the active top-level product remains **KaushalAI**. A judge is no longer shown a misleading module header during the special guided route.
- Reporting-period controls remain on data summaries (KaushalAI, Centres, Insights, Actions) but are omitted on the scenario narrative and individual saved case screens. Case evidence is a saved record, not a period-selectable dashboard.
- The narrow mobile header uses a shrink-safe page label and flexible height, avoiding title collisions while preserving the four-item bottom navigation and a readable date selector on summary screens.
- The existing six centre tabs remain direct URLs and keyboard-focusable links. Opening a nested section such as Camera Trust at 320px brings the active tab into its local horizontal scroll viewport **without scrolling the document or changing the selected centre**. The nav includes screen-reader guidance that additional sections can be reached horizontally.
- Actions no longer renders a second separate **Ask KaushalAI** button. The single existing shell assistant trigger is already permission-aware. Removing the redundant button also prevents the Actions page from advertising an assistant trigger that cannot work in protected read-only sessions.
- No video, AI thresholds, camera provenance, evidence links, PDF endpoints, saved officer permissions, or government approval claims have been changed.

## Acceptance verification

A new Playwright matrix checks all four module labels/active links and exactly one visible assistant trigger, the judge and case context title and date-control semantics, centre deep-link active-tab visibility and keyboard focus at 320px, and narrow-screen document overflow for all four modules plus mission and case views. Existing 390px, protected-browser, OIDC, reports, camera replay, evidence/audit and full Playwright tests remain mandatory.

Only a passing 7-job app CI and protected release-container build should qualify a merge. After merging, the same checks must pass again on the exact new main SHA. Real workstation and real-site accuracy validation remain external, and pilot acceptance issue #91 stays open.
