# Phase 11 — Source-matched numeric Camera Trust replay (local-only)

The existing private 4-clip MEVA/UHCTD replay shows recorded frames and a research annotator's supplied event windows. It previously had NO separately computed video evidence trace in the player. Phase 11 adds the actual Camera Trust numerical heuristic outputs to that SAME private viewer, never a new top-level module or uploaded media pipeline.

## Generate local evidence-quality samples

Requires a separately downloaded/extracted private Phase 9 replay kit, stored OUTSIDE the repository, and backend Python dependencies including OpenCV. The private folder must contain:
- the four Day 3 source MP4 clips;
- selected_clips.csv;
- kw-research-replay.local.json produced by scripts/prepare_research_replay.py from the earlier source approval step.

Run once on the private workstation:

~~~powershell
python scripts/prepare_research_triage_trace.py --clip-dir "C:\PrivateResearch\KaushalWatch_Phase9_Private_Replay_Kit\private-cache"
~~~

This script refuses to proceed if the current video bytes or annotation sheet disagree with the already-frozen local replay catalog. It refuses symlinks, directory traversal into the source checkout, unsupported protected runtime modes or invalid decoder metadata.

It decodes each clip at 3 FPS, samples once per second, and runs the existing backend/app/services/camera_quality.py sample function against an UNVERIFIED first video frame. Its output, kw-research-analysis.local.json, is exclusively created in the same private folder with restrictive file permissions. It contains four source-matched SHA-256 digests, numeric-quality category observations, labelled research event intervals and limited frame timestamps; no original video pixels, still images, faces, addresses or security tokens.

Set local development mode and KAUSHALWATCH_LOCAL_RESEARCH_REPLAY=true with KAUSHALWATCH_RESEARCH_REPLAY_DIR pointing to the private directory as already described in docs/demo/CONTROLLED_DRIVE_RESEARCH_REPLAY.md. Refresh /demo/mission.

## How to read the UI

Three distinct layers stay separate:

1. Recorded MP4 video at its actual playback timestamp.
2. Preexisting UHCTD Day 3 annotation of the intervention time window.
3. Source-verified computed numeric heuristic observations: evidence usability and possible scene interference, sampled at 1 FPS.

The numeric trace card appears only after the server verifies the SHA-matched source and the complete temporal trace. A missing or invalid report shows only original annotations; it never invents a predicted value.

The private read-only endpoint is /api/demo/research-replay/analysis. It uses the SAME development-only localhost and request-origin restrictions as the video route, verifies all four source digests, validates every source-frame index, source timestamp, annotation boundary, enumeration and summary count, and strips original filenames and media before replying. It returns 404 in protected mode and 503 for invalid private evidence. It has private no-store response headers.

The trace uses an UNVERIFIED first-frame reference. It demonstrates a genuine local image-processing computation but NOT physical camera freshness, independent annotation accuracy, real ITI footage, camera interference intent, held-out model accuracy or permission for deployment. There is no live input, enforcement or official integration.

## Tests and boundaries

Backend regression tests build private synthetic MP4 files and freeze a matching local annotation catalog. They verify real OpenCV execution, no real-source requirements, source hash drift rejection, annotated-interval drift rejection and protected-mode refusal. Node regression tests verify signed-off server input consistency (SHA, frame ordering, 1 FPS timing, event labels and counts). Browser E2E verifies the new cue panel aligns with the user-selected clip and the separate annotation layer.

No research video, people identities, private media directory or trace data is committed to GitHub. The four-module application shell remains unchanged. No new accuracy numbers are claimed and institutional acceptance Issue #91 remains open.
