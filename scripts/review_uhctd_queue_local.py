#!/usr/bin/env python3
"""Local-only manual review of Phase 3D target intervals.

The GUI decodes frame previews in memory from the user's licensed recordings.
No frames, clips, faces or images are written to disk or uploaded; only the
reviewer's own numerical/categorical judgements are saved to a separate CSV.
This is a targeted development review, never blind hold-out qualification.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import Counter
from pathlib import Path

import cv2

SCENES = (
    "unreviewed", "camera_displacement", "foreground_change",
    "lighting_ir_change", "visibility_degraded", "unchanged_scene",
    "other", "uncertain",
)
CONFIDENCE = ("unknown", "yes", "no")
STATES = ("UNREVIEWED", "REVIEWED", "NEEDS_SECOND_REVIEW")
DECISION_COLS = (
    "review_id", "day", "category", "start_seconds", "end_seconds",
    "review_status", "scene_classification", "visual_evidence_usable",
    "reference_still_valid", "reviewer_notes",
)


def read_queue(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"Review queue CSV not found: {path}")
    results = []
    seen = set()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {
            "review_id", "day", "category", "start_seconds", "end_seconds",
            "review_start_seconds", "review_end_seconds",
        }
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Queue is missing required columns")
        for row in reader:
            name = row["review_id"]
            if not name or name in seen or row["day"] not in ("day3", "day4"):
                raise ValueError("Duplicate/invalid case ID or dataset")
            if row["category"] not in (
                "carried", "new_near_event", "new_far_from_event"
            ):
                raise ValueError(f"Unexpected case category: {row['category']}")
            seen.add(name)
            try:
                values = [float(row[key]) for key in (
                    "review_start_seconds", "start_seconds", "end_seconds",
                    "review_end_seconds",
                )]
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Bad playback offsets for {name}") from exc
            if not all(math.isfinite(v) for v in values):
                raise ValueError(f"Nonfinite playback offset for {name}")
            a, b, c, d = values
            if a < 0 or a > b or b > c or c > d:
                raise ValueError(f"Nonmonotonic playback interval for {name}")
            results.append(dict(row))
    if not results:
        raise ValueError("Review queue contains no cases")
    return results


def default_decision(item: dict) -> dict:
    return {
        "review_id": item["review_id"],
        "day": item["day"],
        "category": item["category"],
        "start_seconds": item["start_seconds"],
        "end_seconds": item["end_seconds"],
        "review_status": "UNREVIEWED",
        "scene_classification": "unreviewed",
        "visual_evidence_usable": "unknown",
        "reference_still_valid": "unknown",
        "reviewer_notes": "",
    }


def _validate_decision(d: dict) -> None:
    if (d["review_status"] not in STATES
            or d["scene_classification"] not in SCENES
            or d["visual_evidence_usable"] not in CONFIDENCE
            or d["reference_still_valid"] not in CONFIDENCE):
        raise ValueError(f"Invalid classification for {d['review_id']}")
    if (d["review_status"] == "REVIEWED"
            and d["scene_classification"] == "unreviewed"):
        raise ValueError("Select a classification or mark NEEDS_SECOND_REVIEW")
    if len(d["reviewer_notes"]) > 2000:
        raise ValueError("Notes are too long")


def load_decisions(path: Path, cases: list[dict]) -> dict[str, dict]:
    decisions = {item["review_id"]: default_decision(item) for item in cases}
    if not path.is_file():
        return decisions
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not set(DECISION_COLS).issubset(reader.fieldnames or []):
            raise ValueError("Prior review CSV has missing columns")
        encountered = set()
        for row in reader:
            key = row["review_id"]
            if key not in decisions or key in encountered:
                raise ValueError("Prior decisions do not match current queue")
            encountered.add(key)
            d = {column: row[column] for column in DECISION_COLS}
            for name in ("day", "category", "start_seconds", "end_seconds"):
                if d[name] != decisions[key][name]:
                    raise ValueError(f"Previous review case metadata changed: {key}")
            _validate_decision(d)
            decisions[key] = d
    return decisions


def write_decisions(path: Path, queue: list[dict], decisions: dict[str, dict]) -> None:
    # Atomic replace; original generated queue is deliberately untouched.
    if path.suffix.lower() != ".csv":
        raise ValueError("Review output must have .csv suffix")
    if set(decisions) != {q["review_id"] for q in queue}:
        raise ValueError("Review entries do not match case IDs")
    for d in decisions.values():
        _validate_decision(d)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".tmp")
    try:
        with pending.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(DECISION_COLS))
            writer.writeheader()
            for item in queue:
                writer.writerow({
                    col: decisions[item["review_id"]][col] for col in DECISION_COLS
                })
        os.replace(pending, path)
    finally:
        if pending.exists():
            pending.unlink()


def describe(queue: list[dict], decisions: dict[str, dict]) -> dict:
    return {
        "status": "TARGETED_LOCAL_REVIEW_NOT_INDEPENDENT_VALIDATION",
        "cases": len(queue),
        "reviewed": sum(
            d["review_status"] == "REVIEWED" for d in decisions.values()
        ),
        "needs_second_review": sum(
            d["review_status"] == "NEEDS_SECOND_REVIEW" for d in decisions.values()
        ),
        "by_day": dict(Counter(c["day"] for c in queue)),
        "by_scene": dict(Counter(
            d["scene_classification"] for d in decisions.values()
            if d["review_status"] == "REVIEWED"
        )),
        "privacy": (
            "Only reviewer labels saved; frames, people and video never "
            "exported by this tool"
        ),
        "limitations": [
            "Reviewer-selected failure-enriched queue is not representative",
            "Annotation-normal does not certify video usability",
            "No automatic camera-reference enrollment, compliance or attendance action",
        ],
    }


def launch_gui(queue: list[dict], decisions: dict[str, dict], output: Path,
               videos: dict[str, Path]) -> None:
    # Import GUI only when requested so headless CI can test the same CLI.
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError as exc:
        raise RuntimeError("This reviewer needs Windows Python with tkinter") from exc

    root = tk.Tk()
    root.title("KaushalWatch — Local Camera Trust Review (Experimental)")
    root.geometry("1000x780")
    root.minsize(750, 680)
    root.configure(bg="#eef2f2")
    captures: dict[str, cv2.VideoCapture] = {}
    for day, path in videos.items():
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            for old in captures.values():
                old.release()
            root.destroy()
            raise ValueError(f"Cannot open local video for {day}: {path}")
        captures[day] = cap

    state = {"index": 0, "scanning": False, "photo": None, "ignore_slider": False}
    heading = ttk.Label(root, font=("Segoe UI", 15, "bold"))
    heading.pack(pady=(12, 3))
    metadata = ttk.Label(root, wraplength=850, justify="center")
    metadata.pack(pady=(0, 5))
    # Keep navigation above the preview so Windows scaling cannot hide it.
    footer = ttk.Frame(root)
    footer.pack(pady=(0, 7))
    image_label = tk.Label(
        root, bg="#111a1c", width=770, height=350, anchor="center",
        text="Loading local frame…", fg="white",
    )
    image_label.pack(padx=15, pady=4)
    time_label = ttk.Label(root)
    time_label.pack(pady=2)
    seconds = tk.DoubleVar(value=0.0)
    scrub = tk.Scale(
        root, variable=seconds, orient="horizontal", from_=0, to=1,
        resolution=0.333, length=800, showvalue=False,
    )
    scrub.pack(pady=0)
    controls = ttk.Frame(root)
    controls.pack(pady=5)

    scene = tk.StringVar(value=SCENES[0])
    usable = tk.StringVar(value=CONFIDENCE[0])
    reference = tk.StringVar(value=CONFIDENCE[0])
    review_status = tk.StringVar(value=STATES[0])

    form = ttk.Frame(root)
    form.pack(fill="x", padx=17, pady=(10, 0))
    for col, (text, variable, choices) in enumerate((
        ("Observed scene", scene, SCENES),
        ("Evidence usable?", usable, CONFIDENCE),
        ("Reference valid?", reference, CONFIDENCE),
        ("Review status", review_status, STATES),
    )):
        block = ttk.Frame(form)
        block.grid(row=0, column=col, padx=5, sticky="ew")
        ttk.Label(block, text=text).pack(anchor="w")
        ttk.Combobox(
            block, textvariable=variable, values=choices,
            width=23 if col == 0 else 16, state="readonly",
        ).pack(fill="x")
        form.columnconfigure(col, weight=1)
    ttk.Label(
        root,
        text="Reviewer notes (avoid names, faces or personal identifiers)",
    ).pack(anchor="w", padx=22, pady=(10, 0))
    notes = tk.Text(root, height=3, wrap="word")
    notes.pack(fill="x", padx=20)

    def current():
        return queue[state["index"]]

    def bounds() -> tuple[float, float]:
        q = current()
        return float(q["review_start_seconds"]), float(q["review_end_seconds"])

    def display(t: float) -> None:
        lo, hi = bounds()
        t = max(lo, min(hi, float(t)))
        item = current()
        cap = captures[item["day"]]
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            messagebox.showerror("Invalid video", "Video has no usable FPS")
            return
        frame_number = max(0, round(t * fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, image = cap.read()
        if not ok or image is None:
            messagebox.showerror(
                "Decode error", f"Could not decode {item['day']} at {t:.1f}s"
            )
            return
        h, w = image.shape[:2]
        scale = min(790 / w, 345 / h, 1.0)
        if scale < 1.0:
            image = cv2.resize(
                image, (max(1, int(w * scale)), max(1, int(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        hh, ww = rgb.shape[:2]
        ppm = f"P6\n{ww} {hh}\n255\n".encode("ascii") + rgb.tobytes()
        photo = tk.PhotoImage(data=ppm, format="PPM")
        state["photo"] = photo
        image_label.configure(image=photo, text="", width=790, height=345)
        time_label.configure(
            text=(
                f"Offset {t:.1f}s | Review span {lo:.1f}–{hi:.1f}s "
                "| Still-frame scan: not real-time video playback"
            )
        )
        state["ignore_slider"] = True
        seconds.set(t)
        state["ignore_slider"] = False

    def on_scrub(value):
        if not state["ignore_slider"]:
            display(float(value))

    scrub.configure(command=on_scrub)

    def stop_scan():
        state["scanning"] = False
        scan_button.configure(text="Scan frames every 5s")

    def scan_tick():
        if not state["scanning"]:
            return
        _, hi = bounds()
        new_time = seconds.get() + 5.0
        if new_time > hi:
            stop_scan()
            return
        display(new_time)
        root.after(250, scan_tick)

    def toggle_scan():
        if state["scanning"]:
            stop_scan()
        else:
            state["scanning"] = True
            scan_button.configure(text="Stop frame scan")
            scan_tick()

    def step(offset: float):
        stop_scan()
        display(seconds.get() + offset)

    for col, (caption, func) in enumerate((
        ("Start", lambda: step(bounds()[0] - seconds.get())),
        ("−30s", lambda: step(-30)),
        ("−5s", lambda: step(-5)),
        ("+5s", lambda: step(5)),
        ("+30s", lambda: step(30)),
        ("Middle", lambda: step((bounds()[0] + bounds()[1]) / 2 - seconds.get())),
        ("End", lambda: step(bounds()[1] - seconds.get())),
    )):
        ttk.Button(controls, text=caption, command=func).grid(
            row=0, column=col, padx=3
        )
    scan_button = ttk.Button(controls, text="Scan frames every 5s",
                             command=toggle_scan)
    scan_button.grid(row=0, column=7, padx=5)

    def persist():
        row = current()
        d = decisions[row["review_id"]]
        d["scene_classification"] = scene.get()
        d["visual_evidence_usable"] = usable.get()
        d["reference_still_valid"] = reference.get()
        d["review_status"] = review_status.get()
        d["reviewer_notes"] = notes.get("1.0", "end-1c").strip()
        try:
            write_decisions(output, queue, decisions)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not save", str(exc))
            return False
        return True

    def load_case(index: int):
        stop_scan()
        state["index"] = index
        item = current()
        d = decisions[item["review_id"]]
        scene.set(d["scene_classification"])
        usable.set(d["visual_evidence_usable"])
        reference.set(d["reference_still_valid"])
        review_status.set(d["review_status"])
        notes.delete("1.0", "end")
        notes.insert("1.0", d["reviewer_notes"])
        heading.configure(
            text=f"Case {index + 1}/{len(queue)} — {item['review_id']}"
        )
        metadata.configure(
            text=(
                f"{item['category']} | previous incident: {item.get('previous_incident', 'unknown')} "
                f"| flagged samples: {item.get('flagged_samples', 'unknown')}\n"
                f"Original timestamp = recording offset, not civil clock time"
            )
        )
        lo, hi = bounds()
        state["ignore_slider"] = True
        scrub.configure(from_=lo, to=hi)
        seconds.set(lo)
        state["ignore_slider"] = False
        display(lo)

    def navigate(delta: int):
        if not persist():
            return
        target = state["index"] + delta
        if 0 <= target < len(queue):
            load_case(target)
        else:
            messagebox.showinfo(
                "Review boundary", "No more cases in that direction."
            )

    def close():
        stop_scan()
        if not persist():
            return
        for cap in captures.values():
            cap.release()
        root.destroy()

    ttk.Button(footer, text="← Previous", command=lambda: navigate(-1)).pack(
        side="left", padx=5
    )
    ttk.Button(footer, text="Save labels", command=persist).pack(
        side="left", padx=5
    )
    ttk.Button(footer, text="Next →", command=lambda: navigate(1)).pack(
        side="left", padx=5
    )
    ttk.Button(footer, text="Save and close", command=close).pack(
        side="left", padx=5
    )
    ttk.Label(
        root,
        text="Development only • No automatic tampering conclusion • Frames stay in memory",
        foreground="#526063",
    ).pack(pady=3)
    root.protocol("WM_DELETE_WINDOW", close)
    load_case(0)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--day3-video", required=True, type=Path)
    parser.add_argument("--day4-video", required=True, type=Path)
    parser.add_argument("--reviews-out", required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true",
                        help="Check inputs and existing labels without opening GUI")
    args = parser.parse_args()
    queue_path = args.queue.resolve()
    output = args.reviews_out.resolve()
    if queue_path == output:
        parser.error("Output must not overwrite generated queue CSV")
    videos = {
        "day3": args.day3_video.resolve(),
        "day4": args.day4_video.resolve(),
    }
    for day, path in videos.items():
        if not path.is_file():
            parser.error(f"{day} local video is not readable: {path}")
    queue = read_queue(queue_path)
    decisions = load_decisions(output, queue)
    if args.validate_only:
        print(json.dumps(describe(queue, decisions), indent=2))
        return
    launch_gui(queue, decisions, output, videos)


if __name__ == "__main__":
    main()
