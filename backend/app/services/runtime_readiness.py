from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.services.demo_assets import load_demo_manifest_and_cache


def build_runtime_readiness(
    *,
    attendance_detector,
    practical_detector,
    zones_path: Path,
    evidence_path: Path,
    infrastructure_probe: Callable[[], object] = load_demo_manifest_and_cache,
) -> dict:
    """Build the shared readiness payload used by the API and assistant."""
    zones_ready = zones_path.exists()
    practical_ready = zones_ready and bool(practical_detector.authoritative)

    try:
        infrastructure_probe()
        infrastructure_ready = True
        infrastructure_message = (
            "Stage-safe infrastructure manifest and cached detector telemetry are available."
        )
    except (FileNotFoundError, ValueError) as exc:
        infrastructure_ready = False
        infrastructure_message = f"Infrastructure demo assets unavailable: {exc}"

    if practical_ready:
        practical_message = (
            f"{practical_detector.backend} detector and bundled work-zone profiles are available."
        )
    elif not zones_ready:
        practical_message = (
            "Practical-work runtime unavailable: bundled work-zone profiles are missing."
        )
    else:
        practical_message = (
            "Practical-work analysis can process the video, but final conclusions are "
            "withheld because the active detector is non-authoritative: "
            f"{practical_detector.message}"
        )

    return {
        "vision_setup": {
            "selected_demo_detector": "openvino",
            "command": "python scripts/prepare_demo_vision.py --install",
            "note": (
                "Run the setup command in the same Python environment used to start "
                "the API. Auto mode will then prefer the benchmarked local OpenVINO model."
            ),
        },
        "attendance": {
            "ready": bool(attendance_detector.authoritative),
            "backend": attendance_detector.backend,
            "mode": attendance_detector.mode,
            "message": attendance_detector.message,
        },
        "practical_work": {
            "ready": practical_ready,
            "backend": practical_detector.backend,
            "mode": practical_detector.mode,
            "authoritative": bool(practical_detector.authoritative),
            "processing_available": zones_ready,
            "default_zone_profiles": ["default", "authorized", "unauthorized"],
            "message": practical_message,
        },
        "infrastructure": {
            "ready": infrastructure_ready,
            "mode": "stage_safe_cached_adapter",
            "message": infrastructure_message,
        },
        "evidence": {
            "ready": evidence_path.exists(),
            "privacy_note": (
                "Person regions are blurred where a primary person detector is available; "
                "human review remains required."
            ),
        },
    }
