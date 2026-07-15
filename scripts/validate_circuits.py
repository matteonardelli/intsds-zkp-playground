#!/usr/bin/env python3
"""Functional validation for any campaign profile in the unified manifest.

Core circuits receive valid, boundary, and invalid witnesses. Linked circuits
add transaction-binding tests: an incorrect public tag and mutations of shared
values that are irrelevant to the local component policy must be rejected.
Separate linked bundles are also checked for application-level tag equality.

No trusted setup or proof generation is required.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment_manifest import (
    CAMPAIGNS,
    CircuitExperiment,
    SeparateProofBaseline,
    filter_experiments,
    input_path,
    logical_experiments,
    required_circuit_specs,
)
from run_bench import run_command, source_fingerprint


FIELD_PRIME = int(
    "21888242871839275222246405745257275088548364400416034343698204186575808495617"
)

BINDING_ONLY_MUTATIONS: dict[str, str] = {
    "linked_valid_limit_validity_32": "spent_window",
    "linked_valid_limit_limit_32": "balance",
    "linked_account_budget_validity_32": "spent_private",
    "linked_account_budget_transition_32": "spent_window",
    "linked_account_budget_limit_32": "receiver_balance",
    "linked_account_budget_budget_32": "sender_balance",
    "linked_token_bundle_membership_32_depth_16": "amount",
    "linked_token_bundle_nullifier_32_depth_16": "token_value",
    "linked_token_bundle_validity_32_depth_16": "spent_private",
    "linked_token_bundle_budget_32_depth_16": "token_randomness",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--campaign", choices=CAMPAIGNS, default="paper")
    parser.add_argument("--families", nargs="*")
    parser.add_argument("--experiments", nargs="*")
    parser.add_argument(
        "--no-generate-inputs",
        action="store_true",
        help="Fail rather than regenerate deterministic inputs when missing.",
    )
    return parser.parse_args()


def integer(payload: dict[str, Any], key: str) -> int:
    return int(payload[key])


def assign(payload: dict[str, Any], key: str, value: int) -> None:
    payload[key] = str(value)


def increment(payload: dict[str, Any], key: str) -> None:
    payload[key] = str((integer(payload, key) + 1) % FIELD_PRIME)


def boundary_and_invalid(
    family: str, valid: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    boundary = copy.deepcopy(valid)
    invalid = copy.deepcopy(valid)

    if family == "local_financial_validity":
        amount = integer(valid, "amount")
        assign(boundary, "balance", amount)
        assign(invalid, "balance", amount - 1)
    elif family == "operating_limit":
        total = integer(valid, "spent_window") + integer(valid, "amount")
        assign(boundary, "window_limit", total)
        assign(invalid, "window_limit", total - 1)
    elif family == "privacy_budget":
        total = integer(valid, "spent_private") + integer(valid, "amount")
        assign(boundary, "anonymity_budget", total)
        assign(invalid, "anonymity_budget", total - 1)
    elif family == "state_transition_and_conservation":
        assign(invalid, "sender_new", integer(valid, "sender_new") + 1)
    elif family == "merkle_membership":
        increment(invalid, "root")
    elif family == "nullifier_correctness":
        increment(invalid, "nullifier")
    elif family == "local_validity_and_operating_limit":
        amount = integer(valid, "amount")
        total = integer(valid, "spent_window") + amount
        assign(boundary, "balance", amount)
        assign(boundary, "window_limit", total)
        assign(invalid, "window_limit", total - 1)
    elif family == "account_policy_core":
        total = integer(valid, "spent_window") + integer(valid, "amount")
        assign(boundary, "window_limit", total)
        assign(invalid, "receiver_new", integer(valid, "receiver_new") + 1)
    elif family == "account_policy_with_privacy_budget":
        spent_total = integer(valid, "spent_window") + integer(valid, "amount")
        private_total = integer(valid, "spent_private") + integer(valid, "amount")
        assign(boundary, "window_limit", spent_total)
        assign(boundary, "anonymity_budget", private_total)
        assign(invalid, "anonymity_budget", private_total - 1)
    elif family == "token_policy_bundle":
        private_total = integer(valid, "spent_private") + integer(valid, "amount")
        assign(boundary, "anonymity_budget", private_total)
        assign(invalid, "anonymity_budget", private_total - 1)
    else:
        raise ValueError(f"No functional mutation defined for family: {family}")

    return boundary, invalid


def compile_if_needed(
    project_root: Path, spec: CircuitExperiment
) -> tuple[Path, Path, Path]:
    fingerprint = source_fingerprint(project_root, spec)
    build_dir = (
        project_root / "build" / "validation" / f"{spec.name}_{fingerprint[:12]}"
    )
    circuit_path = project_root / "circuits" / spec.circuit_file
    base_name = circuit_path.stem
    witness_js = build_dir / f"{base_name}_js" / "generate_witness.js"
    wasm = build_dir / f"{base_name}_js" / f"{base_name}.wasm"

    if not witness_js.exists() or not wasm.exists():
        build_dir.mkdir(parents=True, exist_ok=True)
        run_command(
            [
                "circom",
                str(circuit_path),
                "--r1cs",
                "--wasm",
                "--sym",
                "-l",
                str(project_root / "node_modules"),
                "-o",
                str(build_dir),
            ],
            cwd=project_root,
        )
    return build_dir, witness_js, wasm


def witness_succeeds(
    project_root: Path,
    build_dir: Path,
    witness_js: Path,
    wasm: Path,
    payload: dict[str, Any],
) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="validation_", dir=str(build_dir)) as tmp:
        tmp_dir = Path(tmp)
        input_json = tmp_dir / "input.json"
        witness = tmp_dir / "witness.wtns"
        input_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        result = run_command(
            [
                "node",
                str(witness_js),
                str(wasm),
                str(input_json),
                str(witness),
            ],
            cwd=project_root,
            check=False,
        )
        output = f"{result.stdout}\n{result.stderr}"[-3000:]
        return result.returncode == 0 and witness.exists(), output


def ensure_inputs(
    project_root: Path,
    specs: list[CircuitExperiment],
    no_generate: bool,
) -> None:
    missing = [input_path(project_root, spec.name) for spec in specs]
    missing = [path for path in missing if not path.exists()]
    if missing and not no_generate:
        run_command(
            [
                "node",
                str(project_root / "scripts" / "generate_inputs.js"),
                "--out-dir",
                str(project_root / "inputs" / "valid"),
            ],
            cwd=project_root,
        )
        missing = [path for path in missing if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing benchmark inputs:\n" + "\n".join(f"- {p}" for p in missing)
        )


def append_result(
    rows: list[dict[str, Any]],
    *,
    spec_name: str,
    family: str,
    composition_id: str | None,
    case_name: str,
    expected: bool,
    actual: bool,
    diagnostic: str,
) -> None:
    passed = actual == expected
    rows.append(
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "experiment_name": spec_name,
            "family": family,
            "composition_id": composition_id,
            "case": case_name,
            "expected_success": expected,
            "actual_success": actual,
            "test_passed": passed,
            "diagnostic": "" if passed else diagnostic,
        }
    )
    print(f"{spec_name:58s} {case_name:32s} {'PASS' if passed else 'FAIL'}")


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    if shutil.which("circom") is None or shutil.which("node") is None:
        raise EnvironmentError("circom and node must be available in PATH")

    logical = filter_experiments(
        logical_experiments(args.campaign),
        names=args.experiments,
        families=args.families,
    )
    if not logical:
        raise ValueError("No experiments selected")
    specs = required_circuit_specs(logical)
    ensure_inputs(project_root, specs, args.no_generate_inputs)

    rows: list[dict[str, Any]] = []
    for spec in specs:
        source = input_path(project_root, spec.name)
        valid = json.loads(source.read_text(encoding="utf-8"))
        build_dir, witness_js, wasm = compile_if_needed(project_root, spec)

        if spec.binding_mode == "tx_tag":
            cases: list[tuple[str, dict[str, Any], bool]] = [("valid", valid, True)]

            bad_tag = copy.deepcopy(valid)
            increment(bad_tag, "tx_tag")
            cases.append(("incorrect_tx_tag", bad_tag, False))

            mutation_field = BINDING_ONLY_MUTATIONS.get(spec.name)
            if mutation_field:
                changed = copy.deepcopy(valid)
                increment(changed, mutation_field)
                cases.append((f"binding_only_{mutation_field}", changed, False))

        else:
            boundary, invalid = boundary_and_invalid(spec.family, valid)
            cases = [
                ("valid", valid, True),
                ("boundary", boundary, True),
                ("invalid", invalid, False),
            ]

        for case_name, payload, expected in cases:
            actual, diagnostic = witness_succeeds(
                project_root, build_dir, witness_js, wasm, payload
            )
            append_result(
                rows,
                spec_name=spec.name,
                family=spec.family,
                composition_id=spec.composition_id,
                case_name=case_name,
                expected=expected,
                actual=actual,
                diagnostic=diagnostic,
            )

    # Application-level bundle rule for linked separate proofs.
    for experiment in logical:
        if not isinstance(experiment, SeparateProofBaseline):
            continue
        if experiment.binding_mode != "tx_tag":
            continue
        tags = [
            str(
                json.loads(
                    input_path(project_root, name).read_text(encoding="utf-8")
                )["tx_tag"]
            )
            for name in experiment.components
        ]
        valid_match = len(tags) == len(experiment.components) and len(set(tags)) == 1
        append_result(
            rows,
            spec_name=experiment.name,
            family=experiment.family,
            composition_id=experiment.composition_id,
            case_name="bundle_equal_tags",
            expected=True,
            actual=valid_match,
            diagnostic=str(tags),
        )

        mismatched = list(tags)
        mismatched[-1] = str((int(mismatched[-1]) + 1) % FIELD_PRIME)
        rejected = len(set(mismatched)) != 1
        append_result(
            rows,
            spec_name=experiment.name,
            family=experiment.family,
            composition_id=experiment.composition_id,
            case_name="bundle_mismatched_tag_rejected",
            expected=True,
            actual=rejected,
            diagnostic=str(mismatched),
        )

    output = project_root / "results" / f"functional_validation_{args.campaign}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    failures = sum(not row["test_passed"] for row in rows)
    print(f"Wrote {output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
