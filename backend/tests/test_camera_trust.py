"""Camera trust regression coverage; never check in UHCTD media."""
import cv2
import numpy as np

from app.services.camera_trust import CameraTrustState, assess_camera


def _scene():
    frame = np.full((180, 240, 3), 120, dtype=np.uint8)
    cv2.rectangle(frame, (25, 30), (95, 125), (220, 220, 220), -1)
    cv2.rectangle(frame, (130, 15), (210, 165), (30, 30, 30), 3)
    cv2.line(frame, (5, 170), (230, 70), (10, 10, 10), 3)
    return frame


def _stream(frames, seconds=0.5):
    state = CameraTrustState()
    return [assess_camera(f, state=state, sample_seconds=seconds) for f in frames]


def test_normal_static_with_small_variation_does_not_trigger_frozen_feed():
    base = _scene()
    frames = []
    for i in range(25):
        frame = base.copy()
        frame[3, 3] = (i % 10) * 9
        frames.append(frame)
    results = _stream(frames)
    assert all(item.trusted for item in results)
    assert not any(item.is_frozen for item in results)


def test_identical_replayed_frames_trigger_after_sustained_interval():
    base = _scene()
    results = _stream([base.copy() for _ in range(10)])
    assert results[0].trusted
    assert results[-1].is_frozen
    assert not results[-1].trusted


def test_full_bright_obstruction_detected_after_persistence():
    base = _scene()
    covered = np.full_like(base, 125)
    results = _stream([base] * 4 + [covered] * 9)
    assert all(result.trusted for result in results[:4])
    assert not results[-1].trusted
    assert any("obstructed" in reason for reason in results[-1].reasons)


def test_progressive_defocus_reduces_trust():
    base = _scene()
    blurred = cv2.GaussianBlur(base, (35, 35), 12)
    results = _stream([base] * 2 + [blurred] * 9)
    assert results[-1].is_blurry
    assert not results[-1].trusted


def test_viewpoint_displacement_on_structured_scene_suspends_trust():
    base = _scene()
    moved = np.roll(base, 60, axis=1)
    results = _stream([base] * 2 + [moved] * 9)
    assert results[-1].scene_shift
    assert not results[-1].trusted


def test_black_video_untrusted_and_state_not_reused_across_records():
    base = _scene()
    dark = np.zeros_like(base)
    first = _stream([base] * 2 + [dark] * 6)
    assert not first[-1].trusted
    assert first[-1].is_too_dark
    new_recording = _stream([base.copy(), base.copy()])
    assert all(result.trusted for result in new_recording)


def test_one_frame_occlusion_does_not_trigger_exception():
    base = _scene()
    covered = np.full_like(base, 200)
    result = _stream([base] * 5 + [covered] + [base] * 6)
    assert all(v.trusted for v in result)


def test_independent_background_texture_frames_not_viewpoint_tamper():
    rng = np.random.default_rng(20261004)
    frames = [
        rng.integers(90, 220, size=(180, 240, 3), dtype=np.uint8)
        for _ in range(30)
    ]
    results = _stream(frames, seconds=0.2)
    assert all(v.trusted for v in results)
    assert not any(v.scene_shift for v in results)
