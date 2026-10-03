from __future__ import annotations

import argparse
import csv
import shlex
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert EPFL per-person bounding-box ground truth into timestamp occupancy counts."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--fps", type=float, default=25.0)
    parser.add_argument("--step-frames", type=int, default=25)
    args = parser.parse_args()

    counts: Counter[int] = Counter()
    for raw in Path(args.input).read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        cols = shlex.split(raw)
        if len(cols) < 10:
            continue

        # External EPFL derivative annotation columns:
        # id xmin ymin xmax ymax frame lost occluded generated label
        frame = int(float(cols[5]))
        lost = int(float(cols[6]))
        label = cols[9].strip('"').upper()
        if label == "PERSON" and lost == 0:
            counts[frame] += 1

    if not counts:
        raise SystemExit("No usable PERSON annotations found")

    first_frame = min(counts)
    last_frame = max(counts)
    selected = [
        frame for frame in range(first_frame, last_frame + 1)
        if (frame - first_frame) % args.step_frames == 0
    ]

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "second", "true_count"])
        writer.writeheader()
        for frame in selected:
            writer.writerow({
                "frame": frame,
                "second": round(frame / args.fps, 4),
                "true_count": counts.get(frame, 0),
            })

    print(f"wrote {len(selected)} labelled timestamps to {out}")


if __name__ == "__main__":
    main()
