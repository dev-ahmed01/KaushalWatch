#!/usr/bin/env python3
"""Post-review quality audit for local Phase 3D manual classifications.

Does not read images or re-run detectors. Classifications and reference
validity come from human inputs, not independent certification. The
clarification queue is a convenience sample, NOT a new accuracy benchmark.
No reviewer free-text notes are exported.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

SCENES = frozenset({
    "camera_displacement", "foreground_change", "lighting_ir_change",
    "visibility_degraded", "unchanged_scene", "other", "uncertain", "unreviewed",
})
STATES = frozenset({"REVIEWED", "UNREVIEWED", "NEEDS_SECOND_REVIEW"})
VERDICTS = frozenset({"yes", "no", "unknown"})
REQUIRED = frozenset({
    "review_id", "day", "category", "start_seconds", "end_seconds",
    "review_status", "scene_classification", "visual_evidence_usable",
    "reference_still_valid",
})


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_reviews(path: Path, *, per_pattern: int = 3) -> tuple[dict, list[dict]]:
    if not 1 <= per_pattern <= 20:
        raise ValueError("per_pattern must be between 1 and 20")
    if not path.is_file():
        raise ValueError("Saved manual review CSV does not exist")
    rows = []
    seen = set()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError("Review CSV is missing required columns")
        for r in reader:
            case_id = r["review_id"]
            if not case_id or case_id in seen:
                raise ValueError("Blank or repeated case ID")
            seen.add(case_id)
            if (r["day"] not in ("day3", "day4")
                    or r["review_status"] not in STATES
                    or r["scene_classification"] not in SCENES
                    or r["visual_evidence_usable"] not in VERDICTS
                    or r["reference_still_valid"] not in VERDICTS):
                raise ValueError(f"Invalid categorical review values for {case_id}")
            if r["review_status"] == "REVIEWED" and r["scene_classification"] == "unreviewed":
                raise ValueError(f"Reviewed case lacks a scene classification: {case_id}")
            try:
                start, end = float(r["start_seconds"]), float(r["end_seconds"])
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid review offsets for {case_id}") from exc
            from math import isfinite
            if not (isfinite(start) and isfinite(end) and 0 <= start <= end):
                raise ValueError(f"Invalid review offsets for {case_id}")
            rows.append(r)
    if not rows:
        raise ValueError("No saved manual review cases")

    complete = [r for r in rows if r["review_status"] == "REVIEWED"]
    patterns = {
        "stable_view_unusable_needs_reason": [
            r for r in complete
            if r["scene_classification"] == "unchanged_scene"
            and r["visual_evidence_usable"] == "no"
        ],
        "degraded_but_usable_needs_scope": [
            r for r in complete
            if r["scene_classification"] == "visibility_degraded"
            and r["visual_evidence_usable"] == "yes"
        ],
        "degraded_unusable_reference_check": [
            r for r in complete
            if r["scene_classification"] == "visibility_degraded"
            and r["visual_evidence_usable"] == "no"
        ],
    }
    selected = []
    for pattern, group in patterns.items():
        # Deterministic, balanced by day and category where available;
        # not a statistical random sample or independent reviewer.
        ordered = sorted(
            group, key=lambda r: (r["day"], r["category"], float(r["start_seconds"]))
        )
        day3 = [r for r in ordered if r["day"] == "day3"]
        day4 = [r for r in ordered if r["day"] == "day4"]
        picks = []
        for i in range(max(len(day3), len(day4))):
            if i < len(day3):
                picks.append(day3[i])
            if i < len(day4):
                picks.append(day4[i])
        for r in picks[:per_pattern]:
            selected.append({
                "review_id": r["review_id"], "day": r["day"],
                "category": r["category"],
                "start_seconds": r["start_seconds"],
                "end_seconds": r["end_seconds"],
                "original_scene": r["scene_classification"],
                "original_usable": r["visual_evidence_usable"],
                "original_reference_still_valid": r["reference_still_valid"],
                "reason_to_clarify": pattern,
                "independently_verified_reference": "",
                "observation_scope_or_degradation_cause": "",
                "confirmed_evidence_usable": "",
                "independent_review_status": "UNREVIEWED",
            })
    summary = {
        "status": "PHASE3D_REVIEW_QUALITY_AUDIT_DEVELOPMENT_ONLY",
        "production_qualified": False,
        "reviewed": len(complete),
        "cases": len(rows),
        "status_counts": dict(sorted(Counter(r["review_status"] for r in rows).items())),
        "scene_by_day": {
            day: dict(sorted(Counter(
                r["scene_classification"] for r in complete if r["day"] == day
            ).items())) for day in ("day3", "day4")
        },
        "patterns_needing_clarification": {k: len(v) for k, v in patterns.items()},
        "reference_marked_valid_yes": sum(
            r["reference_still_valid"] == "yes" for r in complete
        ),
        "reference_independently_verified": "NOT_ASSESSED",
        "selected_clarification_cases": len(selected),
        "notes_present_count": sum(bool(r.get("reviewer_notes", "").strip()) for r in rows),
        "source_decisions_sha256": _hash(path),
        "limitations": [
            "A stable camera view can still have unusable image evidence",
            "Degraded footage may still support a narrower observation task",
            "Reference marked yes is not proof of comparison to an approved healthy reference",
            "These selected intervals are enriched failure examples, not unbiased prevalence",
            "No automatic tampering determination, auto-reference reset or production integration",
            "Never infer reviewer intent or override the original saved answers",
        ],
        "privacy": "Aggregate summary contains no case IDs, free text or camera images",
    }
    return summary, selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True,
                        help="Directory for aggregate JSON and optional local clarification CSV")
    parser.add_argument("--per-pattern", type=int, default=3)
    args = parser.parse_args()
    summary, selected = inspect_reviews(
        args.reviews.resolve(), per_pattern=args.per_pattern
    )
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "review_quality_audit.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    queue_path = args.out / "optional_clarification_queue.csv"
    with queue_path.open("w", newline="", encoding="utf-8-sig") as handle:
        columns = [
            "review_id", "day", "category", "start_seconds", "end_seconds",
            "original_scene", "original_usable", "original_reference_still_valid",
            "reason_to_clarify", "independently_verified_reference",
            "observation_scope_or_degradation_cause",
            "confirmed_evidence_usable", "independent_review_status",
        ]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(selected)
    print(json.dumps(summary, indent=2))
    print(f"Optional local clarification queue: {queue_path.resolve()}")


if __name__ == "__main__":
    main()
