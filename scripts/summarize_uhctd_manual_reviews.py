#!/usr/bin/env python3
"""Aggregate completed targeted Camera Trust reviews without exposing notes.

Data is selection-biased (22 deliberately sampled failure windows), not a
reliable population estimate or independent validation. The tool reads only
the saved local review CSV and original numerical queue. It never opens
videos, copies reviewer notes, resets any baseline or changes camera trust.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from review_uhctd_queue_local import load_decisions, read_queue

SCENE_TYPES = (
    "camera_displacement", "foreground_change", "lighting_ir_change",
    "visibility_degraded", "unchanged_scene", "other", "uncertain", "unreviewed",
)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def counts_by(items: list[dict], field: str) -> dict[str, int]:
    return dict(sorted(Counter(item[field] for item in items).items()))


def aggregate(queue_file: Path, review_file: Path, *,
              require_complete: bool = False) -> dict:
    if not review_file.is_file():
        raise ValueError("Saved review decisions CSV is missing; finish and save reviews first")
    queue = read_queue(queue_file)
    seen = set()
    with review_file.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or "review_id" not in reader.fieldnames:
            raise ValueError("Saved review CSV is missing review_id header")
        for row in reader:
            key = row.get("review_id")
            if not key or key in seen:
                raise ValueError("Invalid or duplicate review ID in decisions CSV")
            seen.add(key)
    if seen != {q["review_id"] for q in queue}:
        raise ValueError("Review CSV case IDs do not exactly match review queue")

    decisions = load_decisions(review_file, queue)
    records = [
        {
            "day": item["day"],
            "category": item["category"],
            "status": decisions[item["review_id"]]["review_status"],
            "scene": decisions[item["review_id"]]["scene_classification"],
            "usable": decisions[item["review_id"]]["visual_evidence_usable"],
            "reference": decisions[item["review_id"]]["reference_still_valid"],
        }
        for item in queue
    ]
    done = [r for r in records if r["status"] == "REVIEWED"]
    pending = [r for r in records if r["status"] == "UNREVIEWED"]
    second = [r for r in records if r["status"] == "NEEDS_SECOND_REVIEW"]
    if require_complete and (pending or second):
        raise ValueError(
            f"Not all cases are marked REVIEWED: {len(pending)} unreviewed, "
            f"{len(second)} needing second review"
        )
    statuses = counts_by(records, "status")
    # These combinations are review hypotheses, never automated verdicts.
    candidates = {
        "camera_displacement_with_reference_invalid": sum(
            r["scene"] == "camera_displacement" and r["reference"] == "no"
            for r in done
        ),
        "normal_looking_usable_with_reference_valid": sum(
            r["scene"] == "unchanged_scene"
            and r["usable"] == "yes" and r["reference"] == "yes"
            for r in done
        ),
        "foreground_change_but_usable_reference_valid": sum(
            r["scene"] == "foreground_change"
            and r["usable"] == "yes" and r["reference"] == "yes"
            for r in done
        ),
        "lighting_ir_change_but_usable_reference_valid": sum(
            r["scene"] == "lighting_ir_change"
            and r["usable"] == "yes" and r["reference"] == "yes"
            for r in done
        ),
        "visible_degradation_and_evidence_unusable": sum(
            r["scene"] == "visibility_degraded" and r["usable"] == "no"
            for r in done
        ),
        "visibility_degraded_but_evidence_usable_check": sum(
            r["scene"] == "visibility_degraded" and r["usable"] == "yes"
            for r in done
        ),
        "uncertain_scene_or_reference": sum(
            r["scene"] in ("uncertain", "other")
            or r["reference"] == "unknown"
            for r in done
        ),
    }
    day_summaries = {}
    for day in ("day3", "day4"):
        group = [r for r in done if r["day"] == day]
        day_summaries[day] = {
            "reviewed": len(group),
            "scene": counts_by(group, "scene"),
            "evidence_usable": counts_by(group, "usable"),
            "reference_still_valid": counts_by(group, "reference"),
            "by_review_origin": {
                category: {
                    "reviewed": len(part := [r for r in group if r["category"] == category]),
                    "scene": counts_by(part, "scene"),
                    "evidence_usable": counts_by(part, "usable"),
                    "reference_still_valid": counts_by(part, "reference"),
                }
                for category in ("carried", "new_near_event", "new_far_from_event")
            },
        }

    report = {
        "status": "PHASE3D_MANUAL_REVIEW_AGGREGATE_NOT_HELD_OUT",
        "production_qualified": False,
        "all_cases_marked_reviewed": not pending and not second,
        "cases_in_queue": len(queue),
        "review_status": statuses,
        "reviewed": len(done),
        "needs_second_review": len(second),
        "unreviewed": len(pending),
        "scene": counts_by(done, "scene"),
        "evidence_usable": counts_by(done, "usable"),
        "reference_still_valid": counts_by(done, "reference"),
        "by_day": day_summaries,
        "review_hypotheses_only": candidates,
        "queue_sha256": digest(queue_file),
        "decisions_sha256": digest(review_file),
        "privacy": "Aggregate counts only. No case IDs, reviewer notes, frames or images output.",
        "limitations": [
            "Failure-enriched cases were deliberately selected from previously inspected development footage",
            "Counts are not precision, recall or false-alarm-rate estimates",
            "Reviewer choices are observations, not independently confirmed cause or calibration",
            "Any unknown or second-review case remains unresolved",
            "Reference validity and evidence usability require additional approved procedures",
            "No decision here authorizes camera-tamper sanctions, baseline reset or production integration",
        ],
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true",
                        help="Fail unless all cases marked REVIEWED")
    args = parser.parse_args()
    source_queue = args.queue.resolve()
    source_reviews = args.reviews.resolve()
    output = args.out.resolve()
    if output in (source_queue, source_reviews):
        parser.error("Output must not overwrite input CSV files")
    result = aggregate(source_queue, source_reviews,
                       require_complete=args.require_complete)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
