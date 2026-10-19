# Phase 6 — SIH judge-day runbook and source freeze

## What we are presenting

KaushalWatch remains a clean four-module officer workbench: KaushalAI, Centres, Insights and Actions. A centre reports; cameras and independent evidence narrow what can be concluded; a human officer decides. The prepared scenario numbers and cases are visibly SIMULATED. Bundled replay media are PROCEDURALLY GENERATED, not actual government-centre CCTV. Live detector accuracy, sanctioned stock quantities, official integrations, biometric identity, grant suspension and field certification are never claimed.

This stage integrates earlier Phases 3C, 4 and 5 from PRs #111–113 rather than rebuilding their object-detection evaluator, safe edge queue or protected case review/PDF services.

## Windows launch

From the repository root after installing the Python requirements and Next dependencies (run npm ci in web), use normal Windows PowerShell:

~~~powershell
# Read-only checks: no mutable data reset and no services launched
.\scripts\Start-KaushalWatch-Judge.ps1 -PreflightOnly

# ONLY in the prepared, demo-only workspace:
.\scripts\Start-KaushalWatch-Judge.ps1 -ResetSimulatedState

# Later restart without replacing officer/audit state:
.\scripts\Start-KaushalWatch-Judge.ps1
~~~

The command refuses protected/pilot/production environment settings, PostgreSQL or S3. It checks the shipped replay source hashes, deterministic seed, local Python/npm and local-only server settings. It starts real API (localhost port 8000) and Next (localhost port 3000), and writes temporary logs outside the repo. The default controlled path shows synthetic API case records without claiming real detector inference. Use -CalibratedModel only when the existing authoritative OpenVINO runtime is actually installed; otherwise the strict startup refuses it.

An explicit -ResetSimulatedState runs scripts/judge_reset_guard.py BEFORE any cleanup. The guard rejects non-simulated cases/history, unindexed or tampered evidence, unknown centre settings, non-simulated edge receipts and unexpected symlinks. Never run the reset on actual institution data. It does not delete raw clips or approved source manifests.

Open the launcher's localhost /demo/mission. Its built-in Judge route rail has two human-operated paths. The displayed time ranges are planned speaking targets, NOT wall-clock measurements, automated inference or a true elapsed clock.

## Full judge demonstration (3 minutes 20 seconds)

| Planned window | Demonstrate | Evidence boundary |
| --- | --- | --- |
| 00:00–00:40 | Attendance gap | Illustrative 28 reported vs 19 observed; a single frame never establishes wrongdoing |
| 00:40–01:15 | Camera obstruction | Unknown count withheld, never interpreted as zero trainees |
| 01:15–01:55 | Item-specific infrastructure | Job-role matrix shows visibility and uncertainty; no sanctioned shortage or mechanical-health claim |
| 01:55–02:40 | Saved officer evidence → review → audit → PDF | The saved seeded case is SIMULATED and not derived from procedural replay; officer review changes only the local demo |
| 02:40–02:58 | Normal negative control | Avoid inventing an alert when none is supported |
| 02:58–03:20 | Offline and accuracy limits | Phase 4 actual localhost request-body bytes only if private receipt loaded; Insights scorecard preserves NOT QUALIFIED |

A click on each chapter selects its appropriate existing scenario. Keyboard focus stays on native buttons, the route does not automatically alter case decisions, and all presented model numbers remain subject to the saved provenance boundary.

## One-minute rapid path

| Planned window | Point |
| --- | --- |
| 00:00–00:15 | Attendance: reported/illustrative observed difference |
| 00:15–00:29 | Camera: no count after obstruction |
| 00:29–00:43 | Equipment: item types and uncertainty |
| 00:43–01:00 | Normal negative control plus offline byte proof if available |

The rail offers Next cue, Restart, and direct chapter jumps. It does not create a fifth application module.

## Immutable procedural video verification

~~~powershell
python scripts/verify_judge_sources.py --out "C:\Private\KaushalWatch\phase6-source-lock.json"
python scripts/check_release_readiness.py
python scripts/rehearse_offline_transport.py --out "C:\Private\KaushalWatch\phase4-offline.json"
~~~

The source-lock verifier SHA-256 checks precisely three checked-in MP4 files (east-corridor, training-bay, workshop-floor) against the versioned public camera-trust manifest. Tampering, symlinks and provenance changes fail. The report contains hashes/byte sizes, qualified=false, and no raw paths; it refuses overwriting an existing receipt. It does not certify any actual training centre.

The last command measures actual localhost HTTP-body bytes, durable queue restart and deduplicated replay after a lost acknowledgement. It excludes TLS/TCP header overhead and does not measure remote network throughput. The six-pillar scorecard continues to block missing independent attendance, camera, equipment and practical-work accuracy.

## Company-style release acceptance

All seven CI jobs must pass on the exact PR SHA: hygiene, backend, PostgreSQL persistence, frontend build, protected-browser, OIDC-browser acceptance and Playwright full E2E; the release-container workflow must also pass. Merge only that tested SHA, and verify post-merge main CI and containers again. Automated checks also test the Windows PowerShell read-only preflight, SHA-pinned sources, forbidden reset on real/unindexed/tampered records, 60s/200s chapter continuity, mobile viewport and keyboard focus.

Before recording judges' screen footage, use the Windows workstation to launch and visually rehearse both routes. CI cannot verify its actual GPU, local model weights, authorized institutional footage or spoken presentation duration. Outstanding pilot and field approval remains issue #91. Independent electrician-room box labels and human provenance in #103 remain separately blocked. Do not merge unrelated experimental Camera Trust branches as a shortcut.
