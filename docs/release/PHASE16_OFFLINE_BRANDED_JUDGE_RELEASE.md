# Phase 16 — Offline-branded, source-bound production judge demo

Phase 15 already verifies a genuine read-only Chromium journey through the four modules, saved synthetic officer evidence and real PDF. Phase 16 removes two additional judge-day risks: runtime Google Fonts requests and relying on the Next development server.

This is a local controlled demonstration release path, NOT an institutionally approved production deployment. The developer launcher remains available. No real research footage, AI thresholds, officer audit permissions or frontend modules were changed.

## What changes

The light OS retains Poppins for body and Bricolage Grotesque for headings. Next's built-in next/font/google downloads these licensed fonts at BUILD time and hosts them with its generated static assets. The judge's browser therefore makes no Google Fonts runtime requests. Raw font files are not added to Git or provided separately.

A frozen presentation build is bound to:
- the exact clean Git source commit;
- the API origin, e.g. http://127.0.0.1:8000;
- the actual Next BUILD_ID;
- the procedural camera source manifest SHA-256;
- controlled demonstration mode (never protected officer-mode approval).

An altered/missing receipt, changed source, wrong API port, dirty tracked Git checkout or stale build blocks startup. A source receipt cannot prove Chromium playback or AI field accuracy; actual browser rehearsal tests those separately.

## Windows: one-time build while connected

From the clean, current KaushalWatch checkout:

~~~powershell
cd "C:\Users\Admin\Desktop\KaushalWatch-main"
cd web
npm ci
npx playwright install chromium
cd ..

# Fetch Poppins/Bricolage only at build time and create source-bound receipt.
.\scripts\Prepare-KaushalWatch-OfflineBuild.ps1 -ApiPort 8000

# This preflight is read-only and does not launch/reset anything.
.\scripts\Start-KaushalWatch-Judge.ps1 -PreflightOnly -ProductionWeb -ApiPort 8000
~~~

Do not edit tracked project files or switch commits after the build. If the API port, commit or procedural manifest changes, build again. Keep the generated .next folder on the workstation; it is intentionally excluded from Git.

## Disconnected judge rehearsal and live presentation

After preparation, the local UI, sourced recordings, simulated saved officer case and real generated PDF can be exercised on localhost without access to external browser/CDN/font hosts:

~~~powershell
# Uses optimized Next start (not Next dev), runs Chromium and cleans up.
.\scripts\Start-KaushalWatch-Judge.ps1 -ProductionWeb -RunRehearsal -ApiPort 8000 -WebPort 3000

# Keep both services active for a live human presentation.
.\scripts\Start-KaushalWatch-Judge.ps1 -ProductionWeb -ApiPort 8000 -WebPort 3000
~~~

On a newly prepared machine with working network access, combine the online preparation and rehearsal:

~~~powershell
.\scripts\Start-KaushalWatch-Judge.ps1 -ProductionWeb -BuildProductionWeb -RunRehearsal
~~~

Reset of case data is NEVER implied; -ResetSimulatedState is a separate explicit action guarded against non-demo records. Occupied ports are refused before any reset or build. -ProductionWeb is a localhost-optimized site, not an authorized institutional officer deployment.

## Verification and limits

The new Playwright suite deliberately aborts all browser requests outside localhost. It checks that actual Poppins/Bricolage font faces load locally, the procedural manifest is valid, the main routes render, and the user can inspect a saved synthetic officer case and request a real PDF. The main Phase-15 and protected-browser/OIDC/full browser acceptance suites remain mandatory.

External AI inference, online assistant, cloud databases, remote SMS, speech or other third-party providers are NOT promised offline. npm installation, Chromium installation and build-time font fetching require an initial online preparation step. Actual Windows machine, decoder, browser GPU/audio and other real hardware still require local manual execution.

Independent approved training-centre AI accuracy, pilot permissions and institutional authorization remain separate, and Issue #91 stays OPEN.
