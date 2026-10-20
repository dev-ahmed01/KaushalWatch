# Phase 9 — private, source-pinned Camera Trust baseline audit

Follows the recorded source shortlist in the owner's connected Kaushal Google Drive. UHCTD Day 3 is already-inspected development footage, NOT authorized ITI electrician workshop CCTV, not untouched held-out data and not approved for public release. Do not commit actual video files, screenshots, private manifest or reports into Git.

The product ALREADY supports a private localhost research replay at /demo/mission via scripts/prepare_research_replay.py. This phase does not create a new frontend module or any footage upload loop. Instead it measures what the checked-out basic assess_camera scorer currently does on that source.

## One workstation audit

Extract the Phase 9 private replay kit OUTSIDE the Git checkout. The local private-source-manifest.json must have schema KW_PRIVATE_FOOTAGE_SELECTION_V1, independent_holdout false, training_centre_recording false and public_distribution_authorized false, with a SHA-256 pin for every required Day 3 clip. It uses six known clip names: covered gentle onset, covered strong onset, defocused strong onset, moved gentle onset and two normal controls.

On the development workstation, with backend requirements installed:

~~~powershell
python scripts/audit_private_camera_clips.py --clip-dir "C:\PrivateResearch\KaushalWatch_Phase9_Private_Replay_Kit\private-cache" --output "C:\PrivateResearch\baseline-evidence-audit.json"
~~~

The audit checks exact source hashes, bounds, MP4 signature, non-symlink private path, 3 FPS and expected frame counts. It executes the actual current backend/app/services/camera_trust.py assess_camera with its DEFAULT scoring settings at 1 FPS, using an unverified first-frame reference per clip. Labels come from already-recorded Day 3 annotations, not the model.

The report is created once with 0600 file permissions and is forbidden inside Git. Only numeric counts, source hashes and research labels are written; no raw video, frames, people, private source paths, camera credentials or API calls. Staging, pilot and production modes are rejected. Exit 0 means an observed development audit was produced, NOT that camera accuracy is qualified.

## Private audition on 20 October 2026

With original baseline camera_trust.py Git blob SHA a531ae0eab543e57dbcf183230485bb72efb2f33, using six selected video excerpts (four annotated onsets, two normal controls), the counted results were:

| Development-only observation | Samples | Evidence-untrusted samples |
| --- | ---: | ---: |
| Four annotated onset intervals | 144 | 60 |
| Two normal controls and four pre-event windows | 120 | 35 |
| Strong defocus event | 36 | 4 |
| Gentle movement event | 36 | 2 |
| Normal control #2 | 36 | 33 |

These are NOT camera-tamper precision, general sensitivity, false alarms per real camera-hour, or live officer decisions. Visual quality warnings can coexist with the baseline trusted flag; each scoring penalty must cross the final cutoff, and scene-shift may fire on natural normal changes. No model tuning is performed against these already-inspected excerpts.

## Tests and next acceptance

Synthetic-data CI checks source drift, symlinks, private-only usage, incorrect field-qualification flags, exclusive report creation and real OpenCV video decode using generated pixels. Original camera media and private annotations stay out of the source tree.

Next scientific step: approved genuinely unseen real workshop/camera sources, independent blinded labels, continuous streaming normal-hour burden, onset-local detection and latency, plus a frozen evaluation policy. Report evidence usability separately from suspicion of tampering. Keep institutional deployment Issue #91 open until approval.
