# UI Design Reference

Research snapshot: 2026-10-03

KaushalWatch's command-centre UI is an original implementation informed by established physical-security and connected-operations interface patterns. It does not copy another product's branding, assets, wording, or proprietary component code.

## Primary reference: Verkada Command

Verkada Command is a close adjacent product because it combines camera monitoring, device health, events, investigation and security operations in a single web interface.

Public references reviewed:

- Verkada Command product overview: https://www.verkada.com/command/
- Verkada product-navigation redesign: https://www.verkada.com/blog/introducing-a-intuitive-new-navigation-experience-in-command/
- Verkada camera-page usability redesign: https://www.verkada.com/blog/command-ui-enhancements-public-grids/
- G2 Verkada product/review summary: https://ai.g2.com/product/verkada

At the time of the research snapshot, G2 showed Verkada at 4.7/5 and summarized reviewers as frequently mentioning ease of use and user-friendly Command software.

## Patterns adapted for KaushalWatch

The redesign deliberately adapts interaction patterns rather than visual identity:

1. **Persistent operational navigation**
   - Overview, Attendance, Infrastructure, Cases and Evidence stay discoverable from one stable left rail.
   - The current centre/workspace remains visible as context.

2. **Exception-first hierarchy**
   - Persistent compliance cases sit beside the active verification workflow instead of being buried below forms.
   - Severity, status, evidence and officer actions are visible together.

3. **Compact operational summary**
   - Centre, case, camera and edge-sync counts are summarized in a restrained metric row.
   - Counts remain clearly labelled demo/prototype data.

4. **Trust state close to decisions**
   - Camera trust, edge sync and anonymous identity handling appear as a compact system-posture panel.
   - These signals do not create new compliance claims.

5. **Consistent action placement**
   - Upload/analysis actions share one pattern.
   - Evidence and review actions remain attached to their case.

6. **High information density without visual noise**
   - White operational surfaces, restrained borders, compact typography and one dark navigation plane.
   - Status colour is used sparingly and never as the only source of meaning.

## KaushalWatch-specific boundaries retained

- **PROTOTYPE — SIMULATED OPERATIONAL DATA** remains explicit.
- AI surfaces evidence-backed cases for human review; it does not issue penalties.
- Attendance uses anonymous positional tracking rather than individual identification.
- Apparent operability remains a visual activity proxy and not a mechanical/electrical-health claim.
- Officer-verification-required manifest items are not presented as camera-verified.
- Evidence policy keeps ordinary raw video at the edge by design.
