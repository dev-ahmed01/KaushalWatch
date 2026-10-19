# Controlled private research replay — reuse the existing Drive cache

This path is for the MEVA/UHCTD research clips located in the user's connected Google Drive Kaushal folder. The selected Day-3 research collection contains 14 short MP4s plus an annotation sheet named selected_clips.csv. The implementation chooses the corresponding covered, defocused, moved and normal-control samples. The annotations are research intervention labels, not model detections, real-centre compliance outcomes or independently witnessed tampering.

## One-time preparation without new uploads

The importer intentionally performs NO network requests and NO video copies. Point it to your existing cached short clips and annotation sheet:

python scripts/prepare_research_replay.py --selection-csv "C:\Users\Admin\Desktop\MEVA\uhctd_day3_selection\selected_clips.csv" --clip-dir "C:\Users\Admin\Desktop\MEVA\uhctd_day3_selection" --write

This only hashes the four already-present video files and creates kw-research-replay.local.json beside them. No large full-day recording is required.

If any of those four short files are not cached yet, the existing camera_trust_workstation/kwtrust/drive_sync.py is a resumable Drive reader that skips complete local files and checks source hashes. The private four-file Drive inventory supplied separately (NOT in Git) can be used to retrieve only missing clips. Follow the workstation README and use an authorized OAuth token outside the Git checkout. Connected ChatGPT Drive access does not automatically give the deployed application persistent Google OAuth permissions.

Run the Next.js development server bound to 127.0.0.1 with these SERVER-SIDE variables:
- KAUSHALWATCH_ENV=development
- KAUSHALWATCH_LOCAL_RESEARCH_REPLAY=true
- KAUSHALWATCH_RESEARCH_REPLAY_DIR=C:\Users\Admin\Desktop\MEVA\uhctd_day3_selection

Do not set these on Vercel, Render, public URLs or tunnels. The media route only accepts localhost/127.0.0.1, refuses forwarded public hostnames and cross-site requests, and rejects all protected/staging/pilot/production modes. The source files must be OUTSIDE the web application directory, and hashes are checked before every media request. Video responses support a bounded single-byte range for seeking, with private no-store headers and no path parameter except a fixed four-name alias allowlist.

On http://localhost:3000/demo/mission, the local research panel appears beneath the three procedural video samples. The four recorded sources and their already-existing annotations can be switched and time-seeked. The original Drive IDs, actual source filenames, file paths and Drive credentials are never served to the browser. No training-centre headcounts are inferred from these clips.

### Failure conditions

Missing clip, wrong hash, symlink, extra manifest entry, invalid class, wrong time interval, invalid MP4 container, data larger than 16 MB, unsupported video decoder, external hostname or a protected deployment must fail closed. A research intervention label is not a measured AI prediction, and this route cannot create an officer case, issue a sanction, or certify physical camera health.

### Remaining acceptance

Before the true Phase-2 issue #102 can close, independent annotations, genuine source/model execution receipts and permissions for any real training-centre footage must be qualified. Phase-2B research replay improves the controlled camera-trust narrative, not attendance or equipment-detection accuracy.
