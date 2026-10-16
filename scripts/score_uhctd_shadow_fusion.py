#!/usr/bin/env python3
"""Rescore existing UHCTD spatial-shadow CSVs. DEVELOPMENT ONLY; no video read.

Outputs a numerical summary with exact source hashes. This reproduces the
exploratory fusion rule and baseline comparisons but cannot qualify production
accuracy: interval selection, approved baseline, and independent footage are
not established by these reports.

Example (Windows PowerShell):
  python scripts/score_uhctd_shadow_fusion.py ^
    --day3 artifacts/phase3d/spatial/day3/spatial_shadow_samples.csv ^
    --day4 artifacts/phase3d/spatial/day4/spatial_shadow_samples.csv ^
    --out artifacts/phase3d/spatial/fusion_comparison.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.camera_shadow_fusion import combine_shadow_evidence  # noqa: E402

REQUIRED = frozenset((
    "span", "kind", "frame", "post_onset", "evidence_status",
    "review_55", "global_review", "global_quality_limited",
))


def parse_bool(value: str) -> bool:
    norm = str(value).strip().lower()
    if norm not in ("true", "false"):
        raise ValueError(f"Invalid recorded boolean {value!r}")
    return norm == "true"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fresh_event(rows: list[dict], method: str) -> tuple[bool, bool]:
    onset = next((i for i, row in enumerate(rows) if row["post_onset"]), None)
    if onset is None or onset == 0:
        raise ValueError("Movement events require pre-onset context and positive frames")
    preexisting = rows[onset - 1][method]
    fresh = any(
        rows[i][method] and not rows[i - 1][method]
        for i in range(onset, len(rows))
    )
    return bool(fresh and not preexisting), bool(preexisting)


def score_csv(path: Path) -> dict:
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"Missing sampled CSV: {path}")
    groups: dict[str, list[dict]] = {}
    last_span = None
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not REQUIRED.issubset(set(reader.fieldnames or [])):
            raise ValueError("Missing required original spatial-shadow columns")
        for row in reader:
            name = row["span"]
            if not name or not (
                name.startswith("moved_") or name.startswith("normal_control_")
            ):
                raise ValueError("Unexpected interval type in shadow CSV")
            if name != last_span and name in groups:
                raise ValueError("Discontiguous or repeated interval in shadow CSV")
            if name not in groups:
                groups[name] = []
            last_span = name
            kind = int(row["kind"])
            if kind not in (0, 3) or (kind == 0) != name.startswith("normal_control_"):
                raise ValueError("Interval kind/name mismatch")
            frame = int(row["frame"])
            previous = groups[name]
            if previous and frame <= previous[-1]["frame"]:
                raise ValueError("Non-increasing sampled frame index")
            post = parse_bool(row["post_onset"])
            if kind == 0 and post:
                raise ValueError("Normal control cannot have a movement onset")
            spatial = parse_bool(row["review_55"])
            global_alert = parse_bool(row["global_review"])
            global_quality_limited = parse_bool(row["global_quality_limited"])
            fused = combine_shadow_evidence(
                {"evidence_status": row["evidence_status"], "review_55": spatial},
                {
                    "persistent_review": global_alert,
                    "quality_limited": global_quality_limited,
                },
            )
            previous.append({
                "frame": frame,
                "post_onset": post,
                "spatial": spatial,
                "global": global_alert,
                "fusion": fused["review_cue"],
                "evidence_status": fused["evidence_status"],
            })

    if not groups or not any(k.startswith("moved_") for k in groups):
        raise ValueError("No movement events in sampled CSV")
    moved = {k: v for k, v in groups.items() if k.startswith("moved_")}
    normal = {k: v for k, v in groups.items() if k.startswith("normal_control_")}
    if not normal:
        raise ValueError("No normal controls in sampled CSV")

    comparisons = {}
    for method in ("spatial", "global", "fusion"):
        outcomes = [fresh_event(rows, method) for rows in moved.values()]
        comparisons[method] = {
            "fresh_moved_review_events": sum(ok for ok, _ in outcomes),
            "moved_events_total": len(moved),
            "preexisting_at_onset": sum(prior for _, prior in outcomes),
            "normal_controls_with_review": sum(
                any(r[method] for r in rows) for rows in normal.values()
            ),
            "normal_controls_total": len(normal),
            "normal_samples_with_review": sum(
                r[method] for rows in normal.values() for r in rows
            ),
        }
    return {
        "development_only": True,
        "qualification": "NOT_HELD_OUT_NOT_PRODUCTION_APPROVED",
        "source_csv": str(path),
        "source_csv_sha256": sha256(path),
        "comparisons": comparisons,
        "unknown_low_texture_samples": sum(
            row["evidence_status"] == "UNKNOWN_LOW_TEXTURE"
            for rows in groups.values() for row in rows
        ),
        "events": {
            name: {
                "fusion_fresh": fresh_event(rows, "fusion")[0],
                "fusion_preexisting": fresh_event(rows, "fusion")[1],
            }
            for name, rows in moved.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day3", type=Path, required=True)
    parser.add_argument("--day4", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.resolve() in {args.day3.resolve(), args.day4.resolve()}:
        parser.error("Output must not overwrite source CSVs")
    result = {
        "status": "PHASE3D_SHADOW_FUSION_DEVELOPMENT_REPLAY_ONLY",
        "production_integration": False,
        "rule": (
            "spatial 55% if sufficient tiles; global fallback on low spatial "
            "texture ONLY when global structural texture is sufficient"
        ),
        "limitations": [
            "Selected Day 3/Day 4 windows already used during development",
            "Reported normal windows are not a full-day false-alert-rate estimate",
            "Pre-event references were derived from annotation-confirmed healthy frames",
            "No proof of camera tampering, intentional interference, or real-time integrity",
            "No released Camera Trust or attendance/practical pipeline integration",
        ],
        "day3": score_csv(args.day3),
        "day4": score_csv(args.day4),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "day3": result["day3"]["comparisons"],
        "day4": result["day4"]["comparisons"],
        "report_path": str(args.out.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
