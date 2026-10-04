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

Accepted event IDs are removed locally; unaccepted events remain queued. Synced
analysis summaries are folded into central Analysis History, and synced exception
cases become reviewable without uploading the raw recording.

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
