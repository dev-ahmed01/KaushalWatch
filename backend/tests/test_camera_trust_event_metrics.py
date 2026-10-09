"""Guard against inflated tampering-event recall from already-active alerts."""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import evaluate_uhctd_camera_trust as evaluator  # noqa: E402


def _source(tmp_path):
    video = tmp_path / "event.avi"
    csv_path = tmp_path / "event.csv"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (80, 60))
    assert writer.isOpened()
    try:
        for index in range(20):
            image = np.full((60, 80, 3), 110 + index % 3, dtype=np.uint8)
            writer.write(image)
    finally:
        writer.release()
    with csv_path.open("w", newline="") as file:
        labels = csv.writer(file)
        for index in range(20):
            labels.writerow([index + 1, 0 if index < 6 else 1, 0, 0, 0])
    return video, csv_path


def _fake_state(alert):
    return SimpleNamespace(
        trusted=not alert,
        tamper_suspected=alert,
        quality_status="SUFFICIENT",
        reasons=["camera viewpoint may have shifted"] if alert else [],
    )


def test_active_alert_before_onset_cannot_count_as_new_detection(tmp_path, monkeypatch):
    video, annotations = _source(tmp_path)
    monkeypatch.setattr(evaluator, "assess_camera", lambda *args, **kwargs: _fake_state(True))
    summary, events = evaluator.score_recording(
        video, annotations, sample_seconds=0.1, verbose=False
    )
    assert summary["per_tamper_class"]["covered"]["events_detected"] == 0
    assert summary["per_tamper_class"]["covered"]["events_with_preexisting_tamper_alert"] == 1
    assert events[0]["any_alert_during_event"]
    assert not events[0]["detected"]
    assert events[0]["preexisting_tamper_alert"]


def test_new_rising_alert_inside_event_counts_once(tmp_path, monkeypatch):
    video, annotations = _source(tmp_path)
    counter = iter(range(20))
    def fake_assess(*args, **kwargs):
        return _fake_state(next(counter) >= 8)
    monkeypatch.setattr(evaluator, "assess_camera", fake_assess)
    summary, events = evaluator.score_recording(
        video, annotations, sample_seconds=0.1, verbose=False
    )
    assert summary["per_tamper_class"]["covered"]["events_detected"] == 1
    assert events[0]["detected"]
    assert not events[0]["preexisting_tamper_alert"]
    assert events[0]["detection_delay_seconds"] == 0.2
