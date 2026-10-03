# Demonstration and Evaluation Data

## EPFL Laboratory sequence
For the first attendance benchmark, use **one camera only** from the EPFL CVLab Laboratory 6-person sequence: Camera 0 (`6p-c0.avi`). Do not implement multi-camera fusion.

Source page:
- https://www.epfl.ch/labs/cvlab/data/data-pom-index-php/

Direct Camera 0 sequence used by the downloader:
- https://documents.epfl.ch/groups/c/cv/cvlab-pom-video1/www/6p-c0.avi

EPFL describes the laboratory sequence as four synchronized cameras observing four/six people walking inside a laboratory for roughly 2.5 minutes at 25 fps. The page states the people are laboratory members and the dataset can be used for research purposes subject to its stated citation/usage terms.

### Why one camera
The intended KaushalWatch deployment is room-level CCTV compliance monitoring. Single-camera evaluation is therefore more representative and avoids unnecessary calibration, homography, multi-view fusion and cross-camera identity complexity.

### What EPFL can validate
- person-detection behavior
- physical occupancy/count error
- robustness of the camera-trust and temporal-smoothing path

### What EPFL cannot validate
- PMKVY-specific equipment classes
- AEBAS integration
- training-centre infrastructure compliance
- final compliance-case FP/FN on our full scenario

Those require the controlled mock training-centre clip.

## Controlled final demo clip
Record a fixed-camera clip with known ground truth:
- exact number of people
- known expected/reported attendance
- 3–4 large equipment classes
- one deliberately missing item
- one visible machine/activity proxy
- deliberate camera obstruction/freeze simulation

Maintain an annotation CSV alongside the local clip, but do not commit footage containing real participants unless explicit permission and repository policy allow it.
