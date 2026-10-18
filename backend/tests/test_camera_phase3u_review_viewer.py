"""Phase3U blind/local frame reviewer: CSV safety, exact seeking and recovery."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from phase3t_review_viewer_core import (  # noqa: E402
    CASE_KEY, CHOICES, FIELDS, NOTES, FrameBounds, ReviewSession,
    format_video_time, read_exact_frame, read_sequential_frame,
)


def _row(n: int = 1):
    row = {field: "" for field in FIELDS}
    row.update({
        "case_id": f"KWT3T-{n:03d}",
        "video_alias": "DAY3" if n % 2 else "DAY4",
        "start_frame": str(100 * n + 1),
        "end_frame": str(100 * n + 540),
    })
    return row


def _write(path: Path, rows: list[dict]):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_assignments_open_without_model_predictions_and_source_is_immutable(tmp_path):
    source = tmp_path / "reviewer_01.csv"
    output = tmp_path / "reviewer_01_completed_local.csv"
    _write(source, [_row(1), _row(2)])
    before = source.read_bytes()
    s = ReviewSession(source, output)
    assert s.completed_count == 0
    assert not output.exists()
    answers = {col: "yes" if "confidence" not in col else "high"
               for col in CHOICES}
    answers["footage_available_yes_no_unknown"] = "yes"
    answers["reviewer_id"] = "reviewer01"
    answers[NOTES] = "Checked at source, no identifying detail."
    s.update(0, answers)
    assert s.completed(0)
    assert not s.completed(1)
    s.save()
    assert source.read_bytes() == before
    assert output.exists()
    assert not list(tmp_path.glob(".phase3u-review-*.tmp"))
    resumed = ReviewSession(source, output)
    assert resumed.completed_count == 1
    assert resumed.rows[0]["reviewer_id"] == "reviewer01"
    assert all(k not in resumed.rows[0] for k in
               ("candidate_policies", "model_prediction", "sealed_model_key"))


def test_partial_case_remains_incomplete_and_persists(tmp_path):
    source = tmp_path / "reviewer_01.csv"
    output = tmp_path / "reviewer_01_completed_local.csv"
    _write(source, [_row(1)])
    s = ReviewSession(source, output)
    s.update(0, {"reviewer_id": "reviewer01",
                 "visible_focus_loss_yes_no_uncertain": "uncertain"})
    s.save()
    resumed = ReviewSession(source, output)
    assert resumed.completed_count == 0
    assert resumed.rows[0]["visible_focus_loss_yes_no_uncertain"] == "uncertain"


def test_original_assignment_never_overwritten(tmp_path):
    source = tmp_path / "reviewer_01.csv"
    _write(source, [_row()])
    with pytest.raises(ValueError, match="Never overwrite"):
        ReviewSession(source, source)


def test_old_completed_sheet_from_different_assignment_rejected(tmp_path):
    original = tmp_path / "reviewer_01.csv"
    saved = tmp_path / "reviewer_01_completed_local.csv"
    _write(original, [_row()])
    tampered = _row()
    tampered["end_frame"] = "9999"
    _write(saved, [tampered])
    with pytest.raises(ValueError, match="Saved worksheet changes"):
        ReviewSession(original, saved)


def test_extra_prediction_columns_and_hidden_scores_rejected(tmp_path):
    path = tmp_path / "reviewer_01.csv"
    row = _row()
    row["candidate_policies"] = "supposed_false_alarm"
    with path.open("w", encoding="utf-8", newline="") as fd:
        w = csv.DictWriter(fd, fieldnames=[*FIELDS, "candidate_policies"])
        w.writeheader()
        w.writerow(row)
    with pytest.raises(ValueError, match="blinded Phase3T"):
        ReviewSession(path, tmp_path/"answers.csv")


@pytest.mark.parametrize("change,pattern", [
    ({"case_id": "=cmd()"}, "Invalid case ID"),
    ({"video_alias": "DAY5"}, "Unknown video"),
    ({"start_frame": "0"}, "Invalid frame"),
    ({"end_frame": "1"}, "Reversed frame"),
    ({"footage_available_yes_no_unknown": "confirmed_true"}, "Unexpected option"),
    ({"short_observation_notes_without_person_identifiers": "=HYPERLINK(1)"}, "Unsafe notes"),
])
def test_malformed_and_spreadsheet_injection_rows_rejected(tmp_path, change, pattern):
    path = tmp_path / "worksheet.csv"
    row = _row()
    row.update(change)
    _write(path, [row])
    with pytest.raises(ValueError, match=pattern):
        ReviewSession(path, tmp_path / "completed.csv")


def test_mutation_cannot_change_case_frame_identity_or_model_columns(tmp_path):
    path = tmp_path / "worksheet.csv"
    _write(path, [_row()])
    s = ReviewSession(path, tmp_path/"completed.csv")
    with pytest.raises(ValueError, match="immutable"):
        s.update(0, {"start_frame": "130"})
    with pytest.raises(ValueError, match="immutable"):
        s.update(0, {"candidate_policies": "positive"})
    assert s.rows[0]["start_frame"] == "101"


def test_duplicate_case_ids_rejected(tmp_path):
    path = tmp_path/"worksheet.csv"
    _write(path, [_row(), _row()])
    with pytest.raises(ValueError, match="Duplicate case"):
        ReviewSession(path, tmp_path/"completed.csv")


def test_time_display_relative_not_wallclock_and_bounds():
    assert format_video_time(1, 10.0) == "00:00:00.000"
    assert format_video_time(36001, 10.0) == "01:00:00.000"
    assert format_video_time(1801, 3.0) == "00:10:00.000"
    with pytest.raises(ValueError, match="Invalid frame timestamp"):
        format_video_time(5, 0.0)
    bounds = FrameBounds(100, 150)
    assert bounds.clamp(99) == 100
    assert bounds.clamp(151) == 150
    assert bounds.advance(150, +1) == 150
    assert bounds.advance(100, -1) == 100
    assert bounds.allows(120)
    assert not bounds.allows(151)
    with pytest.raises(ValueError, match="Invalid frame limits"):
        FrameBounds(20, 10)


class FakeCV2:
    CAP_PROP_POS_FRAMES = 1


class FakeCapture:
    def __init__(self, count=10, *, drift=0):
        self.frames = list(range(1, count+1))
        self.next = 0
        self.drift = drift
        self.seeks = []

    def set(self, _key, value):
        self.next = int(value)
        self.seeks.append(self.next)
        return True

    def read(self):
        if 0 <= self.next < len(self.frames):
            value = self.frames[self.next]
            self.next += 1
            return True, value
        return False, None

    def get(self, _key):
        return self.next + self.drift


def test_exact_frame_seek_is_1_based_and_playback_sequential():
    cap = FakeCapture()
    assert read_exact_frame(cap, 4, FakeCV2) == 4
    assert cap.seeks == [3]
    assert read_sequential_frame(cap, 5, FakeCV2) == 5
    assert read_exact_frame(cap, 2, FakeCV2) == 2


def test_inexact_decoder_fails_closed_instead_of_showing_wrong_frame():
    bad = FakeCapture(drift=5)
    with pytest.raises(ValueError, match="Decoder frame mismatch"):
        read_exact_frame(bad, 4, FakeCV2)
    bad = FakeCapture(drift=-4)
    read_exact_frame(FakeCapture(), 1, FakeCV2)
    bad.next = 4
    with pytest.raises(ValueError, match="Sequential decoder frame mismatch"):
        read_sequential_frame(bad, 5, FakeCV2)


def test_out_of_range_video_fails_and_cannot_show_unrequested_frame():
    cap = FakeCapture(count=5)
    with pytest.raises(ValueError, match="cannot read requested"):
        read_exact_frame(cap, 6, FakeCV2)


def test_invalid_video_alias_or_noninteger_case_frame_does_not_initialize(tmp_path):
    path = tmp_path/"assign.csv"
    broken = _row()
    broken["start_frame"] = "5.0"
    _write(path, [broken])
    with pytest.raises(ValueError, match="Invalid frame"):
        ReviewSession(path, tmp_path/"completed.csv")
