#!/usr/bin/env python3
"""Run functional valid/boundary/invalid checks before timing experiments.

The script compiles circuits when necessary but does not run trusted setup or
proof generation. An invalid test succeeds when witness generation fails.
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

from experiment_manifest import circuit_experiments, filter_experiments, input_path
from run_bench import run_command, source_fingerprint


FIELD_PRIME = int(
    "21888242871839275222246405745257275088548364400416034343698204186575808495617"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--families", nargs="*")
    parser.add_argument("--experiments", nargs="*")
    return parser.parse_args()


def integer(payload: dict[str, Any], key: str) -> int:
    return int(payload[key])


def assign(payload: dict[str, Any], key: str, value: int) -> None:
    payload[key] = str(value)


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
        assign(
            invalid,
            "sender_new",
            integer(valid, "sender_new") + 1,
        )
    elif family == "merkle_membership":
        assign(invalid, "root", (integer(valid, "root") + 1) % FIELD_PRIME)
    elif family == "nullifier_correctness":
        assign(
            invalid,
            "nullifier",
            (integer(valid, "nullifier") + 1) % FIELD_PRIME,
        )
    elif family == "local_validity_and_operating_limit":
        amount = integer(valid, "amount")
        total = integer(valid, "spent_window") + amount
        assign(boundary, "balance", amount)
        assign(boundary, "window_limit", total)
        assign(invalid, "window_limit", total - 1)
    elif family == "account_policy_core":
        total = integer(valid, "spent_window") + integer(valid, "amount")
        assign(boundary, "window_limit", total)
        assign(
            invalid,
            "receiver_new",
            integer(valid, "receiver_new") + 1,
        )
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


def compile_if_needed(project_root: Path, spec: Any) -> tuple[Path, Path, Path]:
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


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    if shutil.which("circom") is None or shutil.which("node") is None:
        raise EnvironmentError("circom and node must be available in PATH")

    selected = filter_experiments(
        circuit_experiments(), names=args.experiments, families=args.families
    )
    if not selected:
        raise ValueError("No circuits selected")

    rows: list[dict[str, Any]] = []
    for spec in selected:
        source = input_path(project_root, spec.name)
        if not source.exists():
            raise FileNotFoundError(
                f"Missing {source}; run node scripts/generate_inputs.js first"
            )
        valid = json.loads(source.read_text(encoding="utf-8"))
        boundary, invalid = boundary_and_invalid(spec.family, valid)
        build_dir, witness_js, wasm = compile_if_needed(project_root, spec)

        for case_name, payload, expected in (
            ("valid", valid, True),
            ("boundary", boundary, True),
            ("invalid", invalid, False),
        ):
            actual, output = witness_succeeds(
                project_root, build_dir, witness_js, wasm, payload
            )
            passed = actual == expected
            rows.append(
                {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "experiment_name": spec.name,
                    "family": spec.family,
                    "bits": spec.bits,
                    "merkle_depth": spec.merkle_depth,
                    "case": case_name,
                    "expected_witness_success": expected,
                    "actual_witness_success": actual,
                    "test_passed": passed,
                    "diagnostic": "" if passed else output,
                }
            )
            print(
                f"{spec.name:48s} {case_name:8s} "
                f"{'PASS' if passed else 'FAIL'}"
            )

    output = project_root / "results" / "functional_validation.csv"
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
