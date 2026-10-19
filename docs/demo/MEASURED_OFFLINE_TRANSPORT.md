# Phase 4 — measured offline transport proof (controlled)

The existing edge worker, atomic disk queue, server normalization and idempotent ledger remain the underlying system. Phase 4 closes a real retry hole: when a server accepted an event but the HTTP acknowledgement was lost, previously the server skipped the duplicate WITHOUT acknowledging it. The queue could remain stuck. It now re-ACKs only exactly identical, canonicalized events from the same authenticated device; a reused event ID with changed centre/body or different device is rejected.

## Run the actual reproducible local disconnect/reconnect drill

From repo root with the standard development environment:

~~~powershell
python scripts/rehearse_offline_transport.py --out "C:\Private\KaushalWatch\phase4-offline-transport.json"
~~~

The script creates two GENERATED attendance-abstention metadata records (not camera model predictions), closes a real localhost TCP port to simulate a network outage, checks the disk queue survives a new worker instance, starts a real localhost HTTP server forwarding to the existing FastAPI /api/edge/sync route, deliberately loses the first HTTP acknowledgement AFTER central persistence, and retries the same events. Server duplicate protection re-ACKs, the queue empties, and the central analysis history remains exactly once per event. The script writes a private, non-overwriting file with actual observed request/response BODY byte counts, queued/delivered/remaining totals, duplicate acknowledgements, failures and UTC last-sync timestamp.

This is a **real local HTTP transport test**, NOT a WAN bandwidth test, not transport/TLS overhead, no live government API, no GPU model run or surveillance accuracy claim. The output status is measured_loopback_fixture_not_field_qualified. No footage or credentials are copied to a remote server.

For a legitimate locally-authorized camera result, separately run the EXISTING edge/agent.py analyze command with a source permitted for that workflow, then use agent.py sync to submit only sanitized aggregate metadata. Offline agent status now shows an atomically saved local journal including successful application bytes, last success UTC, retry/error count and persisted queue depth. Do not send source recording pixels in sync.

## Optional presentation inside the existing four-module CRM

Set the following ONLY in a localhost controlled demo, with the JSON report stored **outside web/public and outside the web app directory**:

~~~powershell
$env:KAUSHALWATCH_ENV = "development"
$env:KAUSHALWATCH_LOCAL_OFFLINE_REPORT = "true"
$env:KAUSHALWATCH_OFFLINE_REPORT_PATH = "C:\Private\KaushalWatch\phase4-offline-transport.json"
~~~

Open the existing KaushalAI guided mission; its Offline by design card now shows *measured* delivered/queued, retries, request body bytes, remaining and IST last sync. Without the private report or in protected/staging/pilot/prod it says no local measurement (or the route is disabled). This is not a fifth module. The API is localhost-only, read-only, no-store and validates the synthetic measured status and counter relationships. It refuses external Host/forwarded-host/cross-origin access.

## Security and remaining caveats

- The agent canonicalizes every event using the EXISTING server privacy normalizer **before network transfer**; raw video, frames, face embeddings, identity lists and rejected fields are never sent from the queue. Unsafe queued entries remain on disk for operator correction rather than silently disappearing.
- Queues are bounded by 1,000 records / 2 MB. Sync batches are at most 200 records / 1 MB and one centre per request. Edge queue is single-process with atomic replace, not a distributed broker.
- An optional device-to-centre allowlist, KAUSHALWATCH_EDGE_SYNC_CENTRES_JSON, has format {"device-id":["CENTRE-ID"]}. When configured, the server declines events for other centres. Empty actor access is denied. Institution-specific protected operation MUST configure/verify allowlists and device registration; lack of a mapping is not field pilot approval.
- Successful acknowledged application bytes are measured as len(actual POST body) and len(actual JSON response body). Headers, IP, TCP, retries lost in-flight and HTTPS framing are not included; neither a fixed 5 KB savings statement nor a fabricated 99% reduction is emitted.
- A 503 after central persistence leaves the local event queued; the next identical retry is safely acknowledged. New event IDs for an existing officer-reviewed case still cannot overwrite its review. Device/centre mismatched replay ID is blocked.
- The existing SQLite/JSON single-worker demo remains distinct from production PostgreSQL transactions and live authenticated device/camera provenance. Phase 5 must show officer review and scorecard; institutional field gate #91 stays open.

## Regression

Backend tests use **real localhost sockets**, current FastAPI ingestion and actual disk queues to exercise network cut/rejoin, dropped ACK after server commit, device restart, duplicate re-ACK, centred actor scope, mixed-centre payload, privacy preflight and bounded queue. CI also executes the operator drill and verifies a generated receipt. Node tests guard local-only report admission; Playwright/full-protected builds keep their previous tests.
