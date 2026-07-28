from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import experiment_manifest as manifest  # noqa: E402


class ManifestTests(unittest.TestCase):
    def test_unique_circuit_names(self) -> None:
        rows = manifest.all_circuit_experiments()
        self.assertEqual(len(rows), len({row.name for row in rows}))

    def test_token_bundle_includes_membership_and_nullifier(self) -> None:
        token_rows = [
            row
            for row in manifest.logical_experiments("all")
            if row.family == "token_policy_bundle"
        ]
        self.assertTrue(token_rows)
        for row in token_rows:
            self.assertIn("pi_mem", row.policy_set)
            self.assertIn("pi_null", row.policy_set)

    def test_rq3_scope_has_four_variants_per_bundle(self) -> None:
        rows = manifest.logical_experiments("rq3")
        counts = Counter(row.composition_id for row in rows)
        self.assertEqual(counts["valid_limit_b32"], 4)
        self.assertEqual(counts["account_budget_b32"], 4)
        self.assertEqual(counts["token_bundle_b32_d16"], 4)

    def test_comparison_groups_are_canonical(self) -> None:
        groups = {
            row.comparison_group
            for row in manifest.logical_experiments("all")
            if row.composition_id
        }
        self.assertEqual(groups, {"baseline", "commitment_linked"})

    def test_all_scope_contains_partial_scopes(self) -> None:
        all_rows = set(manifest.logical_experiments("all"))
        self.assertTrue(
            set(manifest.logical_experiments("rq1-rq2")).issubset(all_rows)
        )
        self.assertTrue(set(manifest.logical_experiments("rq3")).issubset(all_rows))



if __name__ == "__main__":
    unittest.main()
