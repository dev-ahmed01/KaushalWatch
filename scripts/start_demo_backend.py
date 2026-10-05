from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

CALIBRATED_ENV = {
    "KAUSHALWATCH_PERSON_DETECTOR": "openvino",
    "KAUSHALWATCH_PERSON_CONFIDENCE": "0.45",
    "KAUSHALWATCH_OPENVINO_TILED": "1",
    "KAUSHALWATCH_OPENVINO_TILE_OVERLAP": "0.18",
    "KAUSHALWATCH_OPENVINO_TILE_NMS_IOU": "0.45",
    "KAUSHALWATCH_ATTENDANCE_COUNT_SOURCE": "confirmed",
    "KAUSHALWATCH_OCCUPANCY_SMOOTHER_WINDOW": "3",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start KaushalWatch with the calibrated SIH attendance demo profile."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    for name, value in CALIBRATED_ENV.items():
        os.environ[name] = value

    from app.services.person_detector import build_person_detector

    detector = build_person_detector()
    if detector.info.backend != "openvino" or not detector.info.authoritative:
        raise SystemExit(
            "Calibrated demo backend requires the authoritative OpenVINO detector. "
            "Run 'python scripts/prepare_demo_vision.py --install' first. "
            f"Current detector: {detector.info.message}"
        )

    if "tiled=on" not in detector.info.message:
        raise SystemExit(
            "Calibrated attendance profile did not enable tiled OpenVINO inference."
        )

    print("KaushalWatch calibrated attendance demo profile")
    print(f"  detector: {detector.info.message}")
    print("  calibration: manual 5-worker target clip; broader held-out validation pending")
    print(f"  API: http://{args.host}:{args.port}")

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(BACKEND)] if args.reload else None,
    )


if __name__ == "__main__":
    main()
