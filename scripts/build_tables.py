#!/usr/bin/env python3
"""Generate the IEEE-compatible LaTeX tables used by the paper."""

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
    "nullifier_correctness": r"Nullifier derivation ($\pi_{\mathsf{null}}$)",
    "local_validity_and_operating_limit": r"Validity $\wedge$ limit",
    "account_policy_core": r"Account policy core",
    "account_policy_with_privacy_budget": r"Account core $+$ budget",
    "token_policy_bundle": r"Token policy bundle",
}
REPRESENTATIVE_ORDER = {
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
COMPOSITION_ORDER = {
    "valid_limit_b32": 0,
    "account_budget_b32": 1,
    "token_bundle_b32_d16": 2,
}
EXECUTION_ORDER = {"monolithic": 0, "separate": 1}
GROUP_ALIASES = {
    "legacy": "baseline",
    "baseline": "baseline",
    "linked": "commitment_linked",
    "commitment": "commitment_linked",
    "commitment_linked": "commitment_linked",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Complete evaluation result directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory; defaults to run_dir",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_group(value: Any) -> str:
    text = str(value or "").strip()
    return GROUP_ALIASES.get(text, text)


def fmt_int(value: Any) -> str:
    parsed = number(value)
    return "--" if parsed is None else f"{int(round(parsed)):,}"


def fmt_bytes(value: Any) -> str:
    parsed = number(value)
    if parsed is None:
        return "--"
    if abs(parsed - round(parsed)) < 1e-9:
        return f"{int(round(parsed)):,}"
    return f"{parsed:,.1f}"


def fmt_ms(value: Any) -> str:
    parsed = number(value)
    return "--" if parsed is None else f"{parsed * 1000:.2f}"


def fmt_ratio(value: Any) -> str:
    parsed = number(value)
    return "--" if parsed is None else f"{parsed:.3f}"


def is_baseline_monolithic(row: dict[str, str]) -> bool:
    if row.get("execution_mode") != "monolithic":
        return False
    group = normalize_group(row.get("comparison_group"))
    return group in {"", "baseline"}


def representative_rows(summary: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for row in summary:
        family = row.get("family", "")
        bits = number(row.get("bits"))
        depth = number(row.get("merkle_depth"))
        if family not in REPRESENTATIVE_ORDER or not is_baseline_monolithic(row):
            continue
        include = (
            (
                family
                in {
                    "local_financial_validity",
                    "operating_limit",
                    "privacy_budget",
                    "state_transition_and_conservation",
                    "local_validity_and_operating_limit",
                    "account_policy_core",
                    "account_policy_with_privacy_budget",
                }
                and bits == 32
            )
            or (family == "merkle_membership" and depth == 16)
            or family == "nullifier_correctness"
            or (family == "token_policy_bundle" and depth == 16)
        )
        if include:
            selected.append(row)

    by_family: dict[str, dict[str, str]] = {}
    for row in selected:
        family = row["family"]
        if family in by_family:
            raise ValueError(f"Duplicate representative row for family {family}")
        by_family[family] = row
    return sorted(selected, key=lambda row: REPRESENTATIVE_ORDER[row["family"]])


def write_representative_table(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3.0pt}",
        r"\renewcommand{\arraystretch}{1.05}",
        r"\caption{Representative Groth16 costs for 32-bit arithmetic configurations and",
        r"16-level membership configurations. Times are in milliseconds; artifact sizes",
        r"are medians of the serialized SnarkJS JSON files.}",
        r"\label{tab:representative-costs}",
        r"\begin{tabular}{@{}lrrrrrrrr@{}}",
        r"\toprule",
        r"\textbf{Policy configuration} &",
        r"\textbf{Constraints} &",
        r"\textbf{Witness med.} &",
        r"\textbf{Prove med.} &",
        r"\textbf{Prove p95} &",
        r"\textbf{Verify med.} &",
        r"\textbf{Online med.} &",
        r"\textbf{Proof (B)} &",
        r"\textbf{Public (B)} \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            " & ".join(
                [
                    LABELS.get(row["family"], row["family"]),
                    fmt_int(row.get("constraints")),
                    fmt_ms(row.get("witness_time_s_median")),
                    fmt_ms(row.get("prove_time_s_median")),
                    fmt_ms(row.get("prove_time_s_p95")),
                    fmt_ms(row.get("verify_time_s_median")),
                    fmt_ms(row.get("total_online_time_s_median")),
                    fmt_bytes(row.get("proof_size_bytes")),
                    fmt_bytes(row.get("public_size_bytes")),
                ]
            )
            + r" \\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def composition_label(row: dict[str, str]) -> str:
    family = row.get("family", "")
    base = LABELS.get(family, family)
    bits = number(row.get("bits"))
    depth = number(row.get("merkle_depth"))
    if family == "token_policy_bundle" and depth is not None:
        return f"{base}, $d={int(depth)}$"
    if bits is not None:
        return f"{base}, $k={int(bits)}$"
    return base


def commitment_comparison_rows(
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    selected = [
        row
        for row in rows
        if normalize_group(row.get("comparison_group")) == "commitment_linked"
        and row.get("composition_id") in COMPOSITION_ORDER
    ]
    by_id: dict[str, dict[str, str]] = {}
    for row in selected:
        composition_id = row["composition_id"]
        if composition_id in by_id:
            raise ValueError(f"Duplicate commitment-linked comparison: {composition_id}")
        by_id[composition_id] = row
    missing = [cid for cid in COMPOSITION_ORDER if cid not in by_id]
    if missing:
        raise ValueError(f"Missing commitment-linked comparison rows: {missing}")
    return sorted(selected, key=lambda row: COMPOSITION_ORDER[row["composition_id"]])


def write_composition_table(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{4.0pt}",
        r"\renewcommand{\arraystretch}{1.05}",
        r"\caption{Monolithic-to-separate cost ratios for commitment-linked policy",
        r"compositions. Values below one favor monolithic enforcement. Time and size",
        r"columns use medians; proof and public-output sizes are aggregate serialized",
        r"SnarkJS JSON sizes.}",
        r"\label{tab:composition-ratios}",
        r"\begin{tabular}{@{}lrrrrrrr@{}}",
        r"\toprule",
        r"\textbf{Composition} &",
        r"\textbf{Constraints} &",
        r"\textbf{Witness} &",
        r"\textbf{Prove} &",
        r"\textbf{Verify} &",
        r"\textbf{Online} &",
        r"\textbf{Proof size} &",
        r"\textbf{Public size} \\",
        r"\midrule",
    ]
    fields = (
        "ratio_constraints",
        "ratio_witness_time_s_median",
        "ratio_prove_time_s_median",
        "ratio_verify_time_s_median",
        "ratio_total_online_time_s_median",
        "ratio_proof_size_bytes",
        "ratio_public_size_bytes",
    )
    for row in rows:
        lines.append(
            " & ".join(
                [composition_label(row)] + [fmt_ratio(row.get(field)) for field in fields]
            )
            + r" \\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def binding_overhead_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = [
        row
        for row in rows
        if row.get("composition_id") in COMPOSITION_ORDER
        and row.get("execution_mode") in EXECUTION_ORDER
    ]
    by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in selected:
        key = (row["composition_id"], row["execution_mode"])
        if key in by_key:
            raise ValueError(f"Duplicate binding-overhead row: {key}")
        by_key[key] = row
    expected = [
        (composition_id, execution_mode)
        for composition_id in COMPOSITION_ORDER
        for execution_mode in ("monolithic", "separate")
    ]
    missing = [key for key in expected if key not in by_key]
    if missing:
        raise ValueError(f"Missing binding-overhead rows: {missing}")
    return sorted(
        selected,
        key=lambda row: (
            COMPOSITION_ORDER[row["composition_id"]],
            EXECUTION_ORDER[row["execution_mode"]],
        ),
    )


def overhead_composition_label(row: dict[str, str]) -> str:
    composition_id = row["composition_id"]
    labels = {
        "valid_limit_b32": r"Validity $\wedge$ limit, $k=32$",
        "account_budget_b32": r"Account core $+$ budget, $k=32$",
        "token_bundle_b32_d16": r"Token policy bundle, $d=16$",
    }
    return labels[composition_id]


def write_binding_overhead_table(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3.2pt}",
        r"\renewcommand{\arraystretch}{1.05}",
        r"\caption{Overhead introduced by transaction-commitment binding. Each entry is",
        r"the ratio between a commitment-linked configuration and its corresponding",
        r"baseline variant; values above one indicate overhead. The monolithic baseline",
        r"uses a shared witness without an explicit transaction commitment, whereas the",
        r"separate baseline is unbound and does not provide equivalent cross-proof",
        r"consistency.}",
        r"\label{tab:binding-overhead}",
        r"\begin{tabular}{@{}llrrrrrrr@{}}",
        r"\toprule",
        r"\textbf{Composition} &",
        r"\textbf{Execution} &",
        r"\textbf{Constraints} &",
        r"\textbf{Witness} &",
        r"\textbf{Prove} &",
        r"\textbf{Verify} &",
        r"\textbf{Online} &",
        r"\textbf{Proof size} &",
        r"\textbf{Public size} \\",
        r"\midrule",
    ]
    fields = (
        "ratio_constraints",
        "ratio_witness_time_s_median",
        "ratio_prove_time_s_median",
        "ratio_verify_time_s_median",
        "ratio_total_online_time_s_median",
        "ratio_proof_size_bytes",
        "ratio_public_size_bytes",
    )
    previous_composition = None
    for row in rows:
        composition_id = row["composition_id"]
        if previous_composition is not None and composition_id != previous_composition:
            lines.append(r"\addlinespace[1pt]")
        lines.append(
            " & ".join(
                [
                    overhead_composition_label(row),
                    str(row["execution_mode"]).capitalize(),
                ]
                + [fmt_ratio(row.get(field)) for field in fields]
            )
            + r" \\"
        )
        previous_composition = composition_id
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = (args.output_dir or args.run_dir).resolve()
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    summary = read_csv(run_dir / "summary.csv")
    composition = read_csv(run_dir / "composition_comparison.csv")
    overhead = read_csv(run_dir / "binding_overhead.csv")

    write_representative_table(
        tables_dir / "table_representative_costs.tex",
        representative_rows(summary),
    )
    write_composition_table(
        tables_dir / "table_composition_ratios.tex",
        commitment_comparison_rows(composition),
    )
    write_binding_overhead_table(
        tables_dir / "table_binding_overhead.tex",
        binding_overhead_rows(overhead),
    )

    print(f"Tables written to {tables_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
