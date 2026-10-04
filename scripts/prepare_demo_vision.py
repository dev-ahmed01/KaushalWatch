from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VISION_REQUIREMENTS = ROOT / "backend" / "requirements-vision.txt"
DOWNLOAD_SCRIPT = ROOT / "scripts" / "download_openvino_person_model.py"
MODEL_XML = (
    ROOT
    / "models"
    / "openvino"
    / "person-detection-retail-0013"
    / "FP16"
    / "person-detection-retail-0013.xml"
)


def run(command: list[str]) -> None:
    print("+", " ".join(command), file=sys.stderr)
    subprocess.run(command, cwd=ROOT, check=True)


def readiness() -> dict:
    model_bin = MODEL_XML.with_suffix(".bin")
    openvino_available = importlib.util.find_spec("openvino") is not None
    return {
        "ready": bool(openvino_available and MODEL_XML.exists() and model_bin.exists()),
        "detector": "openvino",
        "openvino_python_available": openvino_available,
        "model_xml": str(MODEL_XML),
        "model_xml_exists": MODEL_XML.exists(),
        "model_bin": str(model_bin),
        "model_bin_exists": model_bin.exists(),
        "automatic_selection": (
            "KaushalWatch auto mode prefers this benchmarked local OpenVINO model "
            "when the runtime and verified model files are present."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare the benchmarked KaushalWatch OpenVINO person detector."
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install backend/requirements-vision.txt into the active Python environment.",
    )
    parser.add_argument(
        "--refresh-model",
        action="store_true",
        help="Re-run the checksum-verified OpenVINO model download.",
    )
    args = parser.parse_args()

    if args.install:
        run([sys.executable, "-m", "pip", "install", "-r", str(VISION_REQUIREMENTS)])

    if args.refresh_model or not MODEL_XML.exists() or not MODEL_XML.with_suffix(".bin").exists():
        run([sys.executable, str(DOWNLOAD_SCRIPT)])

    payload = readiness()
    print(json.dumps(payload, indent=2))
    if not payload["ready"]:
        raise SystemExit(
            "Vision runtime is not ready. Run this command again with --install "
            "inside the same environment used to start the API."
        )


if __name__ == "__main__":
    main()
