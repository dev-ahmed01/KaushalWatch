# Contributing to KaushalWatch

KaushalWatch is being built as a narrow SIH prototype. Keep changes aligned to the locked build scope in `docs/build-scope.md`.

## Repository rules
- Never commit raw CCTV/demo videos, model weights, generated evidence, runtime databases, or evaluation output.
- Keep heavyweight/experimental vision dependencies optional.
- Every synthetic operational number must be labelled as demo/simulated in the UI or source fixture.
- Do not report accuracy until it comes from an annotated evaluation dataset.
- AI outputs are observations/evidence, not automatic penalties.
- Apparent operability must never be described as mechanical/electrical health.
- No facial recognition, biometric embeddings, or cross-camera identity tracking in this prototype.

## Branching
- `main`: stable only.
- `build/*`: integrated build work.
- `experiment/*`: isolated detector/model experiments; do not merge until benchmarked.

## Before merging
- `pytest -q backend/tests`
- `npm run build` from `web/`
- Update `STATUS.md` if a claim moves between pending / scaffolded / verified.
