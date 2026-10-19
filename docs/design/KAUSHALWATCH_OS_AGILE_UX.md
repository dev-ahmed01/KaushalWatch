# KaushalWatch OS — agile UX delivery

## Original challenge (SIH26245)
Near-real-time or periodic video for training centres, compared against reported attendance and sanctioned infrastructure with bandwidth-aware, privacy-preserving evidence-based officer follow-up. The authoritative internal build scope remains docs/build-scope.md and docs/design/ai-first-restructure.md.

## Product decision
Keep four product destinations because the previous tested AI-first information architecture has already established their routes and evidence APIs:
- **KaushalAI:** what changed, where to go.
- **Centres:** reported vs observed, practical activity, infrastructure, camera trust, evidence.
- **Insights:** only aggregated trustworthy measures and trends.
- **Actions:** one human review and follow-up queue.

Avoid separate primary tabs for analytics, reports, settings, model diagnostics or experiment controls. Centre-level functions use local tabs. A zero-trust camera must not become verified. Video replay markers remain recorded sample markers, not live AI inference.

## Visual system
Body: **Poppins 400/500/600**. Headings: **Bricolage Grotesque 500/600/700**. Offline-safe system fallbacks. Warm white/blue-grey base, single blue action, status color reserved for actual state. Subtle CSS-only node pattern may appear inside overview hero; no background picture competing with evidence. Minimum readable labels and accessible contrast.

## Agile release slices
1. Foundation: tokens, responsive shell, navigation, semantic typography, accessibility.
2. Command centre: stats-first hero and evidence-linked review.
3. Centre cockpit: five verification pillars grouped by officer decision.
4. QA: mobile, keyboard, protection, app build and API regression.
Iterate using GitHub CI, browser tests, then review PR and merge if fully green.

### Quality bar
Existing endpoints, protected session gate, case review audit, source integrity, and prepared recorded samples must not regress. The synthetic fixtures remain explicitly marked on operational screens; user-requested brevity does not permit false live-camera claims.
