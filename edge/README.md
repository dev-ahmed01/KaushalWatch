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

Accepted event IDs are removed locally; unaccepted events remain queued.

## Privacy / integrity boundary

The queued event includes aggregate/compliance metadata and evidence hashes, not face embeddings, identity records, raw frames, local evidence paths or raw video.
