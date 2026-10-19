# Phase 2 — source-locked controlled replay

This phase provides **real recorded-video decoding and source SHA verification** for the *three existing procedural* Camera Trust clips. It does not provide genuine live CCTV, independently labelled attendance accuracy, or proof of the fixture counts in the guided SIH scenarios.

## Launch

From the repository root, use the existing local app/start workflow (Next.js web and FastAPI demo). Navigate to **KaushalAI → Explore the Proof of Training → Source-locked replay** at \`/demo/mission\`. The UI calls \`GET /api/demo/replay\`, verifies the exact three allowlisted public procedural samples against \`web/public/camera-trust/manifest.json\`, then enables video playback. It never accepts a user-provided media path, does not follow Drive URLs, and is disabled when \`NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY=true\`, environment is pilot/staging/production, or strict-staging acceptance is active.

A quality marker was authored by \`scripts/build_camera_trust_clips.py\` for each recording: focus 8–13 s, visibility 9–15 s, and scene alignment 7–13 s respectively. These **are not model detections**. The UI offers frame seeking, real decoded playback, metadata validation, a manifest-matched full SHA-256 and an explicit unverified-model state. The displayed attendance/equipment values belong to *separate illustrative scenarios* and are never attributed to these procedural recordings.

If an expected clip or its manifest is absent, modified, untrusted, over-sized or non-decodable, the replay fails closed; no detections or model confidence are inferred. Static procedural files are already public demo assets—**do not place private footage under \`web/public/\` or \`web/.controlled-replay/\`**.

## Optional saved model receipt — private local input, not certified proof

The source binding also supports *operator-imported* source-matched inference receipts in \`web/.controlled-replay/receipts/<clip-id>.json\`. This path is gitignored, read only by the server and never used as a source of media. No receipt is bundled with the project. The compact schema is:

\`\`\`json
{
  "schema": "KW_REPLAY_MODEL_RECEIPT_V1",
  "source_kind": "PROCEDURALLY_GENERATED_RECORDING_NOT_REAL_CCTV",
  "source_sha256": "<64 lowercase hex matching web/public/camera-trust/manifest.json>",
  "provider": "operator-supplied",
  "model_sha256": "<64 lowercase hex>",
  "profile_sha256": "<64 lowercase hex>",
  "samples": [
    {"second": 0.0, "frame": 0, "boxes": [
      {"label": "person", "score": 0.75, "x": 0.3, "y": 0.2, "width": 0.15, "height": 0.5}
    ]}
  ]
}
\`\`\`

This JSON is a **format example only, not a measured AI result**; do not copy it as a real receipt. Only import genuinely saved inference outputs from the exact file, model and profile; do not manually invent detector boxes. Each sample must match its 12-FPS frame index (±0.05s), be time-ordered, have bounded normalized coordinates and valid confidences. On mismatch, the entire receipt is rejected and *no overlay* is shown. A valid imported receipt is called **source-matched, operator-supplied, unqualified**, because source SHA matching alone cannot prove independent ground truth, model execution or camera field accuracy. Results are visible only at frame-matched playback times.

\`/api/demo/replay\` returns a sanitized, bounded allowlist of box labels and sample numbers, never the original input file, unknown fields, passwords, media directories or trainee identities.

## Next admission step

To replay private approved Drive media, implement a separately reviewed authenticated/centre-scoped, range-safe streaming API with custody and opt-in controls; do **not** copy that footage to \`public/\` or weaken the protected officer proxy. Exact source media + model hash + model profile + authorized frame receipt + blinded labels must be admitted together. That is not implemented by the procedural-video phase.

Phase 3 will integrate manifests and independently reviewed equipment and work-zone footage. Issue #91 remains open for actual pilot acceptance.
