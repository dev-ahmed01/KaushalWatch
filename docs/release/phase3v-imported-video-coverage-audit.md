# Phase 3V — Imported video evidence audit and incomplete coverage

**RESEARCH ONLY.** Stacked after Phase3U. Do not merge into main.

## Observed from the uploaded video-enabled report

The source-pinned local Docker workstation decoded sparse video frames
from 20/40 selected normal-annotated development windows (10/20 Day3
and 10/20 Day4), totaling 240 sampled video frames. It selected all
10 three-consecutive candidate-bearing windows plus ten comparators.
The remaining 20 intervals were NOT pixel-sampled due to the original
10-window/day budget, not a demonstrated source-video mount failure.
Original report labeled these as SOURCE_VIDEO_NOT_MOUNTED; this was
misleading and must be reported as NOT_SELECTED_FOR_BOUNDED_VIDEO_SAMPLING.

Original numerical candidate counts remain Day3 13 / Day4 3 under
three consecutive samples. From the independently timed sparse AVI
feature comparison (12 sampled frames per selected window), possible
large sharpness changes occurred in four of the ten candidate-bearing
measured windows (two each day), and one of ten measured comparator
windows (Day4). **Sparse AVI features and 2-second numerical policy
series are not temporally aligned**, and these are NOT true false
positives, negatives, sensitivity, or physical tampering cases.

## Code: scripts/audit_phase3v_container_video_evidence.py

- Imports Phase3R and Phase3S numerical reports, plus workstation
  evidence-with-video.json. Requires source pins, SHA checksum of
  underlying reports, exact 40 selected window identities and original
  candidate episodes/active samples to match.
- Rejects fake physical-health or production claims, duplicate cases,
  bogus frame bounds, missing/unknown geometric evidence converted into
  supported correspondences, absurd luma ranges or self-contradictory
  sharpness descriptors.
- Outputs a numeric summary of measured vs budget-skipped windows,
  frame sample counts and exploratory sharpness-proxy discordance.
- Does NOT reopen AVIs or recompute video SHA in this auditing process.
  Original source hashing was performed by the standalone workstation.

Example local use:

```powershell
python scripts/audit_phase3v_container_video_evidence.py `
  --evidence C:\Users\Admin\Desktop\evidence-with-video.json `
  --phase3r C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3r\normal-burden-20261018-123541.json `
  --phase3s C:\Users\Admin\Desktop\KaushalWatch-live\artifacts\phase3s\pre-event-20261018-125003.json `
  --out C:\Users\Admin\Desktop\phase3v-audit.json
```

## Docker workstation companion release

A separately downloadable local-only Phase3V workstation package
contains full selected-control sampling (20 windows/day, 12 sparse
frames per control), a dedicated audit-video-report CLI, explicit
measured-vs-skipped budget statuses, improved dashboard coverage
metrics, and dedicated unit/integration tests. This draft repo PR
records the evidence verification logic; it does not itself install
the separate workstation package into the production app.

## Scientific gates

- Phase3P/3R/3S video annotations remain development-only and
  non-independent. Ordinary events do not certify physical camera
  health. Sources can match their own SHA yet lack custody proof.
- ORB/homography proxy is NOT validated physical displacement evidence.
- Not a field false-alarm estimate or a calibrated detector; no
  tuning/alert suppression/automatic camera reset/release authorized.
- A second independent held-out camera and genuine physical reference
  authentication are still required for real deployment claims.
