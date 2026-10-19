# KaushalWatch OS — Sprint 4: Low-bandwidth and release QA

## Scope
Keep the four existing CRM-style officer destinations; no new modules and no raw-video uploads. This release improves access when API reads are delayed, a device disconnects, or independently provisioned centre intelligence is temporarily unavailable.

## Implemented
- **Device offline banner:** only shown when the *browser device* reports offline, not mistaken for API health or camera/edge trust. Live decisions require an online authorized server; prerecorded local MP4s remain the separate demo workspace.
- **Explicit recovery:** Overview, Centres, Actions and Insights have an actual Retry button on network failure. A failed request is never presented as an empty verified queue. GET reads have a bounded 20-second timeout; case review writes are never automatically retried.
- **Fail-closed operational data:** Protected-API failures cannot substitute the shared five-centre demo fixture, even during initial loading. A missing/unauthorized centre ID never takes Bengaluru's centre identity.
- **Independent centre identity vs intelligence:** A failing intelligence response no longer discards a successful centre metadata fetch. Camera counts, compliance states and evidence remain absent until their own trusted response returns.
- **Low-bandwidth centre-source indicator:** displays the registry-configured connectivity class and exact last-analysis timestamp (or no analysis recorded). It explicitly does *not* claim that the centre is currently connected, synced, streaming, or independently trusted.
- **Recorded media recovery:** a failed preloaded sample MP4 has a Retry recording control. All sample clips are local, tiny, synthetic, SHA-pinned in web/public/camera-trust/manifest.json, and labeled PLAYBACK rather than live CCTV.
- **No protected offline cache:** no service worker, IndexedDB persistence, raw footage or personal identity cache is introduced. Edge telemetry is separately bounded and privacy-sanitized by existing backend ingestion. Absence of a browser network is not proof that an edge event has been synced.

## Verification
- Browser online/offline transitions, failure and retry on all four main modules, centre identity outage and targeted recovery, known and unknown centre source distinction, small-screen overflow.
- Exact SHA-256 comparison of all three generated MP4s against the committed manifest using bytes delivered by the serving web app.
- Existing end-to-end officer decision workflow, access-scoped PDF reports, protected sessions/OIDC, PostgreSQL, backend trust/edge and repository hygiene all remain release gates.
- Fonts use existing Poppins/Bricolage Grotesque with system fallbacks and reduced-motion CSS.

## Boundary
This is **offline-tolerant UI and an established edge-summary workflow**, not a service-worker PWA or independently validated field camera system. The server is required for fresh status, protected report access, authorized officer writes and evidence custody. For a completely offline demonstration, start the bundled local backend and Next.js service. Do not call local prerecorded footage a live camera stream.
