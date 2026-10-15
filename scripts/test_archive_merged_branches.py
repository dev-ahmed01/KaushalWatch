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

    def test_phase3c_exact_squash_merged_heads_are_prunable(self):
        # A squash merge changes main's ancestry, not the merged PR's head
        # identity. Only exact, unchanged source heads may be archived.
        heads = {
            "phase3c/epfl-temporal-diagnosis": "9b21fc5a698d1a43e6b19981db9a73e883ef8b80",
            "phase3c/heldout-runtime-fidelity": "0cf7334da7ac316feb5ebb70704e27593ea8c851",
            "phase3c/attendance-evidence-abstention": "3a49987625d34f8a749b901bc1f27e4642338ae4",
            "phase3c/independent-cohort-preflight": "98064aefb7fa79047998c7ffe1ce9be38ea20bf2",
        }
        branches = [branch("main")] + [branch(name, sha) for name, sha in heads.items()]
        branches.append(branch("fix/uhctd-camera-trust-v2", "0fd1076bd2b80ebe1e570b1c3351ab589f273857"))
        prs = [pr(name, sha) for name, sha in heads.items()]
        prs.append(pr("fix/uhctd-camera-trust-v2",
                      "0fd1076bd2b80ebe1e570b1c3351ab589f273857",
                      state="open", merged=False))
        selected, skipped = select_branches(branches, prs, REPO, "main")
        self.assertEqual({row["branch"]: row["sha"] for row in selected}, heads)
        self.assertEqual({row["branch"] for row in skipped},
                         {"main", "fix/uhctd-camera-trust-v2"})
        self.assertTrue(all(row["reason"] == "protected-by-policy" for row in skipped))

    def test_phase3c_moved_tip_must_not_be_deleted(self):
        merged_sha = "98064aefb7fa79047998c7ffe1ce9be38ea20bf2"
        selected, skipped = select_branches(
            [branch("phase3c/independent-cohort-preflight", "a" * 40)],
            [pr("phase3c/independent-cohort-preflight", merged_sha)],
            REPO, "main",
        )
        self.assertFalse(selected)
        self.assertEqual(skipped[0]["reason"], "no-exact-merged-PR-head")

    def test_foreign_repo_merged_pr_cannot_delete_local_branch(self):
        good, skipped = select_branches(
            [branch("copied")],
            [pr("copied",repo="another-owner/another-repo")], REPO,"main")
        self.assertFalse(good)
        self.assertEqual(skipped[0]["reason"],"no-exact-merged-PR-head")


if __name__ == "__main__":
    unittest.main()
