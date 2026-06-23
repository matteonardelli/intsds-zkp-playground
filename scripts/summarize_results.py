#!/usr/bin/env python3
"""Summarize a completed policy-model benchmark campaign."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional


TIMING_METRICS = (
    "witness_time_s",
    "prove_time_s",
    "verify_time_s",
    "total_online_time_s",
)
STATIC_METRICS = ("constraints", "proof_size_bytes", "public_size_bytes")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="results/<run-id> directory")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def to_float(value: str | None) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def percentile(values: Iterable[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile() requires at least one value")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_values(values: list[float], prefix: str) -> dict[str, Any]:
    if not values:
        return {
            f"{prefix}_count": 0,
            f"{prefix}_mean": "",
            f"{prefix}_median": "",
            f"{prefix}_stdev": "",
            f"{prefix}_min": "",
            f"{prefix}_p25": "",
            f"{prefix}_p75": "",
            f"{prefix}_iqr": "",
            f"{prefix}_p95": "",
            f"{prefix}_max": "",
            f"{prefix}_cv": "",
        }
    mean_value = statistics.mean(values)
    p25 = percentile(values, 0.25)
    p75 = percentile(values, 0.75)
    return {
        f"{prefix}_count": len(values),
        f"{prefix}_mean": mean_value,
        f"{prefix}_median": statistics.median(values),
        f"{prefix}_stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        f"{prefix}_min": min(values),
        f"{prefix}_p25": p25,
        f"{prefix}_p75": p75,
        f"{prefix}_iqr": p75 - p25,
        f"{prefix}_p95": percentile(values, 0.95),
        f"{prefix}_max": max(values),
        f"{prefix}_cv": (
            statistics.stdev(values) / mean_value
            if len(values) > 1 and mean_value != 0
            else 0.0
        ),
    }


def summarize_experiments(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("phase") == "measured":
            groups[row["experiment_name"]].append(row)

    summary_rows: list[dict[str, Any]] = []
    for experiment_name, group in sorted(groups.items()):
        first = group[0]
        successful = [
            row
            for row in group
            if row.get("status") == "ok"
            and row.get("verification_ok", "").lower() in {"true", "1"}
        ]
        base: dict[str, Any] = {
            key: first.get(key, "")
            for key in (
                "campaign_run_id",
                "experiment_name",
                "family",
                "policy_set",
                "architecture",
                "role",
                "bits",
                "merkle_depth",
                "composition_id",
                "execution_mode",
                "component_count",
                "component_names",
                "proving_system",
            )
        }
        base["attempted_runs"] = len(group)
        base["successful_runs"] = len(successful)
        base["failed_runs"] = len(group) - len(successful)

        for metric in STATIC_METRICS:
            values = [
                value
                for value in (to_float(row.get(metric)) for row in successful)
                if value is not None
            ]
            base[metric] = statistics.median(values) if values else ""

        for metric in TIMING_METRICS:
            values = [
                value
                for value in (to_float(row.get(metric)) for row in successful)
                if value is not None
            ]
            base.update(summarize_values(values, metric))

        summary_rows.append(base)

    return summary_rows


def composition_comparisons(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in summary_rows:
        composition_id = str(row.get("composition_id") or "")
        if not composition_id:
            continue
        groups[composition_id][str(row["execution_mode"])] = row

    output: list[dict[str, Any]] = []
    comparison_metrics = (
        "constraints",
        "witness_time_s_median",
        "prove_time_s_median",
        "verify_time_s_median",
        "total_online_time_s_median",
        "proof_size_bytes",
        "public_size_bytes",
    )
    for composition_id, modes in sorted(groups.items()):
        if "monolithic" not in modes or "separate" not in modes:
            continue
        mono = modes["monolithic"]
        separate = modes["separate"]
        row: dict[str, Any] = {
            "campaign_run_id": mono["campaign_run_id"],
            "composition_id": composition_id,
            "family": mono["family"],
            "policy_set": mono["policy_set"],
            "architecture": mono["architecture"],
            "bits": mono["bits"],
            "merkle_depth": mono["merkle_depth"],
            "monolithic_experiment": mono["experiment_name"],
            "separate_experiment": separate["experiment_name"],
        }
        for metric in comparison_metrics:
            mono_value = to_float(str(mono.get(metric, "")))
            sep_value = to_float(str(separate.get(metric, "")))
            row[f"monolithic_{metric}"] = mono_value if mono_value is not None else ""
            row[f"separate_{metric}"] = sep_value if sep_value is not None else ""
            if mono_value is not None and sep_value not in (None, 0.0):
                ratio = mono_value / sep_value
                row[f"ratio_{metric}"] = ratio
                row[f"saving_{metric}"] = 1.0 - ratio
            else:
                row[f"ratio_{metric}"] = ""
                row[f"saving_{metric}"] = ""
        output.append(row)
    return output


def semantic_equivalence_rows(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key = {
        (str(row["family"]), str(row["bits"]), str(row["execution_mode"])): row
        for row in summary_rows
    }
    output: list[dict[str, Any]] = []
    for bits in ("16", "32", "64"):
        limit_row = by_key.get(("operating_limit", bits, "monolithic"))
        budget_row = by_key.get(("privacy_budget", bits, "monolithic"))
        if not limit_row or not budget_row:
            continue
        output.append(
            {
                "bits": bits,
                "operating_constraints": limit_row["constraints"],
                "budget_constraints": budget_row["constraints"],
                "constraint_difference": to_float(str(budget_row["constraints"]))
                - to_float(str(limit_row["constraints"])),
                "operating_prove_median_s": limit_row[
                    "prove_time_s_median"
                ],
                "budget_prove_median_s": budget_row["prove_time_s_median"],
            }
        )
    return output


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    raw_path = run_dir / "raw_runs.csv"
    if not raw_path.exists():
        raise FileNotFoundError(raw_path)

    rows = read_csv(raw_path)
    summaries = summarize_experiments(rows)
    comparisons = composition_comparisons(summaries)
    equivalence = semantic_equivalence_rows(summaries)

    write_csv(run_dir / "summary.csv", summaries)
    write_csv(run_dir / "composition_comparison.csv", comparisons)
    write_csv(run_dir / "limit_budget_equivalence.csv", equivalence)

    print(f"Wrote {run_dir / 'summary.csv'}")
    print(f"Wrote {run_dir / 'composition_comparison.csv'}")
    print(f"Wrote {run_dir / 'limit_budget_equivalence.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
