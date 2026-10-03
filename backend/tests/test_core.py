import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.camera_trust import assess_camera
from app.services.evidence import dhash, hamming_hex
from app.services.infrastructure import compare_manifest
from app.services.occupancy import discrepancy_pct, OccupancySmoother
from app.services.operability import apparent_motion_state
from app.services.person_detector import build_person_detector, HogPersonDetector
from app.services.compliance_cases import build_infrastructure_case, build_camera_integrity_case
from app.services.anonymous_tracker import AnonymousCentroidTracker
from app.services.person_detector import Detection
from app.services.offline_queue import EdgeEventQueue, bandwidth_measurement


def test_discrepancy():
    assert round(discrepancy_pct(12, 9), 1) == 25.0


def test_smoother_rejects_single_spike():
    s = OccupancySmoother(window=5)
    vals = [10, 10, 2, 10, 10]
    out = [s.update(x) for x in vals]
    assert out[-1] == 10


def test_camera_dark_is_not_trusted():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    trust = assess_camera(frame)
    assert trust.is_too_dark
    assert not trust.trusted


def test_perceptual_hash_stable():
    a = np.zeros((80, 80, 3), dtype=np.uint8)
    assert hamming_hex(dhash(a), dhash(a.copy())) == 0


def test_operability_motion_proxy():
    frames = []
    for x in [5, 10, 15, 20]:
        f = np.zeros((100, 100, 3), dtype=np.uint8)
        f[30:50, x:x+20] = 255
        frames.append(f)
    state, score = apparent_motion_state(frames, (0, 20, 70, 70), threshold=0.1)
    assert state == "APPARENTLY_ACTIVE"
    assert score > 0


def test_manifest_compare():
    manifest = {"items": [
        {"id":"bench","label":"Bench","required":4,"verification_tier":"camera_verifiable"},
        {"id":"meter","label":"Meter","required":5,"verification_tier":"officer_verification_required"},
    ]}
    observed = {"bench":{"observed_count":3,"mean_confidence":0.9}}
    rows = compare_manifest(manifest, observed)
    assert rows[0]["state"] == "DISCREPANCY"
    assert rows[1]["state"] == "OFFICER_VERIFICATION_REQUIRED"


def test_default_detector_factory(monkeypatch):
    monkeypatch.delenv("KAUSHALWATCH_PERSON_DETECTOR", raising=False)
    assert isinstance(build_person_detector(), HogPersonDetector)


def test_infrastructure_case_builder():
    rows = [
        {"id":"panel","label":"Training Panel","required":4,"observed":3,"state":"DISCREPANCY","confidence":0.9},
        {"id":"bench","label":"Workbench","required":4,"observed":4,"state":"COMPLIANT","confidence":0.9},
    ]
    case = build_infrastructure_case("DEMO-KA-104","B1","Construction Electrician",rows)
    assert case is not None
    assert case.case_type == "infrastructure_compliance"
    assert case.details["items"][0]["state"] == "DISCREPANCY"


def test_camera_integrity_case_builder():
    case = build_camera_integrity_case(
        centre_id="DEMO-KA-104",
        batch_id="B1",
        camera_id="CAM-1",
        reasons=["image excessively blurred"],
        trust_score=20.0,
    )
    assert case.case_type == "camera_integrity"
    assert case.severity == "high"
    assert "suspended" in case.summary.lower()


def test_anonymous_tracker_reuses_short_lived_track_id():
    tracker = AnonymousCentroidTracker(max_distance=50, max_missed=1)
    first = tracker.update([Detection(10, 10, 30, 50, 0.9)])
    assert len(first) == 1
    first_id = first[0].track_id
    second = tracker.update([Detection(14, 12, 34, 52, 0.9)])
    assert len(second) == 1
    assert second[0].track_id == first_id
    assert second[0].hits == 2


def test_anonymous_tracker_discards_stale_tracks():
    tracker = AnonymousCentroidTracker(max_distance=50, max_missed=1)
    tracker.update([Detection(10, 10, 30, 50, 0.9)])
    tracker.update([])
    assert len(tracker.tracks) == 1
    tracker.update([])
    assert tracker.tracks == []


def test_edge_queue_round_trip(tmp_path):
    queue = EdgeEventQueue(tmp_path / "edge-queue.json")
    a = queue.enqueue("attendance_observation", {"occupancy": 9})
    b = queue.enqueue("camera_health", {"trust": 98})
    assert [x["event_id"] for x in queue.pending()] == [a["event_id"], b["event_id"]]
    removed = queue.acknowledge([a["event_id"]])
    assert removed == 1
    assert [x["event_id"] for x in queue.pending()] == [b["event_id"]]


def test_bandwidth_measurement_is_data_driven():
    events = [{"event_id":"E1","occupancy":9}]
    result = bandwidth_measurement(raw_video_bytes=1_000_000, events=events, evidence_bytes=10_000)
    assert result["transmitted_bytes"] < result["raw_video_bytes"]
    assert 0 < result["estimated_transfer_reduction_pct"] < 100
