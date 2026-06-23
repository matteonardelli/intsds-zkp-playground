#!/usr/bin/env python3
"""Generate compact IEEE-compatible LaTeX tables from campaign summaries."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Optional


LABELS = {
    "local_financial_validity": r"Local validity ($\pi_{\mathsf{valid}}$)",
    "operating_limit": r"Operating limit ($\pi_{\mathsf{limit}}$)",
    "privacy_budget": r"Privacy budget ($\pi_{\mathsf{budget}}$)",
    "state_transition_and_conservation": r"State transition ($\pi_{\mathsf{trans}}$)",
    "merkle_membership": r"Merkle membership ($\pi_{\mathsf{mem}}$)",
    "nullifier_correctness": r"Nullifier correctness",
    "local_validity_and_operating_limit": r"Validity $\wedge$ limit",
    "account_policy_core": r"Account policy core",
    "account_policy_with_privacy_budget": r"Account core $+$ budget",
    "token_policy_bundle": r"Token policy bundle",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def number(value: str | None) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def fmt_int(value: str | None) -> str:
    parsed = number(value)
    return "--" if parsed is None else f"{int(round(parsed)):,}"


def fmt_ms(value: str | None) -> str:
    parsed = number(value)
    return "--" if parsed is None else f"{parsed * 1000:.2f}"


def fmt_ratio(value: str | None) -> str:
    parsed = number(value)
    return "--" if parsed is None else f"{parsed:.3f}"


def representative_rows(summary: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for row in summary:
        if row.get("execution_mode") != "monolithic":
            continue
        family = row.get("family")
        bits = number(row.get("bits"))
        depth = number(row.get("merkle_depth"))
        include = (
            (family in {
                "local_financial_validity",
                "operating_limit",
                "privacy_budget",
                "state_transition_and_conservation",
                "local_validity_and_operating_limit",
                "account_policy_core",
                "account_policy_with_privacy_budget",
            } and bits == 32)
            or (family == "merkle_membership" and depth == 16)
            or family == "nullifier_correctness"
            or (family == "token_policy_bundle" and depth == 16)
        )
        if include:
            selected.append(row)

    order = {
        "local_financial_validity": 0,
        "operating_limit": 1,
        "privacy_budget": 2,
        "state_transition_and_conservation": 3,
        "merkle_membership": 4,
        "nullifier_correctness": 5,
        "local_validity_and_operating_limit": 6,
        "account_policy_core": 7,
        "account_policy_with_privacy_budget": 8,
        "token_policy_bundle": 9,
    }
    return sorted(selected, key=lambda row: order.get(row["family"], 99))


def write_representative_table(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\small",
        r"\caption{Representative Groth16 costs for the 32-bit arithmetic configurations and depth-16 membership configurations. Times are reported in milliseconds over successful measured runs.}",
        r"\label{tab:representative-costs}",
        r"\begin{tabular}{lrrrrrr}",
        r"\toprule",
        r"Policy configuration & Constraints & Witness med. & Prove med. & Prove p95 & Verify med. & Proof (B) " + r"\\",
        r"\midrule",
    ]
    for row in rows:
        label = LABELS.get(row["family"], row["family"])
        lines.append(
            " & ".join(
                [
                    label,
                    fmt_int(row.get("constraints")),
                    fmt_ms(row.get("witness_time_s_median")),
                    fmt_ms(row.get("prove_time_s_median")),
                    fmt_ms(row.get("prove_time_s_p95")),
                    fmt_ms(row.get("verify_time_s_median")),
                    fmt_int(row.get("proof_size_bytes")),
                ]
            )
            + r" \\" 
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table*}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def composition_label(row: dict[str, str]) -> str:
    base = LABELS.get(row["family"], row["family"])
    bits = number(row.get("bits"))
    depth = number(row.get("merkle_depth"))
    if row["family"] == "token_policy_bundle" and depth is not None:
        return f"{base}, $d={int(depth)}$"
    if bits is not None:
        return f"{base}, $k={int(bits)}$"
    return base


def write_composition_table(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\small",
        r"\caption{Monolithic-to-separate cost ratios for composed policy configurations. Values below one indicate a saving from enforcing the policies in one proof.}",
        r"\label{tab:composition-ratios}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Composition & Constraints & Proving time & Verification time & Total proof size " + r"\\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            " & ".join(
                [
                    composition_label(row),
                    fmt_ratio(row.get("ratio_constraints")),
                    fmt_ratio(row.get("ratio_prove_time_s_median")),
                    fmt_ratio(row.get("ratio_verify_time_s_median")),
                    fmt_ratio(row.get("ratio_proof_size_bytes")),
                ]
            )
            + r" \\" 
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table*}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    tables_dir = run_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    summary = read_csv(run_dir / "summary.csv")
    composition = read_csv(run_dir / "composition_comparison.csv")

    write_representative_table(
        tables_dir / "table_representative_costs.tex",
        representative_rows(summary),
    )
    write_composition_table(
        tables_dir / "table_composition_ratios.tex", composition
    )

    print(f"Tables written to {tables_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
