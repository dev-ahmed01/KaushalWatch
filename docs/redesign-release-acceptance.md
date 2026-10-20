# KaushalWatch OS — Redesign release verification

## Scope
Five navigation modules: **Overview, Issues, Insights, Centre Desk, Chatbox**. The redesigned mission remains a supporting guide at `/demo/mission`; legacy centre and case deep links remain accessible.

## Required release gates

1. Confirm the exact release branch HEAD SHA and `main` SHA. Run all seven application CI jobs (frontend, backend, hygiene, postgres-persistence, protected-browser, e2e, oidc-browser-acceptance), plus Pilot Release Containers. Do **not** claim a verified merge from PR checks alone; verify the post-merge SHA.
2. Rebuild Next.js with the actual API port and self-hosted fonts. Read the existing launcher instructions before changing any synthetic state. **Never** reset a workspace that may contain real cases or private footage.
3. In a disposable synthetic workspace, open Overview, select each issue kind, inspect case/audit, download PDF, run the source-locked mission and verify an optional MP4 request happens **only after Load verified recording** is clicked.
4. Check Centre Desk tasks persist after reload, two local demo roles can exchange text, a second role can play a saved private voice note, and a third cross-centre role cannot read its media. Role-switching inside the browser is a demo test facility, **not** production authentication.
5. Check Today/Last 7 days/Last 1 month Insights correctly select backend periods and do not invent trends or count unknown camera readings as zero.
6. Review desktop at 1586×992 and 1366×768, mobile at 375×812 and 320×700. Check tab order, focus, speech/record permission denial and document overflow.

## Working local demo example (Windows)

Use ports that are free on the operator laptop; previous notes indicate 8000 and 3000 may be occupied by unrelated apps.

```powershell
cd 'C:\Users\Admin\Desktop\KaushalWatch-Judge'
# Rebuild after pulling the exact merged release SHA.
.\scripts\Prepare-KaushalWatch-OfflineBuild.ps1 -ApiPort 8001
# ONLY when the local folder has been verified as disposable synthetic fixtures:
.\scripts\Start-KaushalWatch-Judge.ps1 -ProductionWeb -ResetSimulatedState -RunRehearsal -ApiPort 8001 -WebPort 3002
# Routine rerun without resetting any persisted messages/tasks:
.\scripts\Start-KaushalWatch-Judge.ps1 -ProductionWeb -ApiPort 8001 -WebPort 3002
```

The above sequence documents intent; **a completed Windows hardware/browser acceptance for this redesign has not been recorded**. Existing scripts may require a SHA-bound artifact update and review after all PRs merge.

## Browser acceptance / optional screenshots

```powershell
cd web
npm ci
npx playwright install chromium
npx playwright test e2e/redesign-r10-acceptance.spec.ts --project chromium
# Optional visual capture; requires running API and local Next app:
$env:KW_CAPTURE_REDESIGN_SCREENSHOTS = 'true'
npx playwright test e2e/redesign-r10-acceptance.spec.ts --project chromium
```

Screenshots are generated locally under `test-results/redesign-screens/`; visually inspect against the five approved reference PNGs, disregarding mockup invented data.

## Feature availability and boundaries

- **Local controlled mode:** local SQLite task/chat audit, synthetic staff/rosters, text and voice note persistence, no real external delivery or actual staff identity proof.
- **Protected deployments:** synthetic Centre Desk/Chatbox endpoints fail closed. Real deployment requires PostgreSQL-backed messaging, provisioned membership/roles, private object storage, retention policy and live security acceptance; don't advertise chat as a deployed external feature.
- **Gemini:** optional server-configured text reasoning via existing assistant tools. Without credentials the product displays labelled source/rule summaries, not pretend AI. Voice-note transport is separate from Groq transcription and TTS.
- **Evidence:** camera trust blocked means unknown, not zero; aggregate attendance variance does not identify absentees; equipment not visible is not necessarily absent; motion is a proxy; repeated images do not prove fraud. The officer owns decisions.
- **Private research footage:** never add any unlicensed MEVA/UHCTD clips from Drive to web/public or Git. Real camera and independent field validation (including issue #103) remain outstanding.

## Final sign-off ledger

| Gate | Pass condition | Verification |
| --- | --- | --- |
| Application CI | Seven jobs green on exact head, then merged main | GitHub Actions runs |
| Container build | Pilot Release Containers green on exact merged main | GitHub Actions run |
| Demo workstation | Fresh port-bound bundle, local playback and report, physical mic trial | Operator sign-off pending |
| Browser parity | Five layouts at 4 viewport sizes, no overflow, appropriate media gating | Screenshot review pending |
| Production Chatbox | Provisioned identities and private production store | Not implemented; local demo only |
| External research / pilot | Independent licensing and field measurements | Not qualified |

The R10 virtual-microphone test uses Chromium's fake media source, not the operator's physical microphone. It checks a valid WebM upload, local preview, persisted history and private playback between permitted demo roles; physical microphone acceptance remains separate.
