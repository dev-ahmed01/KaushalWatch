from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def project_path(env_name: str, default_relative: str) -> Path:
    """Resolve a configurable project asset path.

    Relative environment values are interpreted from the repository root so the
    same .env works whether uvicorn is launched from repo root or backend/.
    """
    raw = os.getenv(env_name, default_relative).strip()
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def demo_manifest_path() -> Path:
    return project_path(
        "KAUSHALWATCH_MANIFEST_PATH",
        "configs/job_roles/construction_electrician.demo.json",
    )


def equipment_cache_path() -> Path:
    return project_path(
        "KAUSHALWATCH_EQUIPMENT_CACHE",
        "demo/cached_detections/dod_110930728.reviewed.json",
    )


def demo_scenario_path() -> Path:
    return project_path(
        "KAUSHALWATCH_SCENARIO_PATH",
        "demo/scenarios/final-demo.example.json",
    )
