# Verified Benchmarks

This document records curated, reproducible benchmark results. Generated CSV/JSON artifacts remain outside git.

## EPFL Laboratory Camera 0 — person detection

**Purpose:** choose the lightweight attendance detector for the SIH prototype.

**Dataset:** EPFL CVLab Laboratory six-person sequence, **Camera 0 only**. EPFL documents the sequence as an indoor laboratory recording with people entering and walking around, and provides ground truth for the six-person laboratory sequence.

- Official dataset page: https://www.epfl.ch/labs/cvlab/data/data-pom-index-php/
- Video used at runtime: `6p-c0.avi`
- Bounding-box annotation source used by the benchmark workflow: the EPFL-Laboratory Camera 0 annotations mirrored by `vpulab/GNN-CCA`.
- Sample interval: every 25 frames (1 second at 25 fps)
- Evaluated labelled frames: **113**
- IoU threshold for a person TP: **0.50**
- OpenVINO confidence threshold: **0.45**
- GitHub Actions benchmark run: **37132927042**
- Artifact digest: `sha256:74ef2763e81d7466e6f1f3c9e3c4e9ca4ddc061b3dbff1a7629d6d51d9c478be`

| Detector | Precision | Recall | F1 | Occupancy MAE | Max count error |
| --- | ---: | ---: | ---: | ---: | ---: |
| OpenCV HOG fallback | 43.82% | 9.11% | 15.09% | 3.000 | 6 |
| **OpenVINO person-detection-retail-0013** | **91.45%** | **89.95%** | **90.69%** | **0.327** | **2** |

### Decision
**OpenVINO person-detection-retail-0013 is the selected SIH attendance detector.** HOG remains only as a zero-download fallback for basic CI/development.

### Interpretation limits
These are person-detection/occupancy results on one public indoor surveillance sequence. They are **not** final PMKVY compliance accuracy. Final SIH claims must also include the controlled training-centre demonstration and case-level TP/FP/FN/TN.

## Browser vertical slice
GitHub Actions also verifies a real browser flow using Playwright:

`synthetic CCTV upload -> backend processing -> compliance case -> retained evidence reachable -> officer review -> cached infrastructure case`

Backend tests, Next.js production build, and browser E2E all pass on the active build branch.
