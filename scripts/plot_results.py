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
GROTH16_CSV_FILE = RESULTS_DIR / "bench_results_groth16.csv"
PLONK_CSV_FILE = RESULTS_DIR / "bench_results_plonk.csv"


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

def plot_if_exists(csv_path: Path, backend:str) -> None:
    try:
        df = load_results(csv_path)

        # Constraints
        make_metric_plot(
            df=df,
            metric_col="constraints",
            ylabel="Number of constraints",
            output_file=RESULTS_DIR / f"constraints_comparison_{backend}.pdf",
        )

        # Proving time_mean
        make_metric_plot(
            df=df,
            metric_col="prove_time_s_mean",
            ylabel="Proving time (s)",
            output_file=RESULTS_DIR / f"proving_time_mean_comparison_{backend}.pdf",
        )

        # Verification time_mean
        make_metric_plot(
            df=df,
            metric_col="verify_time_s_mean",
            ylabel="Verification time (s)",
            output_file=RESULTS_DIR / f"verify_time_mean_comparison_{backend}.pdf",
        )
        # Proving time_median
        make_metric_plot(
            df=df,
            metric_col="prove_time_s_median",
            ylabel="Proving time (s)",
            output_file=RESULTS_DIR / f"proving_time_median_comparison_{backend}.pdf",
        )

        # Verification time_median
        make_metric_plot(
            df=df,
            metric_col="verify_time_s_median",
            ylabel="Verification time (s)",
            output_file=RESULTS_DIR / f"verify_time_median_comparison_{backend}.pdf",
        )

        # Proving time_Variance
        make_metric_plot(
            df=df,
            metric_col="prove_time_s_var",
            ylabel="Proving time (s)",
            output_file=RESULTS_DIR / f"proving_time_variance_comparison_{backend}.pdf",
        )

        # Verification time_Variance
        make_metric_plot(
            df=df,
            metric_col="verify_time_s_var",
            ylabel="Verification time (s)",
            output_file=RESULTS_DIR / f"verify_time_variance_comparison_{backend}.pdf",
        )
        print(f"Plots for {csv_path} saved in: {RESULTS_DIR.resolve()}")
         
    except:
        print(f"Unable to generate plots for {csv_path}")
     
        
def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    plot_if_exists(GROTH16_CSV_FILE, "groth16")
    plot_if_exists(PLONK_CSV_FILE, "plonk")


if __name__ == "__main__":
    main()