# KaushalWatch Camera Trust — Unified product acceptance

**18 October 2026 · acceptance contract v1**

## Delivery contract

The system is a complete **read-only Camera Trust research workstation**, with a local HTML dashboard, FastAPI, Docker Compose, source-pinned numerical findings, 14 independently retrieved Google Drive file hashes, safe resumable Drive ingest code, source checks and a startup acceptance receipt. It runs without ChatGPT, manual reports, recurring uploads, or operator review to generate and examine its *numerical* findings.

The `product-readiness` acceptance gate is derived from the unmodified source JSON on **every startup**. A mismatch blocks startup. This only refreshes a derived acceptance JSON and derived signal comparison; it never modifies raw video, source annotations, evidence reports, operator incidents, reference enrollment or production alarm thresholds.

## Verification receipt

| Contract | Result |
| --- | --- |
| Existing selected normal-labeled windows | 40/40 |
| Existing sparse AVI measurements | 480 across those 40 windows |
| Three-consecutive numerical warning starts | 16 (Day3 13, Day4 3) |
| Source-pinned labeled short clips | 14 of 14 SHA-256 matches |
| Real clip frames with numerical samples | 618 |
| Candidate event-sample observations vs development annotation | 198 of 402 |
| Other-sample candidate observations | 6 of 216 |
| Source clip rerun independently repeated in the container | Exact numeric JSON match |
| Additional unlabeled Drive recordings | 4 original AVIs decoded |
| New sparse external recording samples | 241 fixed-time positions, no physical ground-truth labels |
| Automated local tests | 74 passed |
| Physical camera detection validated independently | **No** |
| Operational warnings or automatic recovery enabled | **No** |

These per-sample descriptive counts are not statistically independent. The clips came from the same developmental source. There is no measured field false-alarm/hour or externally validated movement sensitivity.

## Repository layout

- `kwtrust/` — numerical evidence, clip extraction, Drive ingestion, diagnostics, acceptance, API.
- `example_data/` — previously generated source-pinned numeric research reports and read-only existing development manifests.
- `out/` — existing frozen research outputs plus automatically refreshed **derived** acceptance receipt.
- `drive-sources.json` — only approved Drive file IDs, sizes and SHA-256, not OAuth credentials.
- `local_drive_sources/` — optional private cached recordings and clips. Not packaged or committed.
- `scripts/` — local startup / safe Google Drive file sync.
- `tests/` — immutable evidence accounting, Drive transfer hardening, API and startup contracts.

## Operate without a chat loop

Launch the project via `Start-Workstation.ps1` with Docker Desktop. The dashboard runs on `http://127.0.0.1:8767`; no additional JSON uploads to ChatGPT are needed. The server reads previously computed pinned evidence. The app verifies source continuity and publishes `/api/product-readiness` at every start. To use a new full recording, the direct Drive client can download approved files to the workstation using OAuth/ADC in that environment; this requires one-time authorization not transferrable from ChatGPT's connector. The app does not autonomously deploy or operate CCTV devices.

## What is not physically provable from these files

An independently verified field detector cannot be finished solely by adding code or rerunning existing data. The provided evidence contains synthetic annotated classes and self-referenced image samples; true healthy-camera labels, physical camera reference authentication, real held-out cameras and operator-reviewed incident outcomes were not provided. Therefore the production gate must remain **BLOCKED**. The workstation is finished; claiming the physical tamper detector is field validated would be false.

## Testing

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m kwtrust product-readiness --phase3r example_data/phase3r.json --phase3s example_data/phase3s.json --report out/evidence-full-coverage.json --concordance out/concordance-phase3w.json --clips out/clip-diagnostics.json --drive-manifest drive-sources.json --clip-manifest example_data/selected_clips.csv --out out/product-readiness.json
```

The source archive contains no original MP4/AVI, frames, OAuth keys or `.env` secrets. Google Drive file IDs are included only in the **private distributable**; a public GitHub mirror must omit those IDs and the source-dependent numeric reports.
