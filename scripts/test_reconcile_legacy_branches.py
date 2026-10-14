"""Unit checks: legacy source branch cleanup is exact-tip and archive gated."""
import unittest
from reconcile_legacy_branches import AUDITED, PRESERVE, SUPERSEDED_PRS, audit_config, can_prune


class ReconciliationSafety(unittest.TestCase):
    def test_configuration_excludes_camera_and_main(self):
        audit_config()
        self.assertEqual(len(AUDITED), 11)
        self.assertNotIn("main", AUDITED)
        self.assertNotIn(PRESERVE, AUDITED)

    def test_reconciled_legacy_tip_can_be_pruned_only_after_archival(self):
        name = "redesign/full-command-centre-v3"
        sha = AUDITED[name]
        self.assertTrue(can_prune(name, sha, protected=False, open_heads=set(), tag_sha=sha))
        self.assertFalse(can_prune(name, sha, protected=False, open_heads=set(), tag_sha=None))
        self.assertFalse(can_prune(name, sha, protected=False, open_heads=set(), tag_sha="b" * 40))
        self.assertFalse(can_prune(name, "b" * 40, protected=False, open_heads=set(), tag_sha=sha))

    def test_open_pr_and_protected_ref_are_never_pruned(self):
        branch = SUPERSEDED_PRS[25]
        sha = AUDITED[branch]
        self.assertFalse(can_prune(branch, sha, protected=False, open_heads={branch}, tag_sha=sha))
        self.assertFalse(can_prune(branch, sha, protected=True, open_heads=set(), tag_sha=sha))

    def test_unlisted_branches_never_deleted_even_if_tagged(self):
        for name in ("main", PRESERVE, "unknown-experiment"):
            self.assertFalse(can_prune(name, "a" * 40, protected=False, open_heads=set(), tag_sha="a"*40))


if __name__ == "__main__":
    unittest.main()
