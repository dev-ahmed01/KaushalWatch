from __future__ import annotations
import json
from pathlib import Path
from typing import Protocol


class EquipmentDetector(Protocol):
    def detect_at(self, second: float) -> list[dict]: ...


class CachedEquipmentDetector:
    """Stage-safe fallback that consumes detections precomputed on the exact demo clip."""

    def __init__(self, path: Path):
        self.rows = json.loads(path.read_text()) if path.exists() else []

    def detect_at(self, second: float) -> list[dict]:
        if not self.rows:
            return []
        closest = min(self.rows, key=lambda r: abs(float(r.get("second", 0)) - second))
        return closest.get("detections", [])


# Optional model loader remains lazy inside the adapter; importing the core
# attendance API does not import Torch/Transformers or download any checkpoints.
from app.services.live_equipment import GroundingDinoAdapter
