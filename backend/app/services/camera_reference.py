"""Explicitly reviewed, SHA256-verified camera reference selection.

No auto-learning and no content-driven day/night reference switching:
the operator must supply a known camera ID and a mode selected using
information independent of the potentially tampered camera image.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from app.services.camera_trust import CameraTrustState


def load_reviewed_reference(
    manifest_path: str | Path,
    *,
    camera_id: str,
    mode: str,
) -> CameraTrustState:
    manifest_path = Path(manifest_path).resolve()
    if not camera_id or not mode:
        raise ValueError("camera ID and reference mode are required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or manifest.get("camera_id") != camera_id:
        raise ValueError("Reference manifest version or camera mismatch")
    matching = [r for r in manifest.get("references", []) if r.get("mode") == mode]
    if len(matching) != 1:
        raise ValueError("Exactly one reviewed reference must match the selected mode")
    record = matching[0]
    if not (record.get("approved") is True and record.get("id") and
            record.get("reviewed_by") and record.get("reviewed_at")):
        raise ValueError("Reference must have explicit operator approval metadata")
    image_path = Path(record["image_path"])
    if not image_path.is_absolute():
        image_path = manifest_path.parent / image_path
    encoded = image_path.read_bytes()
    expected = record.get("sha256", "")
    if len(expected) != 64 or hashlib.sha256(encoded).hexdigest() != expected:
        raise ValueError("Reviewed image reference SHA256 mismatch")
    decoded = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None or decoded.size == 0:
        raise ValueError("Invalid reviewed reference image")
    return CameraTrustState(
        reference_frame=decoded.copy(),
        reference_reviewed=True,
        reference_id=str(record["id"]),
        reference_mode=mode,
    )
