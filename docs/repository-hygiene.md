# Repository Hygiene

KaushalWatch keeps source/control-plane material in Git and keeps runtime/demo payloads out of Git.

## Never commit

- CCTV or controlled-demo video files
- downloaded model weights / OpenVINO IR binaries
- generated evidence frames
- runtime case/edge queue state
- reviewed GroundingDINO caches produced from the final video
- final annotation files containing demonstration ground truth
- generated evaluation outputs

These assets belong under the gitignored local paths documented by the project.

## CI enforcement

`python scripts/check_repo_hygiene.py` inspects **tracked** files and fails when it finds:

- common video/model binary extensions,
- runtime/generated data directories,
- OpenVINO model XMLs under `models/`,
- or an unexpectedly large tracked file.

This is intentionally stricter than `.gitignore`: a file accidentally force-added with `git add -f` will still fail CI.

## Allowed examples

Small source fixtures, JSON schemas/example caches and annotation *templates* may be committed when they are clearly labelled simulated/example and contain no real participant media.
