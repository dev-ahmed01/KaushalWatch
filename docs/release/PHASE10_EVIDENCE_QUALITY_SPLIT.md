# Phase 10 — Separate visual evidence from suspected interference

A visually unusable video is not proof of camera tampering. Phase 9 exposed the baseline's limitations on previously inspected Day 3 footage: 60/144 annotated-event frames and 35/120 normal/pre-event frames marked untrusted; this is NOT real-site accuracy.

Phase 10 adds a conservative, review-only decision to the EXISTING numeric Camera Trust worker. It does not tune thresholds on inspected media or change operational attendance threshold settings. The four primary product modules remain.

## New backend contract

The existing backend/app/services/camera_quality.py sample function returns its unchanged illumination, focus, geometric scene change, local coverage and frozen-frame proxies, PLUS an evidence_triage object with schema KW_CAMERA_EVIDENCE_TRIAGE_V1.

| Usability | What is observed | What follows |
| --- | --- | --- |
| NOT_USABLE_FOR_VISUAL_VERIFICATION | Extreme illumination, strong defocus or possible partial coverage | Hold evidence-dependent claims for review |
| REVIEW_REQUIRED_SCENE_ALIGNMENT | Registered scene displacement versus supplied reference | Request independent scene alignment review |
| UNKNOWN_NO_REFERENCE / UNKNOWN_SCENE_REGISTRATION | Missing reference or unreliable visual correspondence | Abstain |
| PROVISIONALLY_OBSERVABLE | No severe loss observed in this sampled frame | Not equivalent to certified camera health |

Interference review is independent: POSSIBLE_SCENE_INTERFERENCE_REVIEW, NOT_ESTABLISHED or UNKNOWN_NO_REFERENCE. Only a structural change or registered displacement with a supplied reference produces the POSSIBLE category. Defocus, darkness, or identical sparse samples alone cannot attribute intentional tampering.

Every row remains physical_camera_health UNKNOWN, malicious_tampering_proven false, enforcement_authorized false, institutional_accuracy_qualified false. Supplied reference pixels do NOT authenticate the provenance of a custodial reference.

The existing standalone worker adds evidence_triage_schema, evidence_unusable_samples, evidence_unknown_or_alignment_review_samples, possible_interference_samples and permanently non-authorizing flags to its sparse shadow observation JSON payload; PostgreSQL migration is unnecessary. Historical observation payloads without triage remain unknown rather than being assigned retrospective certainty.

## Officer and controlled-demo UI

The protected Centre → Camera Trust observations now show separate counts for evidence not usable and possible scene interference plus alignment/reference uncertainty. Numeric examples identify both decisions.

The existing controlled Camera Trust sample player also shows two synchronized AUTHORED cue tracks, rather than faking model detections. The unsupported demo-only Scene people counter has been removed. Exports explicitly identify authored footage and never authorize enforcement.

Private MEVA/UHCTD footage stays outside the repository and public web asset paths. It is research-only and previously inspected; no claim of independent held-out field performance follows from this release.

## Validation

Synthetic test coverage includes focus loss, darkness, scene displacement, local coverage, low-confidence geometry, identical sparse samples, missing reference and generated OpenCV defocus. Worker tests require the new split to be present without asserting camera health. Browser E2E verifies the two decision channels and absence of unsupported people counts.

Next research step: independently authorized, genuinely untouched camera footage, blinded observation labels, measured continuous-stream false alarm burden and event-local latency. Institutional pilot Issue #91 stays open. Do not promote model settings or sanctions from these quality indicators.
