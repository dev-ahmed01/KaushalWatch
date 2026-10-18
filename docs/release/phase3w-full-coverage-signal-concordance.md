# Phase 3W — Complete selected-control AVI feature comparison

**Research-only, stacked on draft Phase3V (#77), never production main.**

The user's uploaded `evidence-full-coverage.json` reports all 40 preselected normal-annotated controls (20/day) with 12 sampled AVI source frames per window: **480 sparse frames**, two hours of *selected* normal-labeled exposure. The earlier report sampled 20 controls. Exact scalar measurements from those earlier 20 controls were reproduced.

The existing 3-consecutive-sample numerical quality candidate is compared *descriptively* against a previously inspected exploratory sparse video Laplacian ratio below 0.5. These two evidence streams use different sampling cadences; no temporal correspondence or camera physical provenance is established.

| Comparison on preselected windows | Day3 | Day4 | Combined |
| --- | ---: | ---: | ---: |
| Candidate and sparse sharpness change | 2 | 2 | 4 |
| Candidate without sparse sharpness change | 6 | 0 | 6 |
| No candidate with sparse sharpness change | 0 | 1 | 1 |
| Neither research cue | 12 | 17 | 29 |

The experimental geometry proxy is **unsupported** for 21/40 controls (233 of 440 inter-sample comparisons unknown). The two largest computed normalized center-displacement proxies are in Day3 controls **without** persistent candidates: frames 34012–34551 (0.55167) and 75310–75849 (0.276472). This cannot establish physical displacement; feature-matching errors, foreground motion and low texture remain live alternatives.

## Code and guarantees

`scripts/analyze_phase3w_full_coverage_concordance.py` builds a 4-way numerical matrix only **after** running the existing strict Phase3V source/report audit. It refuses missing controls, incorrect window denominators, corrupted numeric candidate counts, contradictory SHA pins, false coverage or unknown geometric comparisons mislabeled as supported. Optionally checks that prior scalar AVI records were reproduced exactly. Exports JSON numbers and frame-index intervals only, no images/media.

`backend/tests/test_camera_phase3w_concordance.py` uses synthetic numerical cases for 40-control completeness, source corruption and nonoperational evidence contracts. Separate container workstation package includes the full dashboard comparison and passing local integration tests; it is not deployed to the production app.

## Scientific limits

- 480 sparse frames are not complete video replay. 2-hour selected exposure is not representative camera uptime.
- Normal annotations are not authenticated physical camera health. No blinded independent holdout.
- Geometric proxy is not displacement truth; unavailable proxy is not stationary/healthy.
- Do not fit a new threshold on repeatedly inspected development footage; do not calculate field detection performance from these controls.
- No warning, incident recovery, physical reference or operational enforcement changes.

**Do not merge this draft research stack into production main.**