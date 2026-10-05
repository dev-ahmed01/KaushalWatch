from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.start_demo_backend import CALIBRATED_ENV


def test_calibrated_demo_launcher_freezes_selected_attendance_profile():
    assert CALIBRATED_ENV["KAUSHALWATCH_PERSON_DETECTOR"] == "openvino"
    assert CALIBRATED_ENV["KAUSHALWATCH_PERSON_CONFIDENCE"] == "0.45"
    assert CALIBRATED_ENV["KAUSHALWATCH_OPENVINO_TILED"] == "1"
    assert CALIBRATED_ENV["KAUSHALWATCH_OPENVINO_TILE_OVERLAP"] == "0.18"
    assert CALIBRATED_ENV["KAUSHALWATCH_OPENVINO_TILE_NMS_IOU"] == "0.45"
    assert CALIBRATED_ENV["KAUSHALWATCH_ATTENDANCE_COUNT_SOURCE"] == "confirmed"
    assert CALIBRATED_ENV["KAUSHALWATCH_OCCUPANCY_SMOOTHER_WINDOW"] == "3"


def test_generic_env_keeps_tiled_inference_opt_in():
    env_text = (REPO_ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    assert "KAUSHALWATCH_OPENVINO_TILED=0" in env_text
    assert "KAUSHALWATCH_ATTENDANCE_COUNT_SOURCE=registered" in env_text
    assert "KAUSHALWATCH_OCCUPANCY_SMOOTHER_WINDOW=5" in env_text


def test_demo_env_enables_calibrated_tiled_inference():
    env_text = (REPO_ROOT / "backend" / ".env.demo.example").read_text(encoding="utf-8")
    assert "KAUSHALWATCH_OPENVINO_TILED=1" in env_text
    assert "KAUSHALWATCH_ATTENDANCE_COUNT_SOURCE=confirmed" in env_text
    assert "KAUSHALWATCH_OCCUPANCY_SMOOTHER_WINDOW=3" in env_text
