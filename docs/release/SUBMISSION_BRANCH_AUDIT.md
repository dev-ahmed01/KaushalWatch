# Camera Trust branch consolidation audit

Submission release is PR #82 on branch feat/submission-camera-monitor.

PRs #79, #80, and #81 are already integrated into main. Their historical source branches were squash-merged, so their Git histories may still appear diverged; force-merging them again would risk duplicate changes.

Unmerged drafts PRs #62–#78 form a research-only, stacked Phase 3G–3W chain with dependencies on one another. PR #61 (Phase 3D) and PR #54 (the UHCTD candidate) also contain distinct experimental development. They are not safe to fold into main immediately before submission: they have separate assumptions about physical tamper metrics, potentially incompatible camera APIs, and no new consolidated release acceptance.

These branches are preserved without modification or deletion for the later research review. The submission release consolidates only the tested UI, three authenticated-provenance generated recordings, and launcher into main. No old experimental branch is claimed merged merely because a similarly named feature exists.
