# 60-second KaushalWatch demo click path

## Before the screen recording

From the repository root, reset mutable runtime state and load the deterministic **simulated** judge seed:

```bash
python scripts/prepare_demo_state.py --yes
```

This preserves `data/raw/`, reviewed detector assets and manifests. It seeds exactly:
- 2 verified centres,
- 2 centres needing review,
- 1 uncertain centre because camera trust failed,
- 1 centre with analysis unavailable.

The seed also creates one clearly watermarked synthetic evidence frame, SHA-256 integrity metadata and a resolved duplicate-evidence test record. These are prototype records and remain visibly tagged **Simulated**.

If you will also demonstrate live/manual analysis on the final reviewed clip, run the strict readiness gate separately before the presentation:

```bash
python scripts/check_demo_readiness.py --video data/raw/final-demo.avi --final
```

Do not use an arbitrary video for the infrastructure step. The reviewed infrastructure cache is source-bound; a non-matching clip should become unavailable rather than produce a clean result.

## The 60-second path

**0–8s — Network.** Start on Network. Point to the Karnataka map and the three-row Needs attention list. Say: “KaushalWatch is exception-first. Officers do not watch feeds.” The quiet line should read **2 verified · 2 need review · 1 uncertain · 1 unavailable**. Open Bengaluru TC-04.

**8–18s — Centre Cockpit.** Point to the five pillars. Say: “Reported, required and observed realities are reconciled here. Camera trust gates the conclusion.” Point to Temporal Proof: “One frame is never a case.” The seeded Bengaluru case is visibly tagged **Simulated**.

**18–30s — Evidence.** The retained frame is synthetic and visibly watermarked. Open Technical details briefly to show SHA-256. Open the Evidence tab and point to **1 possible duplicate**. Say: “Integrity is checked independently from the compliance conclusion.”

**30–43s — Human review.** Return to Cockpit and choose **Review evidence**. Say: “AI surfaces evidence; an authorized officer decides.” Enter a short review note, choose **Confirm**, and expand Audit trail to show **Open → Under Review → Confirmed**. This simulated action is intentionally local to the rehearsal; reloading restores the prepared open case.

**43–52s — Reports.** Open Reports. Show the **Simulated** tag, date-range chips and Centre Verification Report preview. Point to **Download PDF**. The PDF is a real generated file and carries the same simulated-data label.

**52–60s — Analysis + Assistant.** Return to the centre and open **Run analysis now**. Point to Manifest reading, Visual evidence, Temporal Proof and Case evidence. Do not start a new run unless the reviewed source clip is ready. Close it and open **Ask assistant**. End with: “Position is tracked, not identity. Missing or untrusted evidence never becomes a verified conclusion.”

## Recovery if the demo state changes

Run:

```bash
python scripts/prepare_demo_state.py --yes
```

Then refresh the browser. Do not manually delete `data/raw/` or reviewed detector files.
