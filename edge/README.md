# KaushalWatch Edge Runtime

This is the low-bandwidth/offline execution path for the prototype.

## Principle

```text
local CCTV/video
    -> local vision pipeline
    -> local compliance case
    -> compact JSON telemetry queue
    -> connectivity returns
    -> POST /api/edge/sync
```

The sync request contains **no raw video**. Minimal evidence may remain local unless an authorized review workflow explicitly requests it.

## Analyze while offline

```bash
python edge/agent.py analyze \
  --video data/raw/final-demo.avi \
  --reported-attendance 12 \
  --centre-id DEMO-KA-104 \
  --batch-id ELEC-DEMO-01
```

Inspect the queue:

```bash
python edge/agent.py status
```

## Sync after connectivity returns

Start the API, then:

```bash
python edge/agent.py sync --url http://127.0.0.1:8000
```

Accepted event IDs are removed locally; unaccepted or rejected events **stay queued**
for explicit operator inspection. The server returns `rejected_events` with bounded reasons.
Do not delete them silently. Sync checks that every acknowledged ID belongs to the
actual sent batch, so a malformed response cannot discard unrelated queued work.

For **staging/pilot/production**, the central endpoint requires a configured
edge token. Set these on the **server**:

```bash
KAUSHALWATCH_ENV=staging
KAUSHALWATCH_EDGE_SYNC_AUTH_MODE=token
KAUSHALWATCH_EDGE_SYNC_TOKENS_JSON='{"workshop-edge-01":"REPLACE_WITH_AT_LEAST_32_RANDOM_NONSPACE_ASCII_CHARACTERS"}'
```

Set `KAUSHALWATCH_EDGE_SYNC_TOKEN` on the local edge device to the *matching
secret* using a secure environment-injection mechanism, then run `sync` normally.
Never commit tokens, include them in command-line parameters, or paste them
into support logs. A development-only `demo` mode continues to support the
local SIH walkthrough without keys; **protected environments refuse demo mode**.

Synced analysis summaries are folded into central Analysis History as **unverified
edge telemetry**, not signed observations. An edge's claimed `compliant` status is
downgraded to `blocked` unless the reported decision is compliant, the detector
is authoritative without failures, and a trustworthy camera ratio of at least
0.5 is supplied. Those fields still originate from the edge; central verification
of real model runs is a separate evaluation requirement. Synced exception cases
begin `open` and never become an officer review merely because the edge supplied
a status such as `confirmed`.

## Automatic monitoring windows

The Settings page stores the centre's automatic-analysis policy and monitoring
windows. A connected edge capture agent can now enforce those windows instead of
requiring an officer to press Start Analysis.

For a local camera buffer/recording:

```bash
python edge/agent.py watch \
  --video data/raw/final-demo.avi \
  --reported-attendance 12 \
  --centre-id DEMO-KA-104 \
  --batch-id ELEC-2026-08 \
  --api-url http://127.0.0.1:8000 \
  --sync
```

The agent polls the centre settings, runs at most once per configured window, stores
its last-run window durably, and can sync compact telemetry after the run. Use
`--once` to check the current schedule once during setup or testing.

This prototype scheduler currently automates the attendance edge pipeline. Practical
work and infrastructure remain available through the full-analysis web workflow until
their edge capture/runtime adapters are connected.

## Privacy / integrity boundary

The queued event includes aggregate/compliance metadata and evidence hashes, not face embeddings, identity records, raw frames, local evidence paths or raw video.


## Crash, concurrency and security boundaries

- The local queue and server event receipt ledger now write JSON to a temporary
  file and atomically replace the previous file, preventing truncated queues or
  acknowledgements after a single interrupted write. In-process locks prevent
  competing threads in one worker from losing updates.
- Replaying an event ID is idempotent. Replaying the *same case* with a new event
  ID is acknowledged but **cannot overwrite an officer-reviewed case**.
- The ingest endpoint accepts only attendance summaries and recognized compliance
  cases. Unsupported types, raw-video-bearing payloads, insecure privacy declarations,
  and malformed identity fields are refused. Only approved aggregate metadata and
  evidence SHA-256 values enter central stores; the server does not read local
  video file paths, images, person boxes or identity records from edge events.
- **This remains a single-worker prototype**, not a durable transaction across
  event receipts, cases and history, and not a distributed multi-process ledger.
  Crashes between committing case/history and its event receipt can replay
  history rows. Production needs a transactional datastore/outbox, HTTPS with
  device identity, and properly authenticated/read-scoped officer data access.
- Bearer tokens authenticate a configured *device secret*, not the authenticity
  of media, model scores, authorization claims or the external incident description.
