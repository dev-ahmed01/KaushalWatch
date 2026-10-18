"""Phase 3U local blind camera-review viewer core: stdlib-only, no media I/O.

Exact frame bounds, worksheet integrity, safe atomic autosave, and completed
status. Deliberately cannot load sealed model metadata, event labels or
quality policy scores. GUI and local video decoding live in separate module.
"""
from __future__ import annotations

import csv
import math
import os
from pathlib import Path
import re
import tempfile

from prepare_phase3t_blinded_reviews import FIELDS

CASE_KEY = ("case_id", "video_alias", "start_frame", "end_frame")
CASE_RE = re.compile(r"^KWT3T-[0-9]{3,5}$")
ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
CHOICES = {
    "footage_available_yes_no_unknown": ("", "yes", "no", "unknown"),
    "visible_focus_loss_yes_no_uncertain": ("", "yes", "no", "uncertain"),
    "lighting_transition_yes_no_uncertain": ("", "yes", "no", "uncertain"),
    "physical_camera_displacement_yes_no_uncertain": ("", "yes", "no", "uncertain"),
    "foreground_occlusion_yes_no_uncertain": ("", "yes", "no", "uncertain"),
    "image_usable_for_human_observation_yes_no_uncertain": ("", "yes", "no", "uncertain"),
    "reviewer_confidence_low_medium_high": ("", "low", "medium", "high"),
}
REVIEW_COLUMNS = tuple(CHOICES)
NOTES = "short_observation_notes_without_person_identifiers"
MAX_NOTES_LENGTH = 500


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _valid_row(row: dict, position: int) -> dict:
    _require(set(row) == set(FIELDS) and
             all(isinstance(row[k], str) for k in FIELDS),
             f"Unexpected worksheet schema at row {position}")
    row = {key: row[key] for key in FIELDS}
    _require(bool(CASE_RE.fullmatch(row["case_id"])),
             f"Invalid case ID at row {position}")
    _require(row["video_alias"] in ("DAY3", "DAY4"),
             f"Unknown video alias at row {position}")
    for key in ("start_frame", "end_frame"):
        _require(row[key].isdigit() and
                 len(row[key]) <= 12 and int(row[key]) > 0,
                 f"Invalid frame number at row {position}")
    _require(int(row["start_frame"]) <= int(row["end_frame"]),
             f"Reversed frame bounds at row {position}")
    reviewer_id = row["reviewer_id"]
    _require(not reviewer_id or bool(ID_RE.fullmatch(reviewer_id)),
             f"Invalid reviewer ID at row {position}")
    for key, allowed in CHOICES.items():
        _require(row[key] in allowed,
                 f"Unexpected option for {key} at row {position}")
    _require(len(row[NOTES]) <= MAX_NOTES_LENGTH,
             f"Notes exceed {MAX_NOTES_LENGTH} characters at row {position}")
    # Excel formula strings must never be generated as valid spreadsheet formulas.
    _require(not row[NOTES].lstrip().startswith(("=", "+", "-", "@")),
             "Unsafe notes prefix: begin with a plain letter instead")
    return row


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream, strict=True)
        _require(reader.fieldnames is not None and
                 set(reader.fieldnames) == set(FIELDS) and
                 len(reader.fieldnames) == len(FIELDS),
                 "Only the original blinded Phase3T reviewer worksheet is accepted")
        rows = [_valid_row(row, index) for index, row in enumerate(reader, 1)]
    _require(bool(rows) and len(rows) <= 1000, "Unexpected worksheet case count")
    ids = [row["case_id"] for row in rows]
    _require(len(set(ids)) == len(ids), "Duplicate case IDs")
    return rows


class ReviewSession:
    """In-memory reviewer answers with local-only atomic progress save."""

    def __init__(self, worksheet: Path, output: Path) -> None:
        self.worksheet = Path(worksheet).resolve()
        self.output = Path(output).resolve()
        _require(self.worksheet != self.output,
                 "Never overwrite the original blinded reviewer assignment")
        _require(self.worksheet.is_file(), "Reviewer assignment CSV not found")
        _require(self.output.parent.exists(),
                 "Completed worksheet destination directory does not exist")
        self.assigned = _read_csv(self.worksheet)
        self.rows = [dict(row) for row in self.assigned]
        if self.output.exists():
            saved = _read_csv(self.output)
            _require(len(saved) == len(self.rows),
                     "Saved worksheet does not match assigned case count")
            for original, previous in zip(self.rows, saved):
                _require(
                    all(original[key] == previous[key] for key in CASE_KEY),
                    "Saved worksheet changes case ID, video alias or frame bounds"
                )
            self.rows = saved

    def update(self, index: int, answers: dict) -> None:
        _require(type(index) is int and 0 <= index < len(self.rows),
                 "Invalid case index")
        _require(set(answers) <= set(FIELDS) - set(CASE_KEY),
                 "Case identity and frame bounds are immutable")
        merged = {**self.rows[index], **answers}
        self.rows[index] = _valid_row(merged, index+1)

    def completed(self, index: int) -> bool:
        row = self.rows[index]
        return bool(row["reviewer_id"]) and all(
            bool(row[key]) for key in REVIEW_COLUMNS
        )

    @property
    def completed_count(self) -> int:
        return sum(self.completed(i) for i in range(len(self.rows)))

    def save(self) -> Path:
        # Atomic replacement: no partial CSV if the process is closed suddenly.
        # Keep original assignment untouched; never create video/frame exports.
        temp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", newline="", encoding="utf-8",
                dir=self.output.parent, prefix=".phase3u-review-",
                suffix=".tmp", delete=False,
            ) as stream:
                temp = Path(stream.name)
                writer = csv.DictWriter(stream, fieldnames=FIELDS,
                                        extrasaction="raise")
                writer.writeheader()
                writer.writerows(self.rows)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.output)
        finally:
            if temp is not None and temp.exists():
                temp.unlink()
        return self.output


class FrameBounds:
    """Inclusive 1-based frame boundaries for exactly one blinded case."""

    def __init__(self, start_frame: int, end_frame: int) -> None:
        _require(type(start_frame) is int and type(end_frame) is int and
                 1 <= start_frame <= end_frame, "Invalid frame limits")
        self.start = start_frame
        self.end = end_frame

    def clamp(self, number: int) -> int:
        _require(type(number) is int, "Frame index must be integer")
        return min(self.end, max(self.start, number))

    def advance(self, current: int, amount: int) -> int:
        _require(type(amount) is int, "Frame step must be integer")
        return self.clamp(current + amount)

    def allows(self, number: int) -> bool:
        return type(number) is int and self.start <= number <= self.end


def format_video_time(frame: int, fps: float) -> str:
    """Timestamp relative to video start, NOT a wall-clock timestamp."""
    _require(type(frame) is int and frame >= 1 and
             isinstance(fps, (float, int)) and
             math.isfinite(fps) and fps > 0, "Invalid frame timestamp inputs")
    sec = (frame - 1) / fps
    hour = int(sec // 3600)
    minute = int((sec % 3600) // 60)
    seconds = sec % 60
    return f"{hour:02d}:{minute:02d}:{seconds:06.3f}"


def read_exact_frame(capture, frame: int, cv2_module):
    """Seek and verify decoder POSITION after reading the requested 1-based frame.

    Source-specific codec seeking can fail; never quietly display the wrong
    frame. Returns decoded ndarray held in process memory only.
    """
    _require(type(frame) is int and frame >= 1, "Invalid requested frame")
    if not capture.set(cv2_module.CAP_PROP_POS_FRAMES, frame - 1):
        raise ValueError(f"Decoder cannot seek to frame {frame}")
    ok, image = capture.read()
    if not ok or image is None:
        raise ValueError(f"Decoder cannot read requested frame {frame}")
    position = capture.get(cv2_module.CAP_PROP_POS_FRAMES)
    if not isinstance(position, (int, float)) or not math.isfinite(position) or abs(position-frame) > 0.51:
        raise ValueError(f"Decoder frame mismatch at requested frame {frame}: {position}")
    return image


def read_sequential_frame(capture, expected_frame: int, cv2_module):
    """Advance exactly one frame after the previously verified position."""
    _require(type(expected_frame) is int and expected_frame >= 1,
             "Invalid next frame")
    ok, image = capture.read()
    if not ok or image is None:
        raise ValueError(f"Decoder stopped at frame {expected_frame}")
    position = capture.get(cv2_module.CAP_PROP_POS_FRAMES)
    if not isinstance(position, (int, float)) or not math.isfinite(position) or abs(position-expected_frame) > 0.51:
        raise ValueError(
            f"Sequential decoder frame mismatch at {expected_frame}: {position}"
        )
    return image
