from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.vision_profile import (
    load_dataset_manifests,
    load_vision_profile,
    validate_dataset_manifest,
    validate_vision_profile,
)


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate KaushalWatch vision-profile provenance and dataset manifests. "
            "This does not run detector benchmarks; it verifies that calibration and "
            "held-out evaluation inputs are structurally ready."
        )
    )
    parser.add_argument(
        "--profile",
        help="Optional vision profile path. Defaults to KAUSHALWATCH_VISION_PROFILE or the frozen SIH profile.",
    )
    parser.add_argument(
        "--dataset",
        help="Optional candidate dataset manifest to validate in addition to registered manifests.",
    )
    parser.add_argument(
        "--strict-candidate",
        action="store_true",
        help="Fail when a candidate dataset has missing declared annotation coverage.",
    )
    args = parser.parse_args()

    profile_path = Path(args.profile).expanduser().resolve() if args.profile else None
    profile = load_vision_profile(profile_path)
    profile_errors = validate_vision_profile(profile)

    registered = load_dataset_manifests()
    candidate_validation = None
    candidate_path = None
    if args.dataset:
        candidate_path = Path(args.dataset).expanduser().resolve()
        if not candidate_path.exists():
            raise SystemExit(f"Dataset manifest not found: {candidate_path}")
        candidate_validation = validate_dataset_manifest(_load_json(candidate_path))

    payload = {
        "profile": {
            "profile_id": profile["profile_id"],
            "status": profile.get("status"),
            "valid": not profile_errors,
            "errors": profile_errors,
        },
        "registered_datasets": [
            {
                "dataset_id": row.get("dataset_id"),
                "status": row.get("status"),
                "path": row.get("path"),
                "valid": row.get("valid"),
                "split_roles": row.get("split_roles", []),
                "annotation_coverage": row.get("annotation_coverage", {}),
                "warnings": row.get("warnings", []),
            }
            for row in registered
        ],
        "candidate": (
            {
                "path": str(candidate_path),
                **candidate_validation,
            }
            if candidate_validation is not None
            else None
        ),
        "promotion_workflow": [
            "1. Register fixed-camera calibration and held-out splits in a dataset manifest.",
            "2. Tune detector/temporal/geometry settings only on the calibration split.",
            "3. Freeze a new vision profile candidate before viewing held-out results.",
            "4. Run held-out attendance, activity, equipment, operability and camera-trust evaluations for the labels the dataset supports.",
            "5. Compare against the currently frozen metrics and document any trade-off.",
            "6. Promote by setting KAUSHALWATCH_VISION_PROFILE only after review.",
        ],
        "claim_boundary": (
            "A structurally valid dataset manifest is not evidence of model accuracy. "
            "Accuracy claims require the corresponding held-out evaluation artifacts."
        ),
    }

    print(json.dumps(payload, indent=2))

    if profile_errors:
        raise SystemExit(2)
    if candidate_validation is not None and not candidate_validation["valid"]:
        raise SystemExit(3)
    if args.strict_candidate and candidate_validation is not None:
        missing = [
            purpose
            for purpose, covered in candidate_validation["annotation_coverage"].items()
            if not covered
        ]
        if missing:
            raise SystemExit(
                "Candidate is structurally valid but missing annotation coverage for: "
                + ", ".join(missing)
            )


if __name__ == "__main__":
    main()
