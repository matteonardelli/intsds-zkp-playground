#!/usr/bin/env python3
"""Summarize benchmark runs and derive the paper-facing comparison CSV files.

The raw runner keeps implementation identifiers such as ``tx_tag`` and accepts
historical comparison-group names. This script normalizes those values to the
terminology used in the paper:

* ``baseline`` for shared-witness monolithic circuits and unbound separate
  proofs;
* ``commitment_linked`` for variants bound to a common transaction commitment.
"""

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
    "bundle_check_time_s",
    "total_online_time_s",
)
STATIC_METRICS = ("constraints", "proof_size_bytes", "public_size_bytes")
COMPARISON_METRICS = (
    "constraints",
    "witness_time_s_median",
    "prove_time_s_median",
    "verify_time_s_median",
    "total_online_time_s_median",
    "proof_size_bytes",
    "public_size_bytes",
)

COMPARISON_GROUP_ALIASES = {
    "legacy": "baseline",
    "baseline": "baseline",
    "linked": "commitment_linked",
    "commitment": "commitment_linked",
    "commitment_linked": "commitment_linked",
}
BINDING_MODE_ALIASES = {
    "tx_tag": "transaction_commitment",
    "transaction_commitment": "transaction_commitment",
    "shared_witness": "shared_witness",
    "unbound": "unbound",
    "none": "none",
    "": "",
}
COMPOSITION_ORDER = {
    "valid_limit_b32": 0,
    "account_budget_b32": 1,
    "token_bundle_b32_d16": 2,
}
GROUP_ORDER = {"baseline": 0, "commitment_linked": 1, "": 2}
EXECUTION_ORDER = {"monolithic": 0, "separate": 1}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="results/<run-id> directory")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        if not row.get("evaluation_run_id"):
            row["evaluation_run_id"] = row.get("campaign_run_id", "")
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_comparison_group(value: Any) -> str:
    text = str(value or "").strip()
    return COMPARISON_GROUP_ALIASES.get(text, text)


def normalize_binding_mode(value: Any) -> str:
    text = str(value or "").strip()
    return BINDING_MODE_ALIASES.get(text, text)


def canonical_policy_set(family: str, value: Any) -> str:
    """Correct historical metadata while preserving the actual circuit scope."""

    if family == "nullifier_correctness":
        return "pi_null"
    if family == "token_policy_bundle":
        return "pi_mem+pi_null+pi_valid+pi_budget"
    return str(value or "")


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
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        f"{prefix}_count": len(values),
        f"{prefix}_mean": mean_value,
        f"{prefix}_median": statistics.median(values),
        f"{prefix}_stdev": stdev,
        f"{prefix}_min": min(values),
        f"{prefix}_p25": p25,
        f"{prefix}_p75": p75,
        f"{prefix}_iqr": p75 - p25,
        f"{prefix}_p95": percentile(values, 0.95),
        f"{prefix}_max": max(values),
        f"{prefix}_cv": stdev / mean_value if mean_value else 0.0,
    }


def summarize_experiments(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("phase") == "measured":
            groups[row["experiment_name"]].append(row)

    summary_rows: list[dict[str, Any]] = []
    metadata_fields = (
        "evaluation_run_id",
        "experiment_name",
        "family",
        "policy_set",
        "architecture",
        "role",
        "bits",
        "merkle_depth",
        "composition_id",
        "comparison_group",
        "binding_mode",
        "execution_mode",
        "component_count",
        "component_names",
        "proving_system",
    )
    for experiment_name, group in sorted(groups.items()):
        first = group[0]
        successful = [
            row
            for row in group
            if row.get("status") == "ok"
            and row.get("verification_ok", "").lower() in {"true", "1"}
        ]
        base: dict[str, Any] = {key: first.get(key, "") for key in metadata_fields}
        family = str(base.get("family") or "")
        base["policy_set"] = canonical_policy_set(family, base.get("policy_set"))
        base["comparison_group"] = normalize_comparison_group(
            base.get("comparison_group")
        )
        base["binding_mode"] = normalize_binding_mode(base.get("binding_mode"))
        base["attempted_runs"] = len(group)
        base["successful_runs"] = len(successful)
        base["failed_runs"] = len(group) - len(successful)

        binding_values = [row.get("binding_ok", "").lower() for row in group]
        base["binding_failures"] = sum(value == "false" for value in binding_values)

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


def ratio_fields(
    row: dict[str, Any],
    *,
    numerator: dict[str, Any],
    denominator: dict[str, Any],
    numerator_label: str,
    denominator_label: str,
) -> None:
    for metric in COMPARISON_METRICS:
        num = to_float(numerator.get(metric))
        den = to_float(denominator.get(metric))
        row[f"{numerator_label}_{metric}"] = num if num is not None else ""
        row[f"{denominator_label}_{metric}"] = den if den is not None else ""
        if num is not None and den is not None:
            row[f"difference_{metric}"] = num - den
        else:
            row[f"difference_{metric}"] = ""
        if num is not None and den not in (None, 0.0):
            ratio = num / den
            row[f"ratio_{metric}"] = ratio
            row[f"saving_{metric}"] = 1.0 - ratio
        else:
            row[f"ratio_{metric}"] = ""
            row[f"saving_{metric}"] = ""


def composition_comparisons(
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for item in summaries:
        composition_id = str(item.get("composition_id") or "")
        comparison_group = normalize_comparison_group(item.get("comparison_group"))
        if composition_id and comparison_group:
            groups[(composition_id, comparison_group)][str(item["execution_mode"])] = item

    output: list[dict[str, Any]] = []
    for (composition_id, comparison_group), modes in groups.items():
        if "monolithic" not in modes or "separate" not in modes:
            continue
        mono = modes["monolithic"]
        separate = modes["separate"]
        row: dict[str, Any] = {
            "evaluation_run_id": mono["evaluation_run_id"],
            "composition_id": composition_id,
            "comparison_group": comparison_group,
            "family": mono["family"],
            "policy_set": canonical_policy_set(
                str(mono.get("family") or ""), mono.get("policy_set")
            ),
            "architecture": mono["architecture"],
            "bits": mono["bits"],
            "merkle_depth": mono["merkle_depth"],
            "monolithic_experiment": mono["experiment_name"],
            "monolithic_binding_mode": normalize_binding_mode(mono["binding_mode"]),
            "separate_experiment": separate["experiment_name"],
            "separate_binding_mode": normalize_binding_mode(separate["binding_mode"]),
        }
        ratio_fields(
            row,
            numerator=mono,
            denominator=separate,
            numerator_label="monolithic",
            denominator_label="separate",
        )
        output.append(row)

    return sorted(
        output,
        key=lambda row: (
            COMPOSITION_ORDER.get(str(row["composition_id"]), 99),
            GROUP_ORDER.get(str(row["comparison_group"]), 99),
        ),
    )


def binding_overhead_rows(
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in summaries:
        composition_id = str(item.get("composition_id") or "")
        comparison_group = normalize_comparison_group(item.get("comparison_group"))
        execution_mode = str(item.get("execution_mode") or "")
        if composition_id and comparison_group and execution_mode:
            by_key[(composition_id, comparison_group, execution_mode)] = item

    output: list[dict[str, Any]] = []
    composition_ids = sorted(
        {key[0] for key in by_key}, key=lambda cid: COMPOSITION_ORDER.get(cid, 99)
    )
    for composition_id in composition_ids:
        for execution_mode in ("monolithic", "separate"):
            baseline = by_key.get((composition_id, "baseline", execution_mode))
            commitment = by_key.get(
                (composition_id, "commitment_linked", execution_mode)
            )
            if not baseline or not commitment:
                continue
            row: dict[str, Any] = {
                "evaluation_run_id": commitment["evaluation_run_id"],
                "composition_id": composition_id,
                "execution_mode": execution_mode,
                "baseline_experiment": baseline["experiment_name"],
                "baseline_binding_mode": normalize_binding_mode(
                    baseline["binding_mode"]
                ),
                "commitment_linked_experiment": commitment["experiment_name"],
                "commitment_linked_binding_mode": normalize_binding_mode(
                    commitment["binding_mode"]
                ),
            }
            ratio_fields(
                row,
                numerator=commitment,
                denominator=baseline,
                numerator_label="commitment_linked",
                denominator_label="baseline",
            )
            output.append(row)
    return output


def composition_variant_rows(
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fields = (
        "evaluation_run_id",
        "composition_id",
        "comparison_group",
        "execution_mode",
        "binding_mode",
        "experiment_name",
        "family",
        "policy_set",
        "bits",
        "merkle_depth",
        "constraints",
        "witness_time_s_median",
        "prove_time_s_median",
        "verify_time_s_median",
        "bundle_check_time_s_median",
        "total_online_time_s_median",
        "proof_size_bytes",
        "public_size_bytes",
        "successful_runs",
        "failed_runs",
        "binding_failures",
    )
    rows = [
        {field: row.get(field, "") for field in fields}
        for row in summaries
        if row.get("composition_id")
    ]
    return sorted(
        rows,
        key=lambda row: (
            COMPOSITION_ORDER.get(str(row["composition_id"]), 99),
            GROUP_ORDER.get(str(row["comparison_group"]), 99),
            EXECUTION_ORDER.get(str(row["execution_mode"]), 99),
        ),
    )


def semantic_equivalence_rows(
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key = {
        (str(row["family"]), str(row["bits"]), str(row["execution_mode"])): row
        for row in summaries
        if not row.get("comparison_group")
    }
    output: list[dict[str, Any]] = []
    for bits in ("16", "32", "64"):
        limit_row = by_key.get(("operating_limit", bits, "monolithic"))
        budget_row = by_key.get(("privacy_budget", bits, "monolithic"))
        if not limit_row or not budget_row:
            continue
        operating_constraints = to_float(limit_row.get("constraints"))
        budget_constraints = to_float(budget_row.get("constraints"))
        output.append(
            {
                "bits": bits,
                "operating_constraints": operating_constraints,
                "budget_constraints": budget_constraints,
                "constraint_difference": (
                    budget_constraints - operating_constraints
                    if operating_constraints is not None
                    and budget_constraints is not None
                    else ""
                ),
                "operating_prove_median_s": limit_row["prove_time_s_median"],
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
    overhead = binding_overhead_rows(summaries)
    variants = composition_variant_rows(summaries)
    equivalence = semantic_equivalence_rows(summaries)

    outputs = {
        "summary.csv": summaries,
        "composition_comparison.csv": comparisons,
        "binding_overhead.csv": overhead,
        "composition_variants.csv": variants,
        "limit_budget_equivalence.csv": equivalence,
    }
    for filename, data in outputs.items():
        write_csv(run_dir / filename, data)
        print(f"Wrote {run_dir / filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
