# KaushalWatch public synthetic showcase deployment

**Purpose:** provide a safe, shareable **simulation** of the recording-driven workflow. This is not a government centre deployment, a real computer-vision benchmark or a public officer workspace.

## Vercel frontend

Deploy repository `dev-ahmed01/KaushalWatch` with Root Directory `web` and Next.js. Configure:

- `NEXT_PUBLIC_KAUSHALWATCH_PUBLIC_SHOWCASE=true`
- `KAUSHALWATCH_PUBLIC_SHOWCASE=true`
- `NEXT_PUBLIC_KAUSHALWATCH_SHOWCASE_API=https://<actual-read-only-render-host>`
- `NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY=false`

The Vercel edge proxy allows only `/demo/studio`, the three checked-in `/camera-trust/*.mp4` assets, `/api/demo/replay`, and framework static files. The main officer pages redirect to the studio. Other Next.js API routes return 404. The AppShell officer nav, localhost backend network polls and drawer are omitted from the public-only build. The studio fetches each public MP4 and compares its SHA-256 with the bundled procedural manifest *in the browser*, failing closed on mismatch. The local full application remains unchanged when the public-showcase flag is off.

## Render sample API

Deploy the same repository as a **new** Render Python web service:

- Build: `python -m compileall -q backend/app/public_showcase.py`
- Start: `python backend/app/public_showcase.py`
- Region: Singapore, free plan for a low-traffic demonstration (may sleep on inactivity).
- No secrets, PostgreSQL, external AI providers or paid inference required.
- Paths: `GET /healthz`, `GET /api/showcase/scenes`. Other paths 404 and mutations 405.

The Render service is *intentionally not* the real FastAPI backend: exposing development/demo mode would allow unauthenticated officer-case and chat writes, which `backend/app/services/review_access.py` explicitly says must **not** be used publicly. The hosted presentation is standalone: its local chat, review and AI actions stay in browser memory and are not shared between visitors. Render provides safe read-only synthetic scenario metadata and an optional availability check.

## Acceptance criteria

1. A Git-connected Vercel production deployment is READY and public access to `/demo/studio` succeeds.
2. `/api/demo/replay` returns only the three pinned procedural sources. All three corresponding public MP4s have actual digest matches in the browser.
3. `/api/assistant/chat`, `/api/proxy`, `/chatbox` and real officer routes **cannot** expose their internal endpoints in the public build.
4. Render `/healthz` and `/api/showcase/scenes` return 200 and synthetic=true, while POST returns 405.
5. Playwright verifies scenario switching, 00:08/00:16 checkpoints, simulated questions, UNKNOWN camera evidence, 320px viewport, and no sensitive real-data endpoints.
6. No original camera footage, Google Drive credentials, production secrets or institutional source data are deployed.
7. Label on the public site: “Simulated demo · scripted analysis”. Do not advertise the fake detection values as derived from these recordings.

**To run a real pilot later**, provision independently reviewed media and actual authentication, private storage, and qualified detectors. Do not flip `KAUSHALWATCH_ENV=development` on an internet-facing copy of `backend/app/main.py`.
