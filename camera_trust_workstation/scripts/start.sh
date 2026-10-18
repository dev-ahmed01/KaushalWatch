#!/bin/sh
set -eu
: "${PHASE3R:=/inputs/phase3r.json}"
: "${PHASE3S:=/inputs/phase3s.json}"
: "${OUTPUT:=/output/evidence-full-coverage.json}"
# Never overwrite prior analysis artifact without explicit local operator action.
if [ -e "$OUTPUT" ]; then
  echo "Using existing immutable research report: $OUTPUT" >&2
else
  if [ "${ENABLE_LOCAL_AVI_ANALYSIS:-0}" = '1' ]; then
    python -m kwtrust analyze --phase3r "$PHASE3R" --phase3s "$PHASE3S" \
      --day3-video "${DAY3_VIDEO:-/videos/day3-source.avi}" --day4-video "${DAY4_VIDEO:-/videos/day4-source.avi}" \
      --max-cases-per-day "${MAX_CASES_PER_DAY:-20}" \
      --samples-per-case "${SAMPLES_PER_CASE:-12}" --phase3p /inputs/phase3p.json --out "$OUTPUT"
  else
    python -m kwtrust analyze --phase3r "$PHASE3R" --phase3s "$PHASE3S" --phase3p /inputs/phase3p.json --out "$OUTPUT"
  fi
fi
# Phase 3W: only derive scalar concordance if all original 40 controls
# were AVI measured. Missing/partial reports retain honest UNKNOWN status.
CONCORDANCE=/output/concordance-phase3w.json
if [ ! -e "$CONCORDANCE" ] && [ -f /inputs/phase3v_uploaded_video_report.json ]; then
  if python - "$OUTPUT" <<'PYTEST'
import json,sys
try:
    coverage=json.load(open(sys.argv[1]))['video_feature_coverage']
    assert coverage['selected_windows']==40
    assert coverage['measured_windows']==40
    assert coverage['unmeasured_windows']==0
    assert coverage['sampled_video_frames']==480
except (KeyError, OSError, AssertionError, ValueError, TypeError):
    sys.exit(1)
PYTEST
  then
    python -m kwtrust concordance --full-report "$OUTPUT" \
      --previous-report /inputs/phase3v_uploaded_video_report.json \
      --phase3r "$PHASE3R" --phase3s "$PHASE3S" --out "$CONCORDANCE"
  else
    echo 'Phase3W concordance requires 40 measured windows; not generated.' >&2
  fi
fi
# Preserve the independently derived numeric evaluation of source-labeled
# Drive clips if no videos are mounted; auto-run from pinned local Drive cache
# when the selected short MP4 source files are available.
CLIP_REPORT=/output/clip-diagnostics.json
if [ ! -e "$CLIP_REPORT" ]; then
  if python - <<'PINCHECK'
from pathlib import Path
from kwtrust.drive_sync import load_manifest,sha256_file
items=[x for x in load_manifest(Path('/inputs/drive-sources.json')) if x.get('group')=='clips']
if len(items)!=14 or not all((Path('/research_clips')/x['name']).is_file() for x in items):
    raise SystemExit(1)
if not all(sha256_file(Path('/research_clips')/x['name'])==x['sha256'] for x in items):
    raise SystemExit(1)
PINCHECK
  then
    python -m kwtrust clip-evaluate --manifest /inputs/selected_clips.csv \
      --clip-dir /research_clips --out "$CLIP_REPORT"
  else
    cp /inputs/clip-diagnostics-drive-real-development.json "$CLIP_REPORT"
  fi
fi
# Self-audit every start. A stale/concurrent derived report is refreshed
# atomically, but underlying source evidence is never overwritten. Missing
# or inconsistent source pins prevent the dashboard from starting.
python -m kwtrust.boot --phase3r "$PHASE3R" --phase3s "$PHASE3S" \
  --video-report "$OUTPUT" --former-video-report /inputs/phase3v_uploaded_video_report.json \
  --concordance "$CONCORDANCE" --clip-report "$CLIP_REPORT" \
  --drive-manifest /inputs/drive-sources.json \
  --clip-manifest /inputs/selected_clips.csv \
  --acceptance-report /output/product-readiness.json \
  --external-scene-report /output/external-scene-probe.json
# Container binds a port; caller MUST bind published port to HOST 127.0.0.1.
exec python -m uvicorn "kwtrust.container_app:app" --host 0.0.0.0 --port 8765 --no-access-log
