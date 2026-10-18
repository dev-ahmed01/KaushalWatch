# Phase 3U — Local frame-accurate blinded review viewer

## Purpose

Review the 20 Phase3T independent cases directly against the original
locally held Day3/Day4 AVI, without exposing candidate model status,
event annotations, hidden policy key, or recording/video media exports.
Two reviewers work separately with the blinded CSVs and keep their
answers independent. This is RESEARCH ONLY; not operator enforcement.

## Requirements

- Windows with a GUI Python installation (Tcl/Tk usually bundled)
- OpenCV for decoding AVI: python -m pip install opencv-python
- Only the correct reviewer worksheet reviewer_01.csv OR reviewer_02.csv
- Original video files (not uploaded to GitHub):
  C:\Users\Admin\Desktop\MEVA\video.avi
  C:\Users\Admin\Desktop\MEVA\UHCTD_Day4\video.avi

## Run

From a checkout of experiment/phase3u-local-blind-review-viewer:

    python scripts/run_phase3t_review_viewer.py

You will be asked to select the review CSV and both videos using normal
file dialogs. Or skip dialogs by specifying:

    python scripts/run_phase3t_review_viewer.py `
      --worksheet 'C:\Users\Admin\Downloads\reviewer_01.csv' `
      --day3-video 'C:\Users\Admin\Desktop\MEVA\video.avi' `
      --day4-video 'C:\Users\Admin\Desktop\MEVA\UHCTD_Day4\video.avi' `
      --reviewer-id reviewer01

The output is reviewer_01_completed_local.csv NEXT to the selected
reviewer_01.csv and is safe to reopen to continue from the same review.
Original worksheet is never overwritten; the viewer never touches the
SEALED_DO_NOT_SHARE_with_reviewers.json key. If --out is specified, it
must be a DIFFERENT local CSV path and its parent folder must exist.

## UI workflow

- Left: all case IDs; checked marker = all required observations answered.
- Middle: the matching day video at the exact chosen 1-based start frame.
  Previous/Next case, Start, End, single-frame Back/Forward, Play/Pause
  and drag-to-frame slider. Playback stops before leaving the selected
  inclusive video interval. Local video timestamps start at 00:00:00.
- Right: reviewer ID, footage availability, focus loss, illumination,
  physical movement, obstruction, image usability, confidence and
  optional notes. Answers saved upon case switch, Save or window Close.
  Partial answers are retained but are not marked complete.
- Exact frame seek is checked using OpenCV decoder position. If the
  decoder reports a mismatch, playback stops rather than silently
  displaying a potentially different frame. Codec seek correctness
  itself requires manual/source-specific verification.

## Privacy/integrity safeguards

- Runs entirely on local PC; no API/network/upload/server endpoint.
- No frame/video/image is written. In-memory RGB->PPM is displayed
  through Tk; application never saves copies of images or clips.
- No sealed prediction key loaded; invalid extra fields in reviewer
  worksheet (including model prediction columns) are rejected.
- Reviewer notes must be short and exclude identifying information.
- Excel-formula-leading notes are rejected to avoid spreadsheet formula
  injection. Blinded case/video/frame identifiers cannot be changed.
- Separate completed CSV is atomically saved; if saved CSV assignment
  identity mismatches the original worksheet, viewer refuses to run.
- The reviewer observation itself is NOT proof of deliberate tampering.
  Uncertain/unknown options remain legitimate and are never
  overwritten by an automated healthy / recovered value.

## Validation

Run: python -m pytest backend/tests/test_camera_phase3u_review_viewer.py -q

Covered: strict worksheet schema/no prediction leakage, duplicates,
invalid values, protected source, atomic resume, partial completion,
source-frame immutability, frame bounds, 1-based decoder seek,
sequential decoding and fail-closed position mismatches. Automated
tests do not substitute for a Windows GUI/codec manual acceptance test.

After completing both independent reviewer worksheets, preserve each
separately. The sealed model key must be released only AFTER answers
are independently locked, for a separate blinded disagreement analysis.
Do not compute field false-alert rates from enriched development cases.
