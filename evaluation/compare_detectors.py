from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hog", required=True)
    parser.add_argument("--openvino", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    hog = load(args.hog)
    ov = load(args.openvino)
    winner = "openvino" if ov["occupancy_mae"] < hog["occupancy_mae"] else "hog"
    if ov["occupancy_mae"] == hog["occupancy_mae"]:
        winner = "tie"

    report = {
        "dataset": "EPFL Laboratory six-person sequence, Camera 0 only",
        "metric": "occupancy MAE on labelled timestamps",
        "hog": hog,
        "openvino": ov,
        "lower_mae_detector": winner,
        "interpretation": (
            "Detector choice is based only on this benchmark. Final SIH metrics "
            "also require the controlled training-centre demonstration."
        ),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
