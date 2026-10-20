# Phase 15 — One-command controlled judge release rehearsal

**Purpose:** prove that the actual Next.js + FastAPI services carry a judge through the four-module application, saved officer evidence, real returned PDF bytes, the short narrative and a negative-control conclusion. Procedural camera recordings and seeded case records are separate synthetic/controlled examples, NOT evidence that a real institution was monitored.

## Windows dry run (read-only by default)

From the KaushalWatch checkout, with Python backend requirements and web dependencies already installed:

~~~powershell
# One-time browser installation in the web directory
cd web
npx playwright install chromium
cd ..

# Source hash + synthetic seed checks; no data writes
.\scripts\Start-KaushalWatch-Judge.ps1 -PreflightOnly

# Launch actual FastAPI + Next, run browser checks and stop only those new servers
.\scripts\Start-KaushalWatch-Judge.ps1 -RunRehearsal
~~~

Only in a disposable synthetic-only environment, the optional pair of switches -ResetSimulatedState -RunRehearsal prepares a known controlled dataset before launch. Never reset real data. Existing launcher guards refuse non-demo records, PostgreSQL/S3 storage, protected environments, occupied ports and altered procedural sources.

The launcher passes actual -ApiPort and -WebPort to the browser tests, checks localhost HTTP readiness both before and after the browser suite, restores the previous E2E environment variables, and terminates only the services it launched. Chromium must be installed independently. To keep the application running for a live human judge, use the normal launcher **without** -RunRehearsal and manually navigate the 60-second or 3m20s cues.

## Real browser acceptance path

New suite: web/e2e/phase15-release-rehearsal.spec.ts. A named CI E2E gate runs it separately before the full Playwright suite.

1. KaushalAI home → Explore the Proof of Training → four controlled scenarios.
2. Source-locked replay manifest resolves three pinned procedural clips, does not claim field accuracy, and displays a verified source receipt.
3. Attendance → Decision → saved synthetic centre-matched case → officer evidence/audit → exact return to the same decision step. Synthetic seeded cases are not falsely linked to procedural videos.
4. GET real centre PDF from running FastAPI; demand HTTP 200, PDF MIME and %PDF- bytes.
5. Run the 60-second manual chapter selection through attendance, obstructed-camera withheld values, item verification uncertainty and a normal/no-exception outcome with NO generated case.
6. Navigate real Centres, centre Overview, Insights report workspace, Actions work queue.
7. Simulate source-manifest outage: no video or camera conclusion may be shown until the human retries and the verified source returns.
8. At 375px width, verify no document overflow on major screens and no case on normal-control selection.

All browser tests are read-only; no officer-review HTTP writes are permitted. Existing CI independently tests role permissions, OIDC, camera-source separation, evidence integrity, offline queue and database persistence.

## Interpretation

A passing run means a controlled local browser journey worked in the tested browser/runtime, not production uptime, a measured 60-second human speaking performance, institutional accuracy, real camera freshness, real-site tampering attribution or government approval. The Playwright and post-test HTTP probe must BOTH succeed for the launcher to announce success. On failure it preserves browser diagnostics and temporary service logs and stops only its launched services.

The final presentation laptop still needs a manual screen/codec/GPU/audio/network/driver rehearsal. External institutional pilot Issue #91 stays OPEN. No private MEVA/UHCTD footage or real CCTV belongs in public assets or Git history.
