# Architecture and Repository Boundaries

## Design principle
The core product must remain demoable even when optional AI components fail. The attendance/case workflow therefore depends only on the core backend. Equipment and detector experiments are adapters.

## Top-level layout
```text
backend/      API, case engine, camera trust, evidence and core CV interfaces
web/          monitoring command-centre UI
configs/      executable demo compliance manifests
evaluation/   offline benchmark scripts + example annotation schemas
scripts/      model/dataset acquisition utilities (no binary assets committed)
demo/         tiny text/JSON demo fixtures only
docs/         scope, privacy and architecture
models/       runtime-only, gitignored
data/         runtime evidence/cases/raw video, mostly gitignored
```

## Dependency boundary
```text
Core API
  ├── OpenCV baseline detector (always available)
  └── Detector interface
        └── OpenVINO person detector (optional requirements)

Infrastructure
  └── EquipmentDetector interface
        ├── CachedEquipmentDetector (stage-safe)
        └── GroundingDINO adapter (experimental)
```

Heavy models must never become import-time dependencies of `app.main`.

## Data boundary
Source code/configuration may be committed. Raw video, downloaded model binaries, generated evidence, runtime DB/state and benchmark outputs must remain outside git.

## Truthfulness boundary
`STATUS.md` is the verification source of truth. README/UI may describe intended behavior but must not upgrade an unverified feature to a verified claim.
