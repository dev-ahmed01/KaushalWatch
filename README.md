# KaushalWatch

**Trusted Visual Compliance for PMKVY Training Centres — SIH26245 prototype**

KaushalWatch reconciles three things:

1. what a training centre reports (simulated AEBAS/SIDH in the prototype),
2. what the selected job-role compliance manifest says the centre should have, and
3. what privacy-preserving camera analytics can physically verify.

Persistent exceptions become evidence-backed compliance cases for human review.

> **Verification notice:** For the exact verified / scaffold-only / pending state of every component, see [`STATUS.md`](STATUS.md). This README describes the intended integrated prototype and does not override the verification caveats in that file.
>
> **Prototype data notice:** sample national/state/centre operational numbers and scheme records in this repository are simulated unless explicitly sourced. Do not present them as live MSDE statistics.

## Current implementation

- FastAPI backend — **implemented; validation tracked in STATUS**.
- CCTV/video upload endpoint — **implemented**.
- OpenCV HOG person-detection baseline — **baseline only; not the final SIH detector**.
- Median occupancy smoothing and reported-vs-observed discrepancy logic — **implemented**.
- Temporal persistence gate before creating a case — **implemented**.
- Camera trust checks for darkness, blur, frozen frames and viewpoint shift — **implemented**.
- Evidence image persistence with SHA-256 — **implemented**.
- Perceptual duplicate-evidence fingerprinting — **implemented; end-to-end duplicate alert workflow still needs demo validation**.
- Human review status workflow — **implemented**.
- Apparent-operability ROI motion proxy — **implemented as a visual activity proxy only; not a mechanical diagnosis**.
- Cached equipment-detection adapter — **implemented so GroundingDINO cannot block the core demo; live GroundingDINO remains a separate validation task**.
- Executable demo compliance manifest — **implemented with explicitly synthetic quantities**.
- Evaluation script — **implemented; example inputs are synthetic until replaced with annotated footage**.
- Privacy-preserving design note — **written**.
- Next.js monitoring UI scaffold — **source present; build/runtime verification is a named milestone in STATUS**.

## Core demo path

```text
single-camera video
  -> camera trust
  -> anonymous person detection
  -> stable physical occupancy
  -> simulated AEBAS comparison
  -> temporal persistence
  -> one compliance case
  -> minimal evidence
  -> officer review
```

Equipment presence, apparent operability and evidence-authenticity checks plug into the same case workflow rather than becoming separate demos.

## Run the backend

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open API docs at `http://localhost:8000/docs`.

## Run the web UI

```bash
cd web
npm install
npm run dev
```

The UI expects the API at `http://localhost:8000` by default.

## Evaluation

Copy `evaluation/annotations.example.csv` and replace the rows with real ground truth.

```bash
python evaluation/evaluate.py --input evaluation/annotations.csv --out-dir evaluation/output
```

Use only measured values in the SIH deck. Do **not** invent accuracy numbers.

## Privacy

Read [`docs/privacy-design.md`](docs/privacy-design.md). Core prototype rule: **track position, not identity**. No current compliance check in the prototype requires individual identification.
