"""Safety regressions for merged-PR branch archival policy."""
from __future__ import annotations

import unittest

from archive_merged_branches import safe_ref, select_branches


REPO = "dev-ahmed01/KaushalWatch"


def branch(name: str, sha: str = "a"*40, protected: bool = False):
    return {"name": name, "commit": {"sha": sha}, "protected": protected}


def pr(name: str, sha: str = "a"*40, *, state="closed", merged=True, repo=REPO):
    return {"state": state, "merged_at": "2026-10-14T12:00:00Z" if merged else None,
            "head": {"ref": name, "sha": sha, "repo": {"full_name": repo}}}


class BranchCleanupSafety(unittest.TestCase):
    def test_branch_ref_filter(self):
        self.assertTrue(safe_ref("feature/some-branch"))
        for name in ("../oops", ".hidden", "foo..bar", "a//b", "", "-evil",
                     "refs/heads/../main", "tag.lock", "test@{1}"):
            self.assertFalse(safe_ref(name), name)

    def test_exact_tip_of_merged_pr_may_be_archived(self):
        good, skipped = select_branches(
            [branch("old-feature"), branch("main")],
            [pr("old-feature")], REPO, "main")
        self.assertEqual(good, [{"branch":"old-feature","sha":"a"*40}])
        self.assertEqual(skipped[0]["reason"], "protected-by-policy")

    def test_diverged_tip_is_never_pruned(self):
        good, skipped = select_branches(
            [branch("old-feature","b"*40)], [pr("old-feature","a"*40)], REPO,"main")
        self.assertFalse(good)
        self.assertEqual(skipped[0]["reason"],"no-exact-merged-PR-head")

    def test_unmerged_and_orphan_branches_are_preserved(self):
        good, skipped = select_branches(
            [branch("experiment"),branch("no-pr")],
            [pr("experiment",merged=False)], REPO,"main")
        self.assertFalse(good)
        self.assertEqual(len(skipped),2)

    def test_open_pr_protects_branch_even_with_prior_merge(self):
        good, skipped = select_branches(
            [branch("feature")],
            [pr("feature"),pr("feature",state="open",merged=False)],
            REPO,"main")
        self.assertFalse(good)
        self.assertEqual(skipped[0]["reason"],"open-PR")

    def test_protected_branches_and_camera_candidate_survive(self):
        good, skipped = select_branches(
            [branch("feature",protected=True),branch("fix/uhctd-camera-trust-v2")],
            [pr("feature"),pr("fix/uhctd-camera-trust-v2")], REPO,"main")
        self.assertFalse(good)
        self.assertEqual(len(skipped),2)

    def test_foreign_repo_merged_pr_cannot_delete_local_branch(self):
        good, skipped = select_branches(
            [branch("copied")],
            [pr("copied",repo="another-owner/another-repo")], REPO,"main")
        self.assertFalse(good)
        self.assertEqual(skipped[0]["reason"],"no-exact-merged-PR-head")


if __name__ == "__main__":
    unittest.main()
