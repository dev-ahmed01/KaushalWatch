# Phase 17 — Production workstation qualification and judge handoff

**Scope:** controlled, synthetic Proof-of-Training demo only. This phase closes an actionable workstation test gap; it does not turn a CI pass into permission to use real camera data or qualify AI accuracy. Four top-level modules and the source/evidence separation stay unchanged.

## Release change

Previously, the Windows `-RunRehearsal` launcher ran **only** the Phase 15 navigation/evidence Chromium tests, even when `-ProductionWeb` was selected. The Phase 16 disconnected-browser/font checks ran in GitHub CI but were not part of the operator's actual one-command rehearsal.

With `-ProductionWeb -RunRehearsal`, the same running FastAPI and optimized Next production processes must now pass **both** existing real-browser suites:

| Suite | What it demonstrates | What it does **not** certify |
| --- | --- | --- |
| `phase15-release-rehearsal.spec.ts` | Four modules, source manifest/denial and retry, synthetic case/evidence, actual PDF bytes, manual scenario cues, normal no-case negative control, 375px view | Real institution data or officer decision accuracy |
| `phase16-offline-branded.spec.ts` | Browser rejects outside-loopback requests, self-hosted Poppins/Bricolage actually load, case and PDF work under simulated network isolation, 320px Insights containment | Physical Wi-Fi disconnection, other installed software, external AI/SMS/SSO availability or true camera model accuracy |

`-RunRehearsal` without `-ProductionWeb` retains its Phase 15 development-mode behavior; it must **not** print an offline-browser pass. A failing test blocks success; the launcher performs a post-run HTTP integrity probe only after browser success, then stops its own newly spawned server processes. Do not stop unrelated services or silently reset data.

## One-time online preparation on the presentation Windows machine

Use a clean checkout on the final presentation commit. Configure a suitable Python environment and install the pinned backend dependencies per the README. Then:

~~~powershell
cd 'C:\Users\Admin\Desktop\KaushalWatch-main'
cd web
npm ci
npx playwright install chromium
cd ..

# Run while connected; Next downloads fonts at build time.
.\scripts\Prepare-KaushalWatch-OfflineBuild.ps1 -ApiPort 8000

# A nonmutating source / synthetic state / frozen build check.
.\scripts\Start-KaushalWatch-Judge.ps1 -PreflightOnly -ProductionWeb -ApiPort 8000
~~~

A frozen `.next` build receipt is deliberately invalidated by a Git revision change, wrong API port or altered procedural source manifest. Rebuild after checking out the final merge commit; do not carry a build from a pre-merge PR branch.

## One-command production workstation rehearsal

On the real Windows presentation machine, preferably with the machine **physically disconnected from the internet after build preparation**:

~~~powershell
.\scripts\Start-KaushalWatch-Judge.ps1 -ProductionWeb -RunRehearsal -ApiPort 8000 -WebPort 3000
~~~

Expected: actual localhost API and mission HTML readiness; passing Phase 15 and Phase 16 Chromium checks; second local API readiness; `REHEARSAL PASSED` and `OFFLINE BROWSER PASSED`; launcher terminates **only** its own processes. Red text/errors, absent pass markers or a timeout means **not signed off**. Local stdout/stderr service logs are printed under the machine's temporary `kaushalwatch-judge` directory; Playwright failure traces are kept under `web/test-results`. Neither is an authorized field dossier.

For a live presentation **after rehearsal**, keep the server running:

~~~powershell
.\scripts\Start-KaushalWatch-Judge.ps1 -ProductionWeb -ApiPort 8000 -WebPort 3000
~~~

Open `http://127.0.0.1:3000/demo/mission`. No reviewer write and no synthetic state reset are implied.

### Physical signoff — only the presenter can verify

The following are **pending** until visibly tested on the owner's actual laptop, external display and demonstration environment:

- Windows PowerShell, correct Python venv, npm and Chromium install, correct frozen receipt, readable logs and clean startup.
- Internet **actually disconnected** after setup; verify mission navigation, fonts, case/PDF, and absence of surprise captive-portal or remote-host prompts.
- External projector/screen sharing resolution, legible 320px/375px responsive navigation when needed, keyboard focus, video playback/codec or explicit fallback, GPU/audio/driver stability, no prolonged spinner.
- Manual timing rehearsal: perform both narrative routes, verify normal/no-exception selection does not create a case, and locate how to return from officer case to the exact mission step.
- Keep any research/private recordings and actual centre PII **out of** browser assets, Git, screenshots shared externally and judge packs.

If playback fails, use the provided safe source/codec recovery route and continue to the evidence chain; do **not** pass synthetic clips off as camera detections. If the browser suite fails, save non-secret diagnostics locally and investigate; do not label it green because another machine's CI passed.

## Presenter story and judge Q&A

**60-second cue target (manual, not measured):**

1. **0–15 s:** Centre reports attendance 28; controlled example shows 19. That is a question for review, not proven fraud.
2. **15–29 s:** An obstructed camera makes headcount UNKNOWN, never zero.
3. **29–43 s:** A trade manifest describes required equipment. Not visible on video does not mean physically absent; observations are evidence-limited.
4. **43–60 s:** A normal control creates no supported case. Close with local offline telemetry and human officer authorization.

**200-second expanded route (manual, not measured):** 0–40 attendance and provenance; 40–75 camera uncertainty; 75–115 trade/equipment obligations; 115–160 saved simulated officer case → SHA-bound evidence → audit/PDF → exact return; 160–178 normal negative control; 178–200 offline safe transport and explicit qualification limits.

**If asked “Is this live CCTV?”** No. Judge media is generated procedural footage; separately seeded cases are synthetic. Licensed real camera evaluation is a different phase.

**“Does the system prove fraud, equipment absence or machine operability?”** No. It surfaces reviewable evidence with abstentions; an authorized officer decides.

**“Does it work without internet?”** The prepared local controlled UI, media, cases and PDF work through localhost and are browser-tested with remote requests blocked. External AI, SSO, SMS and physical Wi-Fi readiness are not promised.

**“What is actually accurate?”** Software control flow and source integrity are tested. Independent held-out classroom/electrician equipment, camera and attendance metrics are not qualified.

**“Is it ready for government deployment?”** No. Authorized HTTPS/OIDC/registry, live private storage and signed external institutional acceptance are outstanding on issue #91; licensed field trade evidence is outstanding on #103.

## Release merge gate

For this phase: Python regression tests enforce that the Windows launch path invokes the existing offline suite *when and only when* production web is selected. The existing CI end-to-end job already runs the Phase 15 and Phase 16 specs against the optimized Next server; the seven-job app CI and Pilot Release Containers must pass on the exact PR SHA and **again on the merged `main` SHA**.

GitHub CI is a *software acceptance* result only. It is **not** the presenter's physical Windows signoff, approved field AI accuracy or institutional pilot activation. Do not close issues #91 or #103.
