from __future__ import annotations

import argparse
from pathlib import Path
import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a deterministic non-sensitive CCTV-style test clip.")
    parser.add_argument("--out", required=True)
    parser.add_argument("--seconds", type=int, default=8)
    parser.add_argument("--fps", type=int, default=10)
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    width, height = 640, 360
    writer = cv2.VideoWriter(
        str(out),
        cv2.VideoWriter_fourcc(*"MJPG"),
        args.fps,
        (width, height),
    )
    if not writer.isOpened():
        raise SystemExit("Could not create test video")

    try:
        for i in range(args.seconds * args.fps):
            # Bright textured scene with continuous motion so camera-health checks stay trustworthy.
            frame = np.full((height, width, 3), 150, dtype=np.uint8)
            for x in range(0, width, 40):
                cv2.line(frame, (x, 0), (x, height), (125, 125, 125), 1)
            for y in range(0, height, 40):
                cv2.line(frame, (0, y), (width, y), (175, 175, 175), 1)

            # Moving coloured blocks deliberately do not resemble pedestrians to HOG.
            offset = (i * 7) % (width - 120)
            cv2.rectangle(frame, (offset, 80), (offset + 70, 145), (40, 120, 220), -1)
            cv2.circle(frame, (width - 80 - (i * 4) % 180, 250), 28, (210, 90, 60), -1)
            cv2.putText(
                frame, f"KAUSHALWATCH E2E FRAME {i:03d}",
                (18, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2,
            )
            writer.write(frame)
    finally:
        writer.release()

    print(out)


if __name__ == "__main__":
    main()
