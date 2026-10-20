# Phase 7 — actual judge runtime readiness and recovery

After merged Phases 3C–6, this operational hardening closes a startup ambiguity: an alive process does not prove that the judge presentation works.

The Windows launcher now checks frozen video hashes and the deterministic synthetic seed, refuses ports occupied by old processes BEFORE optional demo reset, starts the backend and the Next.js CLI directly, and waits up to 75 seconds for actual source/API/PDF/mission responses. Startup failure stops just-launched processes, with service logs under the operating system's temporary kaushalwatch-judge directory.

## Verify a running local demonstration

~~~powershell
python scripts/check_judge_runtime.py --api-port 8000 --web-port 3000 --once
~~~

The read-only verifier checks these six REAL localhost paths:

| Path | Required response |
| --- | --- |
| /api/health | HTTP 200, service kaushalwatch-api, healthy true |
| /api/centres | Actual DEMO-KA-104 centre in the seeded API response |
| /api/cases | Saved SIM-KA-104-ATT record whose details.simulated is true |
| /api/cases/SIM-KA-104-ATT/evidence-pack | Identical saved case/centre, plus review and integrity |
| /api/centres/DEMO-KA-104/report.pdf | PDF media type and actual PDF signature |
| /demo/mission | HTTP 200 HTML with the expected KaushalWatch controlled mission |

The verifier rejects wrong backends, empty case stores, redirected logins, fake PDF placeholders, missing source relationships and stale 404 pages. It sends requests strictly to 127.0.0.1 with redirects and proxies disabled, caps the bytes read and reports fixture IDs only. It never transfers raw camera clips, credentials or officer identity.

## Windows judge workstation commands

~~~powershell
python -m pip install -r backend/requirements.txt
cd web
npm ci
cd ..

# Verify only — no mutable reset:
.\scripts\Start-KaushalWatch-Judge.ps1 -PreflightOnly

# Explicitly reseed only in a safe synthetic demo workspace:
.\scripts\Start-KaushalWatch-Judge.ps1 -ResetSimulatedState

# Recheck the actual running local services:
python scripts/check_judge_runtime.py --once

# Restart later without erasing saved local officer actions:
.\scripts\Start-KaushalWatch-Judge.ps1
~~~

If a port is occupied, stop and inspect the old application first. Do not reset a case store to fix a network/process conflict. If startup fails, inspect temporary service logs. The launcher prints immediate process IDs for stopping the controlled processes; never reuse stale PID-based commands after restart because PIDs can be recycled.

## Test and acceptance boundaries

Backend tests use actual localhost sockets for good/bad JSON, missing synthetic cases, wrong evidence centre, fake PDF, stale login page and port conflict. GitHub browser CI runs this same probe against actual launched FastAPI and built Next before Playwright. Full seven-job CI, release container and merged-SHA checks remain required.

A successful localhost probe verifies a functional synthetic demonstration path, NOT independent detector accuracy, GPU support, licensed real CCTV footage, network bandwidth, legal pilot permission or official deployment. Institutional acceptance stays on issue #91 and the source-specific heldout issues.
