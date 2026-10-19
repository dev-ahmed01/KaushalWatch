# Phase 5 — one officer evidence path plus honest qualification scorecard

**State:** The established protected officer workflow is reused, not rebuilt. Real electrician-centre detector accuracy, original authorized footage, independent labels and institution acceptance remain NOT QUALIFIED. Issues #91, #102 and #103 remain open.

## Judge workflow, inside four modules

1. Open KaushalAI → Guided mission and choose an attendance gap, obstructed camera, item-specific equipment or normal control. The Reported → Required → Observed → Decision illustrative counts stay labelled controlled examples.
2. The SHA-pinned procedural video intentionally remains separate from the authored case/attendance counts. If an exact real matching source is missing, no video-to-case connection is claimed.
3. The new **Officer evidence chain** fetches the actual saved case evidence-pack for that centre, displays source-link status, retained frame count and SHA/duplicate state, officer review status, actual audit-event count, and links to the saved case and centre PDF. A missing or mismatched case fails closed. The normal control never invents an incident.
4. The existing case page has privacy-reduced images, persistence timeline, officer role-controlled atomic review and audit history. The report route generates a real PDF from stored records, not government approval. The same source status is preserved. The new change enforces centre access on individual evidence-pack reads just as centre PDF already did.

Existing backend release officer journey tests already exercise generated video upload → camera-trust abstention → retained blurred evidence + SHA → persistence → protected review → audit/report. These are synthetic functionality tests, not institution accuracy.

## Six-pillar measured quality/uncertainty scorecard

In Insights, a small six-pillar section now surfaces attendance MAE/false alerts, camera trust/abstention, equipment counts, per-class IoU box localization, apparent practical work, and offline transport. Missing independent data is NOT QUALIFIED / null, never zero-error.

The new Python assembler evaluation/proof_of_training_scorecard.py reads SHA-pinned existing receipts and NEVER executes or replaces existing detector/evaluator. A frozen localization candidate can report genuine offline model per-class TP/FP/FN only when source, label, protocol and model proposal properties agree; it remains *pending external audit*. CI/synthetic metrics are withheld. A Phase 4 local measured HTTP transport body may show delivered counts and actual serialized bytes but is explicitly a loopback fixture measurement, not WAN/TLS volume.

The private report ALWAYS states qualified=false, even if an input independently claims true. It cannot silently promote scorecard CSV fixtures, unsigned receipts, source hashes or manually entered percentages into real accuracy.

### Optional local operator setup

Prepare a private folder outside the repository with genuinely available measured receipts. Create a frozen scorecard-inputs.json:

~~~json
{
  "schema": "KW_SCORECARD_INPUTS_V1",
  "status": "frozen",
  "receipts": {
    "offline_transport": {"path": "phase4-offline-transport.json", "sha256": "<actual file SHA-256>"},
    "equipment_localization": {"path": "equipment-localization.local.json", "sha256": "<actual file SHA-256>"}
  }
}
~~~

Use actual file hashes, not the example strings above. In PowerShell:

~~~powershell
python evaluation/proof_of_training_scorecard.py --manifest "C:\Private\KW\scorecard-inputs.json" --out "C:\Private\KW\proof-scorecard.local.json"
$env:KAUSHALWATCH_ENV = "development"
$env:KAUSHALWATCH_LOCAL_SCORECARD = "true"
$env:KAUSHALWATCH_SCORECARD_PATH = "C:\Private\KW\proof-scorecard.local.json"
~~~

Or invoke without --manifest: all six metrics are NOT QUALIFIED with no fabricated score. The output file is private, non-overwriting. Missing/mismatched sources exit 2 and block all measurements.

Next.js offers this private output only for explicitly enabled localhost development, denying external hosts/forwarding/cross-origin/protected/pilot/staging/production, symlinks, oversized files and unsupported model metrics. No fifth navigation module or raw footage.

## Test gates and independent acceptance

Backend: secure centre-scoped case evidence-pack, viewer cannot write, SHA-pinned report input, wrong/hallucinated localization scores denied, synthetic output hidden. Frontend: local source admission, refusal to display fabricated qualified metrics. Browser: stored record, actual report PDF header, missing source, normal negative control, 375px and keyboard.

Independent permission, camera video, multi-site held-out labels, official attendance records, real model execution and authorized practical-work schedule remain separate blocked institutional milestones. The Phases 3–5 CI gates prove the software flows, not external certification.
