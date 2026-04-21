#!/usr/bin/env python3
"""
Create simple comparison plots from bench_results.csv.

Input:
    results/bench_results.csv

Output:
    results/constraints_comparison.pdf
    results/proving_time_comparison.pdf
    results/verify_time_comparison.pdf
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


RESULTS_DIR = Path("results")
CSV_FILE = RESULTS_DIR / "bench_results.csv"


def load_results(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing CSV file: {csv_path}")

    df = pd.read_csv(csv_path)

    # Expand tags_json into explicit columns
    tags = df["tags_json"].apply(json.loads)
    tags_df = pd.json_normalize(tags)

    df = pd.concat([df.drop(columns=["tags_json"]), tags_df], axis=1)

    # Normalize column names for convenience
    if "family" not in df.columns or "bits" not in df.columns:
        raise ValueError("Expected 'family' and 'bits' fields in tags_json")

    df["bits"] = df["bits"].astype(int)

    return df


def make_metric_plot(
    df: pd.DataFrame,
    metric_col: str,
    ylabel: str,
    output_file: Path,
) -> None:
    families = sorted(df["family"].unique())
    bits = sorted(df["bits"].unique())

    plt.figure(figsize=(8, 5))

    for family in families:
        sub = df[df["family"] == family].sort_values("bits")
        x = sub["bits"].tolist()
        y = sub[metric_col].tolist()
        plt.plot(x, y, marker="o", label=family)

    plt.xlabel("Bit-width")
    plt.ylabel(ylabel)
    plt.xticks(bits)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = load_results(CSV_FILE)

    # Constraints
    make_metric_plot(
        df=df,
        metric_col="constraints",
        ylabel="Number of constraints",
        output_file=RESULTS_DIR / "constraints_comparison.pdf",
    )

    # Proving time
    make_metric_plot(
        df=df,
        metric_col="prove_time_s_mean",
        ylabel="Proving time (s)",
        output_file=RESULTS_DIR / "proving_time_comparison.pdf",
    )

    # Verification time
    make_metric_plot(
        df=df,
        metric_col="verify_time_s_mean",
        ylabel="Verification time (s)",
        output_file=RESULTS_DIR / "verify_time_comparison.pdf",
    )

    print("Plots saved in:", RESULTS_DIR.resolve())


if __name__ == "__main__":
    main()