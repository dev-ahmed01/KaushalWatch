# Proof of Training — Phase 3A trade-specific equipment proof

Implemented as a read-only, controlled equipment matrix inside /demo/mission. It uses the existing Construction Electrician–LV (CON/Q0603) example manifest and the three existing cached detection examples. No fifth top-level module, extra backend persistence layer or fabricated media was introduced.

## Source boundaries

1. Item **types** are tied to the existing manifest's CSDCI/NSDC curriculum source notes.
2. Every **required quantity** (4 workbenches, 12 chairs, 4 training panels, 1 drill, 6 multimeters) is explicitly simulated. These are **not** government-sanctioned requirements.
3. All three **example observed counts** at 0, 10 and 20 seconds are author-created data from demo/cached_detections/construction_electrician.example.json. SHA-256 of the exact original manifest and example cache is carried in the API response, but **video_source_sha256=null** and **model_run_verified=false**. A fixture data hash is NOT a camera source or model-execution receipt.
4. The multimeter is manual/officer-verification tier: absent in the sample cache means **unknown, not zero**. Drill is partially camera-verifiable: visible presence alone says nothing about electrical/mechanical health or whether a workshop task was authorized.
5. An interactive "Illustrate camera blocked" switch withholds **all** observed sample values. There is no violation, headcount or zero-by-absence inference.
6. This phase's matrix is **not a formal compliance engine**. The canonical backend pipeline remains backend/app/services/infrastructure.py and infrastructure_pipeline.py. The UI only describes illustrative values; it does not duplicate or alter backend case rules or save a compliance event.
7. No per-class precision/recall/TP/FP/FN, ROI consistency, independent labels or real footage detections are available in this controlled fixture. The UI states this clearly. The existing evaluation/equipment_holdout.py separately checks independent source-pinned count annotations and never promotes corrected caches to detector qualification. Practical activity remains governed by external authorized schedules and worker-local visible-motion limits; no mechanical fitness claim.

## Acceptance

- Endpoint GET /api/demo/trade-proof exists only for controlled nonprotected modes; if manifest/cache missing, modified into an invalid schema, or contains unapproved classes/samples, fails closed with 503.
- Browser matrix shows the manifest's five item types, correct relative quantities, exact three time samples, safe manual-verification tier and abstention on simulated camera blockage.
- A source-verified **equipment** recording is NOT part of this phase. The existing MEVA private camera-quality research clips contain camera intervention research labels, not verified electrical lab tools. Linking equipment detections to those recordings would falsely imply training-centre source evidence.
- Phase 3B still required: authorized camera-specific equipment footage, actually frozen model weights, ROI/frame-aligned output, independent per-class boxes/count annotations, negative/occlusion held-out clips, and trustworthy real footage inference. Do not close issue #103 until those exist.

Development tests: node --experimental-strip-types --test app/lib/server/trade-proof.test.mjs from web/. Browser checks: web/e2e/trade-proof-mission.spec.ts. Full CI must pass before merge. Issue #91 stays blocked for real pilot.
