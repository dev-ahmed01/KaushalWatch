#!/usr/bin/env python3
"""Build a local manual-review queue from Phase 3D numerical diagnostics.

This does not read video, export images, change detector thresholds, or
approve a camera reference. The queue is deliberately enriched for failures,
so its reviewer decisions must not be reported as population accuracy.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

EXPECTED_STATUS = "COMPLETE_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT"
CATEGORIES = ("carried", "new_near_event", "new_far_from_event")


def _number(value, what: str) -> float:
    try:
        n = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid {what}") from exc
    if not math.isfinite(n) or n < 0:
        raise ValueError(f"Invalid {what}")
    return n


def _integer(value, what: str) -> int:
    n = _number(value, what)
    if not n.is_integer():
        raise ValueError(f"Noninteger {what}")
    return int(n)


def _boolean(value: str) -> bool:
    if value not in ("True", "False"):
        raise ValueError("Invalid saved boolean")
    return value == "True"


def _rows(path: Path, required: set[str]) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"Missing numerical report: {path}")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not required.issubset(set(reader.fieldnames or ())):
            raise ValueError(f"Invalid numerical report columns: {path.name}")
        return list(reader)


def _read_day(directory: Path, day: str, near_seconds: float) -> tuple[list[dict], dict]:
    summary_path = directory / "continuous_shadow_summary.json"
    if not summary_path.is_file():
        raise ValueError(f"Missing complete summary: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (summary.get("status") != EXPECTED_STATUS
            or summary.get("qualified") is not False
            or summary.get("production_integration") is not False):
        raise ValueError(f"{day}: only complete, nonqualified reports are allowed")
    fps = _number(summary.get("fps"), "source FPS")
    cadence = _number(summary.get("effective_sample_seconds"), "sample cadence")
    if not fps or not cadence:
        raise ValueError("FPS and sample cadence must be positive")
    normal_expected = _integer(
        summary["methods"]["fusion"]["normal_review_samples"],
        "total normal review samples"
    )
    hourly = summary.get("normal_review_hours")
    if not isinstance(hourly, list) or not hourly:
        raise ValueError("Use extended evaluator with per-hour normal review counts")
    events = []
    for row in _rows(
        directory / "continuous_shadow_events.csv",
        {"class", "start_frame", "end_frame", "method"},
    ):
        if row["method"] != "fusion":
            continue
        if row["class"] not in ("covered", "defocused", "moved"):
            raise ValueError("Invalid event class")
        start = _integer(row["start_frame"], "event start")
        end = _integer(row["end_frame"], "event end")
        if start < 1 or end < start:
            raise ValueError("Invalid event interval")
        events.append((start, end, row["class"]))
    events.sort()
    if any(x[1] >= y[0] for x, y in zip(events, events[1:])):
        raise ValueError("Overlapping labeled events")

    normal = []
    for row in _rows(
        directory / "continuous_shadow_normal_review_episodes.csv",
        {
            "start_frame", "end_frame", "samples", "spatial_cue_samples",
            "global_fallback_samples", "already_alerted_before_normal_span",
        },
    ):
        start = _integer(row["start_frame"], "normal span start")
        end = _integer(row["end_frame"], "normal span end")
        count = _integer(row["samples"], "flagged samples")
        spatial = _integer(row["spatial_cue_samples"], "spatial samples")
        fallback = _integer(row["global_fallback_samples"], "fallback samples")
        carried = _boolean(row["already_alerted_before_normal_span"])
        if start < 1 or end < start or count < 1 or spatial + fallback != count:
            raise ValueError("Invalid normal review span")
        previous_event = next(
            ((a, b, label) for a, b, label in reversed(events) if b < start),
            None,
        )
        gap = (start - previous_event[1]) / fps if previous_event else None
        category = (
            "carried" if carried
            else "new_near_event" if gap is not None and gap <= near_seconds
            else "new_far_from_event"
        )
        normal.append({
            "day": day,
            "category": category,
            "start_frame": start,
            "end_frame": end,
            "start_seconds": round((start - 1) / fps, 3),
            "end_seconds": round((end - 1) / fps, 3),
            "sampled_review_seconds": round(count * cadence, 3),
            "flagged_samples": count,
            "spatial_samples": spatial,
            "global_fallback_samples": fallback,
            "carried": carried,
            "previous_incident": previous_event[2] if previous_event else "none",
            "seconds_since_prior_incident_end": (
                round(gap, 3) if gap is not None else ""
            ),
            "start_hour": int(((start - 1) / fps) // 3600),
        })
    normal.sort(key=lambda item: item["start_frame"])
    if any(a["end_frame"] >= b["start_frame"] for a, b in zip(normal, normal[1:])):
        raise ValueError("Overlapping normal review spans")
    if sum(item["flagged_samples"] for item in normal) != normal_expected:
        raise ValueError("Normal review spans do not reconcile with summary")
    expected_hours = {
        _integer(h["hour_from_recording_start"], "hour"):
            _integer(h["fusion_review_samples"], "hour review samples")
        for h in hourly
    }
    if sum(expected_hours.values()) != normal_expected:
        raise ValueError("Hourly normal review totals do not reconcile")
    churn_hours = sorted(
        (
            (
                _integer(h["new_fusion_review_episodes"], "hour new episodes"),
                _integer(h["hour_from_recording_start"], "hour"),
            )
            for h in hourly
        ),
        key=lambda pair: (-pair[0], pair[1]),
    )
    return normal, {
        "day": day,
        "total_normal_review_samples": normal_expected,
        "normal_review_spans": len(normal),
        "review_categories": dict(Counter(i["category"] for i in normal)),
        "sample_counts_by_category": dict(
            (c, sum(i["flagged_samples"] for i in normal if i["category"] == c))
            for c in CATEGORIES
        ),
        "top_churn_hours": [
            {"hour_from_start": h, "new_review_episodes": n}
            for n, h in churn_hours[:5]
        ],
    }


def choose(normal: list[dict], hourly: list[dict], *,
           per_category: int, churn_hours: int) -> list[dict]:
    """Take longest examples per cause class and additional high-churn hours."""
    chosen: dict[tuple[str, int], dict] = {}
    for category in CATEGORIES:
        group = sorted(
            (r for r in normal if r["category"] == category),
            key=lambda r: (-r["flagged_samples"], r["start_frame"]),
        )
        for row in group[:per_category]:
            chosen[(row["day"], row["start_frame"])] = dict(row, selection="longest_" + category)
    for item in hourly[:churn_hours]:
        hour = item["hour_from_start"]
        new_review_candidates = [
            r for r in normal
            if r["start_hour"] == hour
            and (r["day"], r["start_frame"]) not in chosen
            and not r["carried"]
        ]
        if new_review_candidates:
            row = sorted(
                new_review_candidates,
                key=lambda x: (-x["flagged_samples"], x["start_frame"]),
            )[0]
            chosen[(row["day"], row["start_frame"])] = dict(
                row, selection="high_churn_hour"
            )
    return sorted(chosen.values(), key=lambda r: (r["day"], r["start_frame"]))


def create_queue(day3: Path, day4: Path, *,
                 near_seconds: float = 60.0, per_category: int = 3,
                 churn_hours: int = 2, context_seconds: float = 10.0) -> tuple[list[dict], dict]:
    if any(not math.isfinite(v) or v < 0 for v in (near_seconds, context_seconds)):
        raise ValueError("Time parameters must be finite and nonnegative")
    if not 1 <= per_category <= 20 or not 0 <= churn_hours <= 10:
        raise ValueError("Selection counts outside allowed range")
    all_selected = []
    summaries = {}
    for day, path in (("day3", day3), ("day4", day4)):
        normal, overview = _read_day(path, day, near_seconds)
        summaries[day] = overview
        selected = choose(
            normal, overview["top_churn_hours"], per_category=per_category,
            churn_hours=churn_hours,
        )
        for row in selected:
            row["review_id"] = f"{day}-normal-{row['start_frame']}"
            row["review_start_seconds"] = round(
                max(0.0, row["start_seconds"] - context_seconds), 3
            )
            row["review_end_seconds"] = round(
                row["end_seconds"] + context_seconds, 3
            )
            row["review_status"] = "UNREVIEWED"
            row["scene_classification"] = ""
            row["visual_evidence_usable"] = ""
            row["reference_still_valid"] = ""
            row["reviewer_notes"] = ""
        all_selected += selected
    return all_selected, {
        "status": "PHASE3D_TARGETED_MANUAL_REVIEW_NOT_HELD_OUT",
        "qualified": False,
        "production_integration": False,
        "selected_cases": len(all_selected),
        "day_summaries": summaries,
        "nearby_seconds": near_seconds,
        "context_seconds": context_seconds,
        "selection_bias": (
            "Enriched for long-duration and high-churn failures. "
            "Do not interpret reviewed sample rates as detector accuracy."
        ),
        "review_guidance": (
            "Review original licensed footage locally at offsets from video start. "
            "Classify camera position, lighting/IR transition, foreground change, "
            "actual visibility problems, uncertain or other; do not invent a cause. "
            "Do not upload identifiable CCTV, auto-enroll camera references, "
            "or turn this into an automated tampering verdict."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day3", required=True, type=Path)
    parser.add_argument("--day4", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--nearby-seconds", type=float, default=60.0)
    parser.add_argument("--per-category", type=int, default=3)
    parser.add_argument("--churn-hours", type=int, default=2)
    parser.add_argument("--context-seconds", type=float, default=10.0)
    args = parser.parse_args()
    queue, metadata = create_queue(
        args.day3, args.day4, nearby_seconds=args.nearby_seconds,
        per_category=args.per_category, churn_hours=args.churn_hours,
        context_seconds=args.context_seconds,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    csv_path = args.out / "targeted_camera_review_queue.csv"
    keys = [
        "review_id", "day", "category", "selection",
        "start_frame", "end_frame", "start_seconds", "end_seconds",
        "review_start_seconds", "review_end_seconds",
        "sampled_review_seconds", "flagged_samples", "spatial_samples",
        "global_fallback_samples", "carried", "previous_incident",
        "seconds_since_prior_incident_end", "start_hour",
        "review_status", "scene_classification", "visual_evidence_usable",
        "reference_still_valid", "reviewer_notes",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=keys)
        writer.writeheader()
        writer.writerows({k: row.get(k, "") for k in keys} for row in queue)
    meta_path = args.out / "targeted_camera_review_summary.json"
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": metadata["status"], "qualified": False,
        "selected_cases": len(queue),
        "selected_by_day": dict(Counter(row["day"] for row in queue)),
        "selected_by_category": dict(Counter(row["category"] for row in queue)),
        "queue_csv": str(csv_path.resolve()),
        "summary_json": str(meta_path.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
