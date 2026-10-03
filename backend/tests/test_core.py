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
