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


class GroundingDinoAdapter:
    """Optional adapter boundary. The core attendance demo never depends on this class."""

    def __init__(self, prompts: list[str]):
        self.prompts = prompts
        self._ready = False

    def setup(self) -> None:
        raise RuntimeError(
            "GroundingDINO is optional and not installed by core requirements. "
            "Validate it separately or use cached demo detections."
        )

    def detect_at(self, second: float) -> list[dict]:
        return [] if not self._ready else []
