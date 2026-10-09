#!/usr/bin/env python3
"""Development-only, frame-aligned UHCTD event survey (not full-day validation).

Select representative obstruction, defocus and camera-movement events and
untampered controls, seeking directly to their video spans. Reports suspected
tampering and visual unusability SEPARATELY. Every span resets temporal state,
which does NOT simulate a continuous 24-hour stream.

Example:
    python scripts/survey_uhctd_events.py \
      --video "C:/Users/Admin/Desktop/MEVA/video.avi" \
      --annotations "C:/Users/Admin/Desktop/MEVA/annotations-1.csv" \
      --out "C:/Users/Admin/Desktop/MEVA/phase7_survey"
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.camera_trust import CameraTrustState, assess_camera  # noqa: E402

LABELS = {0: "normal", 1: "covered", 2: "defocused", 3: "moved"}


def annotation_intervals(path: Path):
    """Parse complete one-based annotations. Do not infer a video's FPS."""
    runs = []
    previous_kind = None
    first = 1
    count = 0
    extent = None
    rate = None
    with path.open(newline="", encoding="utf-8-sig") as inp:
        for row in csv.reader(inp):
            if not row or not any(cell.strip() for cell in row):
                continue
            if len(row) < 5:
                raise ValueError(f"Annotations require five columns; row {count+1}")
            frame = int(row[0].strip())
            kind = int(row[1].strip())
            if frame != count + 1 or kind not in LABELS:
                raise ValueError(f"Unexpected frame or label at annotation row {count+1}")
            if previous_kind is not None and previous_kind != kind:
                runs.append({
                    "kind": previous_kind, "start": first, "end": count,
                    "extent": extent, "rate": rate,
                })
                first = frame
                extent = row[2].strip()
                rate = row[3].strip()
            elif previous_kind is None:
                extent, rate = row[2].strip(), row[3].strip()
            previous_kind = kind
            count += 1
    if previous_kind is None:
        raise ValueError("Empty annotation file")
    runs.append({
        "kind": previous_kind, "start": first, "end": count,
        "extent": extent, "rate": rate,
    })
    return runs, count


def select_spans(runs, fps, events_per_class, controls, event_seconds,
                 context_seconds, control_seconds):
    """Select first varied-parameter events, plus time-spread normal controls."""
    if events_per_class <= 0 or controls <= 0 or min(
        event_seconds, context_seconds, control_seconds
    ) <= 0:
        raise ValueError("All durations, event and control counts must be positive")
    total = runs[-1]["end"]
    context = math.ceil(fps * context_seconds)
    width = math.ceil(fps * control_seconds)
    eligible = [r for r in runs if r["kind"] == 0 and
                r["end"] - r["start"] + 1 >= width + 2 * context]
    if len(eligible) < controls:
        raise ValueError(f"Only {len(eligible)} usable normal runs for {controls} controls")
    spans = []
    for kind in (1, 2, 3):
        candidates = [r for i, r in enumerate(runs) if r["kind"] == kind
                      and i > 0 and runs[i-1]["kind"] == 0
                      and r["start"] - runs[i-1]["start"] >= context]
        if len(candidates) < events_per_class:
            raise ValueError(f"Not enough events with normal pre-onset context for {LABELS[kind]}")
        # Prefer distinct annotation extent settings, then chronological
        # others. The extent is a dataset parameter, not a literal % of area.
        chosen = []
        seen = set()
        for r in candidates:
            if r["extent"] not in seen:
                seen.add(r["extent"])
                chosen.append(r)
            if len(chosen) == events_per_class:
                break
        for r in candidates:
            if len(chosen) >= events_per_class:
                break
            if r not in chosen:
                chosen.append(r)
        for idx, r in enumerate(chosen, start=1):
            spans.append({
                "name": f"{LABELS[kind]}_{idx}_at_{r['start']}",
                "kind": kind, "onset": r["start"],
                "start": r["start"] - context,
                "end": min(r["end"], r["start"] + round(event_seconds*fps) - 1),
                "extent": r["extent"], "rate": r["rate"],
            })
    available = eligible.copy()
    for i in range(controls):
        target = (i + .5) * total / controls
        r = min(available, key=lambda x: abs((x["start"] + x["end"]) / 2-target))
        available.remove(r)
        low = r["start"] + context
        high = r["end"] - context - width + 1
        start = int(max(low, min(high, round(target - width/2))))
        spans.append({
            "name": f"normal_control_{i+1}", "kind": 0, "onset": None,
            "start": start, "end": start + width - 1,
            "extent": "", "rate": "",
        })
    return sorted(spans, key=lambda r: r["start"])


def _safe_ratio(a, b):
    return round(a/b, 6) if b else None


def _evaluate_span(cap, original_reference, span, fps, step):
    cap.set(cv2.CAP_PROP_POS_FRAMES, span["start"]-1)
    observed = float(cap.get(cv2.CAP_PROP_POS_FRAMES))
    if abs(observed-(span["start"]-1)) > 1.0:
        raise ValueError(f"Inexact decoder seek at frame {span['start']}: {observed}")
    state = CameraTrustState(reference_frame=original_reference.copy())
    rows = []
    last_tamper = False
    for frame1 in range(span["start"], span["end"]+1):
        if (frame1-span["start"]) % step:
            if not cap.grab():
                raise ValueError(f"Video ended at frame {frame1}")
            continue
        success, frame = cap.read()
        if not success:
            raise ValueError(f"Cannot decode frame {frame1}")
        trust = assess_camera(frame, state=state, sample_seconds=step/fps)
        tamper = bool(trust.tamper_suspected)
        expected_tamper = span["kind"] != 0 and frame1 >= span["onset"]
        rows.append({
            "frame": frame1, "relative_sec": (frame1-span["start"])/fps,
            "after_onset": bool(expected_tamper), "tamper": tamper,
            "unusable": not trust.trusted, "status": trust.camera_status,
            "rising": bool(tamper and not last_tamper),
            "reasons": "; ".join(trust.reasons),
        })
        last_tamper = tamper
    if not rows:
        raise ValueError("Empty sampled span")
    context = [r for r in rows if not r["after_onset"]]
    positive = [r for r in rows if r["after_onset"]]
    fresh = next((r for r in positive if r["rising"]), None)
    first_any = next((r for r in positive if r["tamper"]), None)
    return {
        **span,
        "start_sec": round((span["start"]-1)/fps, 3),
        "end_sec": round((span["end"]-1)/fps, 3),
        "samples": len(rows),
        "context_samples": len(context),
        "context_false_tamper_samples": sum(r["tamper"] for r in context),
        "context_unusable_samples": sum(r["unusable"] for r in context),
        "positive_samples": len(positive),
        "positive_tamper_samples": sum(r["tamper"] for r in positive),
        "positive_unusable_samples": sum(r["unusable"] for r in positive),
        "tamper_sample_recall": _safe_ratio(sum(r["tamper"] for r in positive), len(positive)),
        "unusable_sample_fraction": _safe_ratio(sum(r["unusable"] for r in positive), len(positive)),
        "fresh_onset_alert": fresh is not None,
        "any_post_onset_alert": first_any is not None,
        "first_new_alert_delay_seconds": (
            round((fresh["frame"]-span["onset"])/fps, 3) if fresh else ""
        ),
        "preexisting_alert_at_onset": bool(
            context and context[-1]["tamper"]
        ),
        "alert_reasons": "; ".join(sorted(set(
            reason for r in positive for reason in r["reasons"].split("; ")
            if reason
        ))),
    }


def survey(video, annotations, out, *, events_per_class=4, normal_windows=12,
           event_seconds=120., context_seconds=20., normal_seconds=90.,
           sample_seconds=.2):
    if sample_seconds <= 0 or not math.isfinite(sample_seconds):
        raise ValueError("Sample interval must be positive")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"Cannot open {video}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or count <= 0:
            raise ValueError("Bad video metadata")
        runs, annotations_frames = annotation_intervals(annotations)
        if count != annotations_frames:
            raise ValueError(f"Video/CSV frame count mismatch: {count} vs {annotations_frames}")
        spans = select_spans(
            runs, fps, events_per_class, normal_windows,
            event_seconds, context_seconds, normal_seconds,
        )
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, reference = cap.read()
        if not ok:
            raise ValueError("Could not read initial video reference")
        step = max(1, round(fps*sample_seconds))
        results = []
        for i, span in enumerate(spans, 1):
            result = _evaluate_span(cap, reference, span, fps, step)
            results.append(result)
            print(
                f"[{i}/{len(spans)}] {span['name']}: "
                f"tamper {result['positive_tamper_samples']}/{result['positive_samples']}; "
                f"unusable {result['positive_unusable_samples']}/{result['positive_samples']}; "
                f"context false tamper {result['context_false_tamper_samples']}/{result['context_samples']}",
                flush=True,
            )
        by_type = {}
        for kind in (0, 1, 2, 3):
            group = [r for r in results if r["kind"] == kind]
            totals = Counter()
            for r in group:
                for field in ("samples","context_samples","context_false_tamper_samples",
                              "context_unusable_samples","positive_samples",
                              "positive_tamper_samples","positive_unusable_samples"):
                    totals[field] += r[field]
            by_type[LABELS[kind]] = {
                "spans": len(group), **dict(totals),
                "events_newly_alerted": sum(r["fresh_onset_alert"] for r in group),
                "positive_tamper_fraction": _safe_ratio(
                    totals["positive_tamper_samples"], totals["positive_samples"]
                ),
                "positive_unusable_fraction": _safe_ratio(
                    totals["positive_unusable_samples"], totals["positive_samples"]
                ),
                "context_false_tamper_fraction": _safe_ratio(
                    totals["context_false_tamper_samples"], totals["context_samples"]
                ),
            }
        normal = by_type["normal"]
        for r in results:
            if r["kind"] != 0:
                normal["context_samples"] += r["context_samples"]
                normal["context_false_tamper_samples"] += r["context_false_tamper_samples"]
                normal["context_unusable_samples"] += r["context_unusable_samples"]
        normal["context_false_tamper_fraction"] = _safe_ratio(
            normal["context_false_tamper_samples"], normal["context_samples"]
        )
        out.mkdir(parents=True, exist_ok=True)
        csv_out = out / "sampled_event_results.csv"
        with csv_out.open("w",newline="",encoding="utf-8") as handle:
            writer = csv.DictWriter(handle,fieldnames=list(results[0]))
            writer.writeheader()
            writer.writerows(results)
        summary = {
            "evaluation_status":"STRATIFIED_DEVELOPMENT_SURVEY_NOT_FULL_DAY_OR_HELD_OUT",
            "warning":(
                "All spans reset detector state and share only the original "
                "first-frame reference. This is NOT continuous-stream scoring, "
                "and selected intervals do not estimate true 24h incident rates."
            ),
            "video":str(video.resolve()),"annotations":str(annotations.resolve()),
            "fps":fps,"total_video_frames":count,"effective_sample_seconds":step/fps,
            "event_sample_seconds":event_seconds,
            "normal_sample_seconds":normal_seconds,
            "pre_event_context_seconds":context_seconds,
            "by_type":by_type,
            "results_csv":str(csv_out.resolve()),
        }
        summary_path = out / "sampled_event_summary.json"
        summary_path.write_text(json.dumps(summary,indent=2),encoding="utf-8")
        return summary
    finally:
        cap.release()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video",type=Path,required=True)
    p.add_argument("--annotations",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--events-per-class",type=int,default=4)
    p.add_argument("--normal-windows",type=int,default=12)
    p.add_argument("--event-seconds",type=float,default=120.)
    p.add_argument("--context-seconds",type=float,default=20.)
    p.add_argument("--normal-seconds",type=float,default=90.)
    p.add_argument("--sample-seconds",type=float,default=.2)
    args=p.parse_args()
    result=survey(args.video,args.annotations,args.out,
       events_per_class=args.events_per_class,normal_windows=args.normal_windows,
       event_seconds=args.event_seconds,context_seconds=args.context_seconds,
       normal_seconds=args.normal_seconds,sample_seconds=args.sample_seconds)
    print(json.dumps({"status":result["evaluation_status"],
         "by_type":result["by_type"],
         "output":str(args.out.resolve())},indent=2))


if __name__=="__main__":
    main()
