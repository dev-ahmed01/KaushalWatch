# KaushalWatch submission playback

Run the Windows launcher from the repository root:

    powershell -ExecutionPolicy Bypass -File .\Start-KaushalWatch-Submission.ps1

It sets the existing local/demo profile, starts FastAPI and Next.js in separate windows, seeds deterministic case data only when missing, and opens:

    http://localhost:3000/centres/DEMO-KA-104/camera-trust

Three H.264 recordings are bundled in web/public/camera-trust. They work offline. No video file chooser, OAuth token, independent PostgreSQL setup, or additional asset downloads are needed to preview them.

The monitor supports camera switching, Play/Pause, Replay, speed change, seek, synced quality markers, Mark reviewed / Undo, All signals and JSON Export. Review status persists locally. Other existing KaushalWatch centre modules remain accessible through the same tabs.

The sources are small procedurally generated recordings with programmed transformations: Training bay (focus 00:08–00:13), Workshop floor (coverage 00:09–00:15), and East corridor (alignment 00:07–00:13). Playback cues refer to those known edits, not an independently validated ML detector. The UI displays a compact PLAYBACK marker instead of a large research banner. The recordings contain no real people or private footage.

Video provenance is recorded in web/public/camera-trust/manifest.json. Repository hygiene allows only these three small SHA-verified generated files, while continuing to reject all other videos, source CCTV, private recordings and model binaries.

Protected deployments continue to use the existing OIDC/CSRF/PostgreSQL private worker, which is intentionally separate from the self-contained submission workspace.
