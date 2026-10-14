from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

from app.services.action_queue import build_action_queue
from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore
from app.services.centre_settings import CentreSettingsStore
from app.services.demo_network import DEMO_CENTRES, centre_rows
from app.services.kaushalai_briefing import build_network_brief
from app.services.network_insights import build_network_insights
from app.services.vision_profile import load_vision_profile, validate_vision_profile
from scripts.prepare_demo_state import prepare_demo_state


PRIMARY_IDS = (
    "DEMO-KA-104",
    "DEMO-KA-112",
    "DEMO-KA-207",
    "DEMO-KA-303",
    "DEMO-KA-509",
)


def _group_history(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("centre_id") or ""), []).append(row)
    return grouped


def main() -> None:
    checks: list[dict] = []

    profile = load_vision_profile()
    profile_errors = validate_vision_profile(profile)
    checks.append({
        "check": "vision_profile_valid",
        "ok": not profile_errors,
        "detail": profile["profile_id"] if not profile_errors else "; ".join(profile_errors),
    })

    with tempfile.TemporaryDirectory(prefix="kaushalwatch-release-gate-") as temp:
        data = Path(temp) / "data"
        seed = prepare_demo_state(data)
        store = CaseStore(data / "cases.json")
        history_store = AnalysisHistoryStore(data / "analysis_history.json")
        settings_store = CentreSettingsStore(data / "centre_settings.json")

        cases = store.list()
        history = history_store.list(limit=500)
        settings = {
            centre["centre_id"]: settings_store.get(centre["centre_id"])
            for centre in DEMO_CENTRES
        }
        rows = centre_rows(
            cases,
            settings_by_centre=settings,
            history_by_centre=_group_history(history),
        )

        brief = build_network_brief(
            centres=rows,
            cases=cases,
            history=history,
            period="yesterday",
        )
        insights = build_network_insights(
            centres=rows,
            cases=cases,
            history=history,
            period="last_7_days",
        )
        actions = build_action_queue(
            centres=rows,
            cases=cases,
            history=history,
            period="yesterday",
        )

        primary_ids = [row["centre_id"] for row in brief["centres"]]
        checks.append({
            "check": "primary_scope_is_exactly_five_centres",
            "ok": tuple(primary_ids) == PRIMARY_IDS,
            "detail": primary_ids,
        })

        expected_counts = {
            "total": 5,
            "verified": 2,
            "review": 2,
            "uncertain": 1,
            "unavailable": 0,
        }
        actual_counts = {
            key: brief["counts"][key]
            for key in expected_counts
        }
        checks.append({
            "check": "network_story_matches_release_seed",
            "ok": actual_counts == expected_counts,
            "detail": actual_counts,
        })

        checks.append({
            "check": "insights_scope_matches_primary_scope",
            "ok": insights["counts"]["total"] == 5,
            "detail": insights["counts"],
        })

        action_labels = [
            f"{item['centre_id']}::{item['title']}"
            for item in actions["actions"]
        ]
        expected_action_labels = [
            "DEMO-KA-303::Review infrastructure exception",
            "DEMO-KA-207::Verify camera evidence",
            "DEMO-KA-104::Review attendance evidence",
            "DEMO-KA-104::Confirm low-activity context",
        ]
        checks.append({
            "check": "ranked_action_story_is_deterministic",
            "ok": action_labels == expected_action_labels,
            "detail": action_labels,
        })

        seeded_cases = set(seed["cases"])
        required_cases = {
            "SIM-KA-104-ATT",
            "SIM-KA-207-CAM",
            "SIM-KA-303-INF",
            "SIM-KA-104-DUP",
        }
        checks.append({
            "check": "review_and_integrity_cases_seeded",
            "ok": required_cases.issubset(seeded_cases),
            "detail": sorted(seeded_cases),
        })

        duplicate = next(
            (item for item in seed["evidence"] if item["evidence_id"] == "SIM-EV-KA104-DUP"),
            None,
        )
        checks.append({
            "check": "duplicate_evidence_fixture_detected",
            "ok": bool(duplicate and duplicate.get("duplicate_of") == "SIM-EV-KA104-01"),
            "detail": duplicate,
        })

    ready = all(item["ok"] for item in checks)
    payload = {
        "ready": ready,
        "primary_scope": list(PRIMARY_IDS),
        "checks": checks,
        "judge_day_sequence": [
            "python scripts/prepare_demo_state.py --yes",
            "python scripts/validate_vision_profile.py",
            "python scripts/check_release_readiness.py",
            "python scripts/start_demo_backend.py",
            "cd web && npm run dev",
        ],
        "strict_real_video_gate": (
            "Run scripts/check_demo_readiness.py --video <exact-video> --final "
            "after the OpenVINO runtime and exact reviewed video are present."
        ),
        "claim_boundary": (
            "This release gate verifies deterministic product state and configuration. "
            "It does not create new model-accuracy claims."
        ),
    }
    print(json.dumps(payload, indent=2))
    raise SystemExit(0 if ready else 2)


if __name__ == "__main__":
    main()
