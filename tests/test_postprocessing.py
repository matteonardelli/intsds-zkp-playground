from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_tables  # noqa: E402
import summarize_results  # noqa: E402


class PostprocessingTests(unittest.TestCase):
    def test_historical_group_names_are_normalized(self) -> None:
        self.assertEqual(
            summarize_results.normalize_comparison_group("legacy"), "baseline"
        )
        self.assertEqual(
            summarize_results.normalize_comparison_group("linked"),
            "commitment_linked",
        )


    def test_historical_run_id_is_normalized(self) -> None:
        import csv
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["campaign_run_id"])
                writer.writeheader()
                writer.writerow({"campaign_run_id": "old-run"})
            rows = summarize_results.read_csv(path)
        self.assertEqual(rows[0]["evaluation_run_id"], "old-run")

    def test_internal_tag_name_is_normalized(self) -> None:
        self.assertEqual(
            summarize_results.normalize_binding_mode("tx_tag"),
            "transaction_commitment",
        )

    def test_table_composition_labels_are_keyed_by_id(self) -> None:
        rows = [
            {"composition_id": "token_bundle_b32_d16", "execution_mode": "separate"},
            {"composition_id": "valid_limit_b32", "execution_mode": "monolithic"},
            {"composition_id": "account_budget_b32", "execution_mode": "separate"},
            {"composition_id": "token_bundle_b32_d16", "execution_mode": "monolithic"},
            {"composition_id": "account_budget_b32", "execution_mode": "monolithic"},
            {"composition_id": "valid_limit_b32", "execution_mode": "separate"},
        ]
        ordered = build_tables.binding_overhead_rows(rows)
        keys = [(row["composition_id"], row["execution_mode"]) for row in ordered]
        self.assertEqual(
            keys,
            [
                ("valid_limit_b32", "monolithic"),
                ("valid_limit_b32", "separate"),
                ("account_budget_b32", "monolithic"),
                ("account_budget_b32", "separate"),
                ("token_bundle_b32_d16", "monolithic"),
                ("token_bundle_b32_d16", "separate"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
