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
- OpenCV HOG person-detection fallback — **development/CI only**.
- OpenVINO person-detection-retail-0013 — **selected SIH attendance detector after EPFL benchmark**.
- Median occupancy smoothing and reported-vs-observed discrepancy logic — **implemented**.
- Temporal persistence gate before creating a case — **implemented**.
- Camera trust checks for darkness, blur, frozen frames and viewpoint shift — **implemented**.
- Evidence image persistence with SHA-256 — **implemented**.
- Perceptual duplicate-evidence fingerprinting — **implemented and integration-tested with identical evidence**.
- Human review status workflow — **implemented**.
- Apparent-operability ROI motion proxy — **implemented as a visual activity proxy only; not a mechanical diagnosis**.
- Cached equipment-detection adapter — **implemented as the stage-safe fallback**.
- GroundingDINO offline precompute path — **isolated smoke inference verified; final-video equipment accuracy still pending**.
- Executable Construction Electrician - LV (CON/Q0603) demo manifest — **implemented; job-role identity sourced, quantities explicitly simulated**.
- Final-demo evaluation scripts — **implemented and CI-smoke-tested; example inputs remain synthetic until replaced with annotations of the exact final clip**.
- Privacy-preserving design note — **written and reflected in code; retained attendance/infrastructure evidence anonymizes detected person regions**.
- Next.js monitoring command centre — **production build and browser E2E verified in GitHub Actions**.
- Offline edge runtime — **locally processes video, queues sanitized compliance telemetry, and syncs JSON events without raw-video upload; dashboard visibility is browser-E2E verified**.

Kaushal Assistant is also implemented as a single tool-grounded agent with multi-turn text chat
and end-to-end browser voice interaction. Its API and browser contracts are automated-test verified.

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

Equipment presence, Temporal Proof, apparent operability, evidence authenticity, camera integrity and officer audit history all plug into the same persisted case workflow rather than becoming separate demos.

## Verified attendance benchmark

On EPFL Laboratory Camera 0 (113 labelled frames, IoU 0.5), the selected OpenVINO detector achieved **91.45% precision, 89.95% recall, 90.69% F1 and 0.327-person occupancy MAE**. See [`docs/benchmarks.md`](docs/benchmarks.md) for methodology and limits.

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

## Kaushal Assistant

Kaushal Assistant uses one OpenAI Agents SDK agent. Operational answers are grounded through
deterministic tools that read the existing analysis history, case/evidence store, centre state,
escalation policy and runtime-readiness service directly. It does not call this FastAPI application
through HTTP from inside the backend and does not synthesize missing KaushalWatch records.

Copy the example environment and add a backend-only OpenAI API key:

```powershell
Copy-Item .env.example .env
# Edit .env and set OPENAI_API_KEY. Do not use a NEXT_PUBLIC_ variable for this secret.
cd backend
python -m uvicorn app.main:app --env-file ..\.env --reload --port 8000
```

In another terminal:

```powershell
cd web
npm install
npm run dev
```

Open `http://localhost:3000/centres/DEMO-KA-104`. Typed questions stay silent by default and
provide a speaker control. Voice questions use the browser microphone, upload the recording for
transcription, send that transcript through the same agent, generate an AI voice response and play
it in the browser. Microphone access works on localhost or another secure browser origin.

If `OPENAI_API_KEY` is missing or `KAUSHAL_AI_ENABLED=false`, the panel shows that setup is
required while the monitoring, analysis and review features continue normally. Conversation memory
is intentionally bounded and process-local for V1, so sessions reset when the API restarts and are
not shared between multiple API workers. `KAUSHAL_AI_TIMEOUT_SECONDS` bounds each provider request
and defaults to 60 seconds.

Assistant endpoints:

- `GET /api/assistant/status` reports enabled/configured availability without exposing secrets.
- `POST /api/assistant/chat` runs grounded text chat and returns session, source and tool metadata.
- `POST /api/assistant/transcribe` accepts a supported multipart audio upload and returns text.
- `POST /api/assistant/speech` converts assistant text to MP3 audio.

## Evaluation

Copy `evaluation/annotations.example.csv` and replace the rows with real ground truth.

```bash
python evaluation/evaluate.py --input evaluation/annotations.csv --out-dir evaluation/output
```

Use only measured values in the SIH deck. Do **not** invent accuracy numbers.

## Privacy

Read [`docs/privacy-design.md`](docs/privacy-design.md). Core prototype rule: **track position, not identity**. No current compliance check in the prototype requires individual identification.


## SIH demo vision profile

Prepare the benchmarked OpenVINO detector in the same Python environment used by the API:

```bash
python scripts/prepare_demo_vision.py --install
```

That command installs the vision runtime when requested, downloads the checksum-verified
`person-detection-retail-0013` model when needed, and verifies both model files. In
`KAUSHALWATCH_PERSON_DETECTOR=auto` mode, KaushalWatch now prefers that local benchmarked
OpenVINO model automatically. You no longer need to rely on the process working directory
for the model path.

For an explicit deployment, copy the values from `backend/.env.demo.example`. HOG remains
available as a zero-download development/CI fallback, but it is non-authoritative and never
produces a final compliance conclusion.

### Attendance recall calibration

For a fixed-camera clip with a manually verified physical headcount, compare conservative
OpenVINO confidence thresholds and the optional 2x2 overlapping tiled pass:

```bash
python scripts/calibrate_attendance_detector.py \
  --video path/to/clip.mp4 \
  --true-count 5
```

The generic runtime keeps tiled inference **off by default**. The frozen SIH demo profile uses
OpenVINO confidence 0.45 with overlapping tiled inference, confirmed-track occupancy and a
3-sample median. It returns 5/5 with 0% discrepancy on the controlled calibration clip and,
on a separate dynamic held-out clip, reduced smoothed-count MAE from 1.5556 to 0.6667 while
improving exact-count rate from 22.22% to 55.56%. See `docs/attendance-calibration.md`.

These are demo-profile results on two fixed-camera clips, not a new general benchmark. The
EPFL benchmark remains the detector precision/recall benchmark.

To start the backend with the frozen target-clip demo profile after preparing OpenVINO:

```bash
python scripts/start_demo_backend.py
```

That launcher forces the selected OpenVINO confidence/tiled settings and fails closed if the
authoritative OpenVINO runtime is unavailable.


## Low-bandwidth / offline mode

```bash
python edge/agent.py analyze \
  --video data/raw/final-demo.avi \
  --reported-attendance 12

python edge/agent.py status

# after connectivity returns
python edge/agent.py sync --url http://127.0.0.1:8000
```

The edge queue contains compact compliance telemetry and evidence integrity hashes, not raw video or biometric identity data. See [`edge/README.md`](edge/README.md).
