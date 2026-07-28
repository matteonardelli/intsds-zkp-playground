#!/usr/bin/env python3
"""Generate paper-oriented figures from completed benchmark results.

Requires pandas and matplotlib. Each figure is written independently. The
composition plot uses only the security-consistent commitment-linked rows.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


FAMILY_LABELS = {
    "local_financial_validity": "Local validity",
    "operating_limit": "Operating limit",
    "privacy_budget": "Privacy budget",
    "state_transition_and_conservation": "State transition",
    "local_validity_and_operating_limit": "Validity + limit",
    "account_policy_core": "Account core",
    "account_policy_with_privacy_budget": "Account core + budget",
    "token_policy_bundle": "Token bundle",
    "merkle_membership": "Merkle membership",
    "nullifier_correctness": "Nullifier derivation",
}
GROUP_ALIASES = {
    "legacy": "baseline",
    "baseline": "baseline",
    "linked": "commitment_linked",
    "commitment": "commitment_linked",
    "commitment_linked": "commitment_linked",
}
COMPOSITION_ORDER = {
    "valid_limit_b32": 0,
    "account_budget_b32": 1,
    "token_bundle_b32_d16": 2,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--rq3-run",
        type=Path,
        help="Optional archived RQ3 result directory; defaults to run_dir",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory; defaults to run_dir",
    )
    parser.add_argument(
        "--format", choices=("pdf", "png"), default="pdf", help="Output format"
    )
    return parser.parse_args()


def read_frame(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def load_data(
    run_dir: Path, rq3_run: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw = read_frame(run_dir / "raw_runs.csv")
    summary = read_frame(run_dir / "summary.csv")
    composition = read_frame(rq3_run / "composition_comparison.csv")

    for frame in (raw, summary, composition):
        for column in (
            "bits",
            "merkle_depth",
            "constraints",
            "prove_time_s",
            "verify_time_s",
            "witness_time_s",
            "total_online_time_s",
            "prove_time_s_median",
            "ratio_prove_time_s_median",
            "ratio_total_online_time_s_median",
        ):
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "comparison_group" in composition.columns:
        composition["comparison_group"] = composition["comparison_group"].map(
            lambda value: GROUP_ALIASES.get(str(value), str(value))
        )
    return raw, summary, composition


def save_current(figures_dir: Path, filename: str, extension: str) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(figures_dir / f"{filename}.{extension}", bbox_inches="tight")
    plt.close()


def plot_constraint_scaling(
    summary: pd.DataFrame, figures_dir: Path, extension: str
) -> None:
    families = [
        "local_financial_validity",
        "operating_limit",
        "privacy_budget",
        "state_transition_and_conservation",
    ]
    data = summary[
        (summary["execution_mode"] == "monolithic")
        & (summary["family"].isin(families))
    ].copy()
    plt.figure(figsize=(5.6, 3.4))
    for family in families:
        group = data[data["family"] == family].sort_values("bits")
        plt.plot(
            group["bits"],
            group["constraints"],
            marker="o",
            label=FAMILY_LABELS[family],
        )
    plt.xlabel("Monetary bit-width")
    plt.ylabel("R1CS constraints")
    plt.xticks([16, 32, 64])
    plt.legend(fontsize=8)
    save_current(figures_dir, "fig_constraints_bitwidth", extension)


def plot_proving_distributions(
    raw: pd.DataFrame, figures_dir: Path, extension: str
) -> None:
    families = [
        "local_financial_validity",
        "operating_limit",
        "privacy_budget",
        "state_transition_and_conservation",
    ]
    data = raw[
        (raw["phase"] == "measured")
        & (raw["status"] == "ok")
        & (raw["execution_mode"] == "monolithic")
        & (raw["bits"] == 32)
        & (raw["family"].isin(families))
    ].copy()
    grouped = [
        data.loc[data["family"] == family, "prove_time_s"].dropna().to_numpy()
        for family in families
    ]
    plt.figure(figsize=(5.8, 3.5))
    plt.boxplot(grouped, tick_labels=[FAMILY_LABELS[f] for f in families])
    plt.ylabel("Proving time (s)")
    plt.xticks(rotation=18, ha="right")
    save_current(figures_dir, "fig_proving_distribution_32", extension)


def plot_merkle_constraints(
    summary: pd.DataFrame, figures_dir: Path, extension: str
) -> None:
    data = summary[
        (summary["execution_mode"] == "monolithic")
        & (summary["family"] == "merkle_membership")
    ].sort_values("merkle_depth")
    plt.figure(figsize=(4.8, 3.2))
    plt.plot(data["merkle_depth"], data["constraints"], marker="o")
    plt.xlabel("Merkle-tree depth")
    plt.ylabel("R1CS constraints")
    plt.xticks([8, 16, 32])
    save_current(figures_dir, "fig_merkle_constraints", extension)


def plot_merkle_proving(
    raw: pd.DataFrame, figures_dir: Path, extension: str
) -> None:
    data = raw[
        (raw["phase"] == "measured")
        & (raw["status"] == "ok")
        & (raw["execution_mode"] == "monolithic")
        & (raw["family"] == "merkle_membership")
    ].copy()
    depths = [8, 16, 32]
    grouped = [
        data.loc[data["merkle_depth"] == depth, "prove_time_s"]
        .dropna()
        .to_numpy()
        for depth in depths
    ]
    plt.figure(figsize=(4.8, 3.2))
    plt.boxplot(grouped, tick_labels=[str(depth) for depth in depths])
    plt.xlabel("Merkle-tree depth")
    plt.ylabel("Proving time (s)")
    save_current(figures_dir, "fig_merkle_proving_distribution", extension)


def plot_composition_ratio(
    composition: pd.DataFrame, figures_dir: Path, extension: str
) -> None:
    if composition.empty:
        return
    data = composition.copy()
    if "comparison_group" in data.columns:
        data = data[data["comparison_group"] == "commitment_linked"].copy()
    if data.empty:
        return
    data["_order"] = data["composition_id"].map(COMPOSITION_ORDER).fillna(99)
    data = data.sort_values("_order")
    data["label"] = data.apply(
        lambda row: (
            f"{FAMILY_LABELS.get(row['family'], row['family'])}\n"
            + (
                f"{int(row['bits'])} bit"
                if pd.notna(row.get("bits"))
                else f"depth {int(row['merkle_depth'])}"
            )
        ),
        axis=1,
    )
    plt.figure(figsize=(7.0, 3.8))
    positions = range(len(data))
    plt.bar(positions, data["ratio_prove_time_s_median"])
    plt.axhline(1.0, linewidth=1)
    plt.xticks(positions, data["label"], rotation=35, ha="right", fontsize=7)
    plt.ylabel("Monolithic / separate median proving time")
    save_current(figures_dir, "fig_composition_proving_ratio", extension)


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    rq3_run = (args.rq3_run or args.run_dir).resolve()
    output_dir = (args.output_dir or args.run_dir).resolve()
    raw, summary, composition = load_data(run_dir, rq3_run)
    figures_dir = output_dir / "figures"

    if raw.empty or summary.empty:
        raise ValueError("Core raw_runs.csv and summary.csv must be non-empty")
    plot_constraint_scaling(summary, figures_dir, args.format)
    plot_proving_distributions(raw, figures_dir, args.format)
    plot_merkle_constraints(summary, figures_dir, args.format)
    plot_merkle_proving(raw, figures_dir, args.format)
    plot_composition_ratio(composition, figures_dir, args.format)

    print(f"Figures written to {figures_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
