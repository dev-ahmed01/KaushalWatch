import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.compliance_cases import build_practical_activity_case
from app.services.practical_activity_pipeline import validate_work_zones


def test_validate_work_zones_accepts_in_bounds_cells():
    validate_work_zones(
        [
            {"zone_id": "work_zone_1", "x": 10, "y": 20, "w": 100, "h": 120},
            {"zone_id": "work_zone_2", "x": 200, "y": 30, "w": 80, "h": 90},
        ],
        width=640,
        height=480,
    )


def test_validate_work_zones_rejects_out_of_bounds_cell():
    with pytest.raises(ValueError, match="outside video bounds"):
        validate_work_zones(
            [{"zone_id": "work_zone_1", "x": 600, "y": 20, "w": 100, "h": 120}],
            width=640,
            height=480,
        )


def test_practical_activity_case_created_when_authorization_absent():
    case = build_practical_activity_case(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO-01",
        camera_id="LAB-CAM-03",
        authorization="absent",
        practical_activity_fraction=0.77,
        active_work_cells=2,
    )

    assert case is not None
    assert case.case_type == "practical_activity_authorization"
    assert case.severity == "high"
    assert case.details["authorization"] == "absent"
    assert case.details["active_work_cells"] == 2
    assert case.details["individual_identification"] is False


def test_practical_activity_case_not_created_for_valid_authorization():
    case = build_practical_activity_case(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO-01",
        camera_id="LAB-CAM-03",
        authorization="valid",
        practical_activity_fraction=0.44,
        active_work_cells=1,
    )

    assert case is None


def test_unknown_authorization_requires_review_case():
    case = build_practical_activity_case(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-DEMO-01",
        camera_id="LAB-CAM-03",
        authorization="unknown",
        practical_activity_fraction=0.44,
        active_work_cells=1,
    )

    assert case is not None
    assert case.case_type == "practical_activity_authorization_review"
    assert case.severity == "medium"
