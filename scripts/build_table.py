#!/usr/bin/env python3
"""
Generate a LaTeX table from bench_results.csv.

Input:
    results/bench_results.csv

Output:
    results/bench_table.tex
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


RESULTS_DIR = Path("results")
CSV_FILE = RESULTS_DIR / "bench_results.csv"
OUTPUT_TEX = RESULTS_DIR / "bench_table.tex"
OUTPUT_TXT = RESULTS_DIR / "bench_table.txt"


FAMILY_LABELS = {
    "sufficient_balance": "Balance",
    "cumulative_limit": "Cumulative limit",
    "balance_and_limit": "Balance + limit",
    "balance_limit_and_conservation": "Bal. + limit + conservation",
}


def load_results(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing CSV file: {csv_path}")

    df = pd.read_csv(csv_path)

    tags = df["tags_json"].apply(json.loads)
    tags_df = pd.json_normalize(tags)
    df = pd.concat([df.drop(columns=["tags_json"]), tags_df], axis=1)

    df["bits"] = df["bits"].astype(int)
    df["family_label"] = df["family"].map(FAMILY_LABELS).fillna(df["family"])

    return df


def format_float(x: float, digits: int = 4) -> str:
    return f"{x:.{digits}f}"


def build_latex_table(df: pd.DataFrame) -> str:
    df = df.sort_values(["bits", "family_label"]).copy()

    lines = []
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(r"\small")
    lines.append(r"\begin{tabular}{lrrrrr}")
    lines.append(r"\toprule")
    lines.append(
        r"Policy & Bits & Constraints & Witness (s) & Prove (s) & Verify (s) \\"
    )
    lines.append(r"\midrule")

    for _, row in df.iterrows():
        policy = row["family_label"]
        bits = int(row["bits"])
        constraints = int(row["constraints"]) if pd.notna(row["constraints"]) else "-"
        witness = format_float(row["witness_time_s_mean"])
        prove = format_float(row["prove_time_s_mean"])
        verify = format_float(row["verify_time_s_mean"])

        lines.append(
            f"{policy} & {bits} & {constraints} & {witness} & {prove} & {verify} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(
        r"\caption{End-to-end cryptographic enforcement cost for representative payment policies. "
        r"We report the number of constraints, witness generation time, proving time, and verification time "
        r"for different bit-widths.}"
    )
    lines.append(r"\label{tab:zkp-bench}")
    lines.append(r"\end{table}")

    return "\n".join(lines)

def build_txt_table(df: pd.DataFrame) -> str:
    df = df.sort_values(["bits", "family_label"]).copy()

    # Prepare rows
    rows = []
    headers = ["Policy", "Bits", "Constraints", "Witness(s)", "Prove(s)", "Verify(s)"]

    for _, row in df.iterrows():
        rows.append([
            row["family_label"],
            str(int(row["bits"])),
            str(int(row["constraints"])) if pd.notna(row["constraints"]) else "-",
            format_float(row["witness_time_s_mean"]),
            format_float(row["prove_time_s_mean"]),
            format_float(row["verify_time_s_mean"]),
        ])

    # Compute column widths
    cols = list(zip(*([headers] + rows)))
    col_widths = [max(len(str(x)) for x in col) for col in cols]

    def format_row(row):
        return " | ".join(
            str(cell).ljust(width)
            for cell, width in zip(row, col_widths)
        )

    separator = "-+-".join("-" * w for w in col_widths)

    lines = []
    lines.append("ZKP Benchmark Results")
    lines.append("")
    lines.append(format_row(headers))
    lines.append(separator)

    for r in rows:
        lines.append(format_row(r))

    return "\n".join(lines)



def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_results(CSV_FILE)

    # TXT version 
    txt_table = build_txt_table(df)
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(txt_table)
    print(f"TXT table written to {OUTPUT_TXT.resolve()}")

    # LaTeX version    
    latex = build_latex_table(df)
    with open(OUTPUT_TEX, "w", encoding="utf-8") as f:
        f.write(latex)
    print(f"LaTeX table written to {OUTPUT_TEX.resolve()}")


if __name__ == "__main__":
    main()